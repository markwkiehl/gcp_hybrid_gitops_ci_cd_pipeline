#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/


__version__ = "0.0.1"
# v0.0.0    Release 2 February 2026
# v0.0.1    Revised with best practices from gcp_rest_api_noaa.

"""
This is a template for a RESTful API server deployed to Google Cloud Run service.


FastAPI is utilized to create the REST API server.
This script will be packaged into a container and configured to run as a Cloud Run Service.
A Cloud Storage volume mount is used to create a bridge between the Cloud Storage bucket
and the Cloud Run container's file system.
Volume mounts allow a container (this script) to access files stored in persistent disks or NFS shares as if they were local.
The feature leverages Cloud Storage FUSE to provide this file system interface.  
When a Cloud Run GCS mount is configured, the bucket name and mount path are explicitly specified.

FastAPI is built on the OpenAPI (formerly Swagger) and JSON Schema standards, it generates interactive documentation automatically without you having to write any extra code.
When the app is deployed to Google Cloud Run, these features will be available at specific sub-paths of the main URL.
    Swagger UI (at /docs)
    ReDoc (at /redoc)


Lifecycle
When Cloud Run starts a container for this app, uvicorn loads this script. Before it opens the door 
to any traffic (including the /ready probe), it executes the code inside lifespan up to the yield statement.
The lifecycle function executes with every instance of the app created by Cloud Run based on demand, so keep it short and fast. 
Once the yield statement is executed in the lifespan function, the application fully runs and endpoints like /ready can be hit
by traffic.  In the case of the /ready endpoint, this is used by Cloud Run during deployment to verify the Google Cloud Storage FUSE mount is loaded.  
Every app instance must verify its own FUSE mount before it can safely accept traffic.
Note that while the app is running (yield), Cloud Run pings the /ready endpoint every 10 seconds. 

When Google Cloud Run decides to shut down the app instance (e.g., because no one has used it for 15 minutes, or you are deploying a new version), 
it sends a SIGTERM signal.  The application stops accepting new connections and resumes the lifespan function after the yield statement.


Overall Architecture Implemented for Cloud Run Deployment:

- Persistent Storage via GCS FUSE:
    The application utilizes Google Cloud Storage (GCS) for persistent file access. 
    Since GCS is object storage, Cloud Run uses GCS FUSE (Filesystem in Userspace) to mount the bucket, 
    making remote objects appear as local files in a directory (e.g., /mnt/storage).

- Server Startup Sequence (Lifespan -> Yield -> Listen):
    The Dockerfile CMD starts the Uvicorn web server. 
    Uvicorn immediately executes the Lifespan Startup block (loading configurations and context) 
    up to the yield statement. Once the yield is reached, Uvicorn opens port 8080 
    and begins listening for HTTP requests.

- Handling FUSE Latency via Startup Probe:
    Google Cloud Run immediately begins polling the /ready endpoint to check if the instance is healthy.
    Because the GCS FUSE mount occurs asynchronously and may take several seconds to appear, 
    the /ready endpoint is designed to return 503 Service Unavailable if the mount is not yet detected. 
    This prevents the application from accepting traffic before it can actually read or write files.

- Traffic Routing:
    The /ready endpoint returns 200 OK only after it confirms the FUSE mount exists and passes 
    I/O validation tests. Once Cloud Run receives this 200 OK response, it considers 
    the instance "Healthy" and begins routing actual user traffic to the /sse endpoint.

    
Google Cloud Run local, ephemeral /tmp directory:

- Non-persistent Storage: 
    The /tmp directory is ephemeral and does not persist across container lifetimes or 
    different running instances of your service.

- Memory-Backed (tmpfs): 
    The /tmp directory is a tmpfs (temporary file system) that resides in the container's 
    allocated RAM, not on disk.

- Memory Limits and OOM: 
    Storage used in /tmp counts directly against your Cloud Run instance's memory limit. 
    If combined usage (Application RAM + /tmp files) exceeds the limit, the container 
    will be terminated with an Out-of-Memory (OOM) error.

- High Performance: 
    While /tmp is significantly faster than GCSFUSE, I/O operations still consume CPU 
    and memory resources. The maximum memory limit for a Cloud Run instance is 32 GiB.


    
Docker Image RO Filesystem
- Use the COPY ./data /app/data command in the Dockerfile.  That data file becomes part of the Read-Only layers of the Docker container image.
- It is static.  It cannot be edited or deleted.  The only way to update it is to redeploy the Docker image.
- It consumes storage with the constainer storage.  It does not consume the RAM allocated to the Cloud Run application like the ephemeral /tmp folder.
- Docker usually grants read access by default, but if you run into "Permission Denied," add RUN chmod -R 755 /app/data to your Dockerfile after the COPY command.



Google Cloud Storage FUSE Mount:
- GCSFUSE is an object storage interface, not a POSIX-compliant filesystem.
- Concurrency: Simultaneous writes to the same object from multiple mounts can lead to data loss, as only the first completed write is saved.
- File Locking and Patching: File locking and in-place file patching are not supported; only whole objects can be written to Cloud Storage.
- Cloud Storage FUSE has significantly higher latency than local file systems and is not recommended for latency-sensitive workloads like databases or applications requiring sub-millisecond random I/O and metadata access.
- Transient errors can occur during read/write operations, so applications should be designed to tolerate such errors.
- Not suitable for workloads with frequent small file operations (under 50 MB), data-intensive training, or checkpoint/restart workloads during the I/O intensive phase.

"""

# ----------------------------------------------------------------------
# Imports

from pathlib import Path
#from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import sys
import time
from contextlib import asynccontextmanager
import asyncio
import json
import httpx
from time import perf_counter



# ---------------------------------------------------------------------------
# Configure logging

# NOTE:
# Always use logger rather than print.  At scale, you can filter the logs by .info, .warning, and .error.
# By default, print() goes to stdout. Depending on the environment, the Python root logger might be sending logs to stderr. 
# You can set an Environment Variable in Cloud Run LOG_LEVEL=WARNING. Even if the code is full of logger.info() calls, they will be discarded instantly by the logger and never sent to Google Cloud
# While Cloud Run captures both print() and logger, they are often processed by different buffers.
# Google Cloud Logging looks for a field named severity to categorize logs (Blue for Info, Orange for Warning, Red for Error). The python-json-logger uses levelname by default.

# Install with: pip install python-json-logger
import logging

# Use a named logger
logger = logging.getLogger(Path(__file__).stem)
logger.setLevel(logging.INFO)

# Setup a standard Text Handler (Not JSON)
# This is what gcloud CLI "pretty prints" best.
if not logger.handlers:
    # Cloud Run captures everything on stdout
    logHandler = logging.StreamHandler(sys.stdout)
    
    # Use a clean, classic format: [LEVEL] Message
    # This format is highly readable in both the CLI and the Console.
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    logHandler.setFormatter(formatter)
    
    logger.addHandler(logHandler)

# Prevent double-logging
logger.propagate = False

logger.info(f"'{Path(__file__).stem}.py' v{__version__}") 
# logger.info(), logger.warning(), logger.error()


# ----------------------------------------------------------------------
# Constants

DEBUG = False

t_boot = perf_counter()

# __file__ is /app/src/main.py
# .parent is /app/src
# .parent.parent is /app
PATH_BASE = Path(__file__).resolve().parent.parent
PATH_GCP = PATH_BASE / "gcp"
PATH_SRC = PATH_BASE / "src"
# Define the data directory: /app/data
PATH_DATA = PATH_BASE / "data"

app_config = {
    "bucket_mount_path": None,                                          # Google Storage bucket mount path
    "path_gcp_tmp": None,                                               # Google Cloud Run ephemeral /tmp
}
# Note: after lifespan(), access 'app_config' this way:
# print(f"bucket_mount_path: {app.state.app_config['bucket_mount_path']}")


# ---------------------------------------------------------------------------
# GCP tools

def savvy_get_os(verbose=False):
    """
    Returns the following OS descriptions depending on what OS the Python script is running in:
        "Windows"
        "Linux"
        "macOS"

    os_name = savvy_get_os()
    """

    import platform

    if platform.system() == "Windows":
        return "Windows"
    elif platform.system() == "Linux":
        return "Linux"
    elif platform.system() == "Darwin":
        return "macOS"
    else:
        raise Exception("Unknown OS: ", platform.system())


def gcp_json_credentials_exist(verbose=False):
    """
    Returns TRUE if the Application Default Credentials (ADC) file "application_default_credentials.json" is found.

    Works with both Windows and Linux OS.

    https://cloud.google.com/docs/authentication/application-default-credentials#personal
    """

    if savvy_get_os() == "Windows":
        # Windows: %APPDATA%\gcloud\application_default_credentials.json
        path_gcloud = Path(Path.home()).joinpath("AppData\\Roaming\\gcloud")
        if not path_gcloud.exists():
            if verbose: logger.info("WARNING:  Google CLI folder not found: " + str(path_gcloud))
            #raise Exception("Google CLI has not been installed!")
            return False
        if verbose: logger.info(f"path_gcloud: {path_gcloud}")
        path_file_json = path_gcloud.joinpath("application_default_credentials.json")
        if not path_file_json.exists() or not path_file_json.is_file():
            if verbose: logger.info("WARNING: Application Default Credential JSON file missing: "+ str(path_file_json))
            #raise Exception("File not found: " + str(path_file_json))
            return False
        
        if verbose: logger.info(str(path_file_json))
        return True
    else:
        # Linux, macOS: 
        # $HOME/.config/gcloud/application_default_credentials.json
        # //root/.config/gcloud/application_default_credentials.json
        path_gcloud = Path(Path.home()).joinpath(".config/gcloud/")
        if not path_gcloud.exists():
            if verbose: 
                logger.info("Path.home(): " + str(Path.home()))
                logger.info("WARNING:  Google CLI folder not found: " + str(path_gcloud))
            # WARNING:  Google CLI folder not found: /.config/gcloud
            #raise Exception("Google CLI has not been installed!")
            return False
        if verbose: logger.info(f"path_gcloud: {path_gcloud}")

        path_file_json = path_gcloud.joinpath("application_default_credentials.json")
        if not path_file_json.exists() or not path_file_json.is_file():
            if verbose: logger.info("WARNING: Application Default Credential JSON file missing: "+ str(path_file_json))
            # /root/.config/gcloud/application_default_credentials.json
            #os.environ['GOOGLE_APPLICATION_CREDENTIALS'] ='$HOME/.config/gcloud/application_default_credentials.json'
            #raise Exception("File not found: " + str(path_file_json))
            return False
        
        if verbose: logger.info(str(path_file_json))
        # /root/.config/gcloud/application_default_credentials.json
        return True


def gcp_fileio_test(path_mount:Path, verbose:bool=False):
    """
    Creates a file 'text_file_utf8.txt' in the drive/folder path_mount and writes series of random strings to it.
    Reads back the strings to confirm read operation functionality. 
    """
    # Define the text filename to write/read to.
    path_file = path_mount.joinpath("text_file_utf8.txt")
    logger.info(f"path_file: {path_file}")
    if path_file.is_file():  path_file.unlink()     # Delete the file if it already exists
    if path_file.is_file(): raise Exception(f"Unable to delete file {path_file}")

    # Generate random strings and write them to path_file
    import random
    import string
    length = 40
    characters = string.ascii_letters + string.digits
    
    # Write the file
    logger.info(f"Writing line by line utf-8 text file: {path_file}")
    with open(file=path_file, mode="w", encoding='utf-8') as f:
        for l in range(0, 5):
            rnd_str = ''.join(random.choice(characters) for i in range(length))
            f.write(rnd_str + "\n")
    
    # Read the file
    if not path_file.is_file(): raise Exception(f"File not found {path_file}")
    logger.info(f"Reading line by line utf-8 text file: {path_file}")
    i = 0
    with open(file=path_file, mode="r", encoding='utf-8') as f:
        for line in f.readlines():
            i += 1
            # Only process lines that are not blank by using: if len(line.strip()) > 0:
            if len(line.strip()) > 0: logger.info(f"{i}  {line.strip()}")        # .strip() removes \n


def get_mount_path() -> Path:
    """
    Return a Path object to the Google Cloud storage bucket FUSE mount location if the app is running in Cloud Run.
    """
    path_bucket_mount = None
    # Define the Mount Path location
    # During deployment, an environment variable MOUNT_PATH is created that points to the Cloud Storage FUSE bucket path.
    mount_env = os.environ.get('MOUNT_PATH')
    if mount_env:
        # MOUNT_PATH environment variable exists because creating the Cloud Storage FUSE bucket is part of the deployment. 
        path_bucket_mount = Path(mount_env)
    elif os.environ.get("K_SERVICE"):
        # Environment variable K_SERVICE is automatically injected by Cloud Run.
        logger.warn("Environment variable MOUNT_PATH expected, but not found.  Defaulting to /mnt/storage")
        path_bucket_mount = Path('/mnt/storage')
    elif gcp_json_credentials_exist():
        # Script is running locally (not in Cloud Run or a Docker container)
        path_bucket_mount = Path(Path.cwd())
    else:
        # Possibly running in a Docker container ???
        msg = f"Unexpected runtime environment found in lifespan(). MOUNT_PATH & K_SERVICE not found. Local ADC not found"
        logger.error(msg)
        raise Exception(msg)

    return path_bucket_mount


def get_tmp_path() -> Path:
    """
    Return a Path object to the Google Cloud Run ephemeral /tmp folder.
    """
    path_gcp_tmp = None
    if os.environ.get("K_SERVICE"):
        # Environment variable K_SERVICE is automatically injected by Cloud Run.
        path_gcp_tmp = Path("/tmp")
    elif gcp_json_credentials_exist():
        # Script is running locally (not in Cloud Run or a Docker container)
        path_gcp_tmp = Path(Path.cwd())
    else:
        # Possibly running in a Docker container ???
        msg = f"Unexpected runtime environment found in lifespan(). MOUNT_PATH & K_SERVICE not found. Local ADC not found"
        logger.error(msg)
        raise Exception(msg)

    return path_gcp_tmp



# ---------------------------------------------------------------------------
# FastAPI Lifespan (Startup/Shutdown)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    IMPORTANT: 
    
    "lifespan" is executed every time a Cloud Run instance scales up.
    Google Cloud Run automatically adds instances based on demand.  

    uvicorn (the web server) does not bind to the listening port (8080) until AFTER the lifespan startup logic completes (yield).

    This lifespan function checks for the presence of 'startup_probe.txt' in the GCS FUSE mount path.
    This file acts as a signal that the GCS bucket has been successfully mounted and is accessible.
    The 'startup_probe.txt' file MUST be created by the deployment process (e.g., Cloud Build, init container)
    before the Cloud Run service is considered ready to handle requests that depend on the GCS mount.
    """

    logger.info("Application lifespan startup sequence initiated.")

    app.state.probe_succeeded = False
    
    # Define the Mount Path location
    path_bucket_mount = get_mount_path()

    # Get Cloud Run ephemeral /tmp folder
    path_gcp_tmp = get_tmp_path()

    # Ensure all keys are initialized before use
    app.state.app_config = {
        "bucket_mount_path": path_bucket_mount,
        "path_gcp_tmp": path_gcp_tmp,
    }

    # Inject GCP_PROJ_ID into the environment.
    # Formerly used by noaa_ncei.py
    #os.environ["GCP_PROJ_ID"] = app.state.app_config['gcp_proj_id']

    # Initialize the global httpx AsyncClient
    # A 120-second timeout accommodates the occasional slow NOAA response
    timeout_config = httpx.Timeout(120.0)
    # Store the client in app.state so all route handlers can access the same connection pool
    app.state.http_client = httpx.AsyncClient(timeout=timeout_config, follow_redirects=True)
    logger.info("httpx.AsyncClient initialized.")

    # Execute other initialization code here, before the yield statement. 

    # Optional block of code
    if os.environ.get("K_SERVICE"):
        pass
        # Environment variable K_SERVICE is automatically injected by Cloud Run.
    else:
        pass
        # Local non-Cloud Run environment

    logger.info(f"lifecycle took {round(perf_counter()-t_boot,1)} s")

    # Application endpoints are now ready to serve traffic.
    yield 

    # 4. SHUTDOWN LOGIC (runs when server is shutting down)
    logger.info("Application shutdown sequence initiated.")

    # Cleanly close the connection pool to prevent resource leaks
    await app.state.http_client.aclose()
    logger.info("httpx.AsyncClient closed.")

 
# FastAPI Application Initialization
# The 'title' and 'description' fields are important for the auto-generated
# OpenAPI documentation (accessible at /docs), which is crucial for
# any REST API server.
app = FastAPI(
    title="Simple REST API Server",
    description="""
    A basic REST API server template ready to be extended for your project needs.  
    It includes access to a Google Cloud Storage bucket. 
    """,
    version=f"{__version__}",
    contact={
            "name": "Mark W Kiehl",
            "url": "http://mechatronicsolutionsllc.com/",
        },
    lifespan=lifespan,       # Attach the lifespan handler
)

# ----------------------------------------------------------------------
# Pydantic Models for Data Validation

class CalculatorInput(BaseModel):
    num1: float
    num2: float
    operation: str = "add"


class ExtApiInput(BaseModel):
    url: str

# ----------------------------------------------------------------------
# Path Operations (API Endpoints)

# An important note about the endpoints:
# Do not prefix the 'def' with 'async' when calling synchronous, long-running functions.  
# When a synchronous function takes 70+ seconds inside an async def route, it entirely blocks the FastAPI event loop. 
# No other users can connect to the application during that time.

# With the prefix 'async' before 'def' removed, FastAPI will automatically detect this and run the blocking function in a separate background threadpool, 
# keeping the server responsive.


@app.get("/healthz")
def liveness_check():
    """
    This is a simple liveness probe for the Google Cloud Load Balancer. It should be as fast as possible.
    """
    return {"status": "alive"}


@app.get("/readyz")
def readiness_check(request: Request):
    """Checks if the environment and storage are fully ready."""
    if not request.app.state.probe_succeeded:
        raise HTTPException(status_code=503, detail="Service initializing")
    return {"status": "ready"}


@app.get("/ready")
def startup_probe(request: Request):
    """
    Cloud Run Startup Probe: Checks FUSE readiness.
    """

    # No need to check FUSE every time if we already passed.
    if request.app.state.probe_succeeded:
        return {"status": "ok", "message": "FUSE mount and probe confirmed ready."}

    # Get the path to Google Cloud Storage bucket FUSE mount & the startup probe file.
    path_bucket_mount = request.app.state.app_config['bucket_mount_path']
    # Check if mount point exists (Fast check)
    if not path_bucket_mount.exists():  raise HTTPException(status_code=503, detail="Waiting for GCS FUSE mount to stabilize.")
    
    path_file_startup_probe = path_bucket_mount.joinpath("startup_probe.txt")
    if path_file_startup_probe.is_file():
        # FUSE mount is ready. Signal Cloud Run to send traffic.
        logger.info(f"Startup probe succeeded. FUSE file found at: {path_file_startup_probe}.")

        # Verify bucket
        # Use path_bucket_mount directly here to avoid race conditions with app.state (app.state.app_config['bucket_mount_path'])
        if DEBUG: 
            logger.info(f"Running I/O validation tests on: {path_bucket_mount}")
            gcp_fileio_test(path_bucket_mount)

    else:
        # FUSE mount is not ready yet. Return a 503 to fail the probe and retry.
        logger.error(f"Startup probe and/or I/O tests failed!")
        raise HTTPException(status_code=503, detail="Waiting for GCS FUSE mount to stabilize.")

    # Test Google Cloud Run in-memory temporary storage (local, ephemeral /tmp directory).
    path_gcp_tmp = request.app.state.app_config['path_gcp_tmp']
    if not path_gcp_tmp.is_dir(): path_gcp_tmp.mkdir(parents=True, exist_ok=True)
    if DEBUG: 
        logger.info(f"Running I/O validation tests on: {path_gcp_tmp}")
        gcp_fileio_test(path_gcp_tmp)

    logger.info("Startup probe and I/O tests succeeded.")
    request.app.state.probe_succeeded = True
    return {"status": "ok", "message": "FUSE mount ready, application is starting up."}


@app.get("/")
def read_root() -> Dict[str, str]:
    """
    This is for users and developers. It provides a friendly "Hello World," a status summary, and links to documentation like Swagger UI.
    """

    # Verify config contents are valid
    config = app.state.app_config
    logger.info(f"config['bucket_mount_path']: {config['bucket_mount_path']}")

    # Check that OPENAI_API_KEY is correctly configured as an environment variable.
    openai_key_val = os.environ.get("OPENAI_API_KEY")
    # NEVER log the full API key! Log only a status and the last 4 characters for verification.
    if openai_key_val:
        logger.info(f"OpenAI API Key check: Key is SET. sk-...{openai_key_val[-4:]}")
    else:
        # Logging as ERROR/CRITICAL here confirms the root cause of the 500
        logger.error("OpenAI API key not set!  Set OPENAI_API_KEY in Cloud Run environment variables.")
        return {"status": "ok", "message": "Server is running, BUT OPENAI_API_KEY not found!."}

    return {"status": "ok", "message": "Server is running. See /docs for API schema."}



@app.post("/api/calculator")
async def calculate(data: CalculatorInput):
    """
    RESTful endpoint for the simple calculator.
    """
    num1 = data.num1
    num2 = data.num2
    operation = data.operation

    if operation == "add":
        result = num1 + num2
        message = f"Successfully calculated the sum of {num1} and {num2}."
    else:
        # Defaulting to addition as per your original logic
        message = f"Operation '{operation}' not supported. Defaulting to addition."
        result = num1 + num2

    return {"result": result, "message": message}


import random
from http import HTTPStatus

async def savvy_request_get_async(
    url: str, 
    client: httpx.AsyncClient, 
    params: dict = None, 
    retries: int = 3, 
    headers: dict = None, 
    verbose: bool = False
):
    """
    Asynchronous version of savvy_request_get.
    Makes a GET request with retries on certain HTTP errors (e.g., 503) or connection issues,
    using a randomized backoff to avoid server overload.

    Returns the response object from a HTTP GET to 'url' of up to 'retries' attempts for HTTP response codes 429,500-504.
    Returns None for other errors. 
    """
    if url is None:
        raise ValueError("Argument 'url' not passed to function")

    retry_codes = [
        HTTPStatus.TOO_MANY_REQUESTS,       # 429
        HTTPStatus.INTERNAL_SERVER_ERROR,   # 500
        HTTPStatus.BAD_GATEWAY,             # 502
        HTTPStatus.SERVICE_UNAVAILABLE,     # 503
        HTTPStatus.GATEWAY_TIMEOUT,         # 504
    ]

    for attempt in range(1, retries + 1):
        if attempt > 1: verbose = True
        try:
            # The timeout duration is handled by the client configuration passed in from lifespan
            response = await client.get(url=url, params=params, headers=headers)
            
            # Show any 301 redirects
            if response.history: 
                if not response.history[0].url == response.url:
                    logger.warning(100*"-")
                    logger.warning(f"URL redirected!")
                    logger.warning(f"{response.history[0].url} -> {response.url}")
                    logger.warning(100*"-")
                #logger.info(f"Original URL: {response.history[0].url}")
                #logger.info(f"Final URL: {response.url}")
            # -----------------------------------

            response.raise_for_status()
            return response  # Success
            
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in retry_codes:
                jitter = random.uniform(0, 2)
                wait_time = attempt * 3 + jitter
                if verbose:
                    logger.warning(f"HTTP {code} on attempt {attempt}/{retries}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                # Note: httpx uses .reason_phrase instead of .reason
                logger.error(f"HTTP Error {code}: {e.response.reason_phrase}")
                return None
                
        except httpx.RequestError as e:
            # Catches network-level errors and httpx.TimeoutException
            jitter = random.uniform(0, 2)
            wait_time = attempt * 3 + jitter
            if verbose:
                logger.warning(f"Request exception on attempt {attempt}/{retries}: {e}. Retrying in {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)
            continue

    if verbose:
        logger.error(f"Failed to get a successful response after {retries} attempts.")
    return None


async def ex_savvy_request_get_async(url: str, client: httpx.AsyncClient, verbose: bool = False):
    
    headers = None
    try:
        # Pass verbose down to the retry handler
        req = await savvy_request_get_async(url=url, client=client, headers=headers, verbose=verbose)
    except Exception as e:
        logger.error(f"Exception in ex_savvy_request_get_async() for url {url}: {repr(e)}")
        return None
    
    if req is None:
        logger.warning(f"Request failed and returned None for url: {url}")
        return None

    # Protect against successful HTTP requests that return non-JSON bodies
    try:
        return req.json()
    except Exception as e:
        logger.error(f"JSON decode error for url {url}: {repr(e)}")
        return None

@app.post("/api/ext_api_call")
async def do_ext_api_call(request: Request, input_data: ExtApiInput) -> dict:
    """
    Simulate a simple external API call
    """

    t_start = perf_counter()

                           
    msg = f"ext_api_call"

    # Extract the global client from app.state
    http_client = request.app.state.http_client
    
    # Await the async data layer function and pass the client AND the missing url
    result = await ex_savvy_request_get_async(url=input_data.url, client=http_client, verbose=False)

    if result is None:
        return {"result": "ERROR", "message": "An error occurred contacting the API"}

    print(f"result:\n{result}")

    logger.info(f"/api/ext_api_call took {round(perf_counter()-t_start,1)} s")

    return {"result": result, "message": msg}




if __name__ == "__main__":
    pass

    # WARNING: Only run this locally, NOT in Google Cloud Run or in a Docker container. 
    if gcp_json_credentials_exist():
        import uvicorn
        # The programmatic call to uvicorn.run()
        # It tells uvicorn to run the 'app' instance found in the 'api_mcp_fastapi_server' module.
        # host="0.0.0.0" makes the server accessible externally (useful for deployment/containers).
        # port=8000 is the default port.
        uvicorn.run(f"{Path(__file__).stem}:app", host="0.0.0.0", port=8000, reload=True)

        # ALTERNATIVELY: To run this script locally in a Windows command (cmd) window:
        # 1) Open a Windows command (cmd) window.
        # 2) Navigate to the project folder and activate the Python virtual environment with: .venv/scripts/activate
        # 3) Navigate to the same folder as where this script resides (cd /src).
        # 4) Execute the following:  uvicorn rest_api_noaa_server:app --reload

