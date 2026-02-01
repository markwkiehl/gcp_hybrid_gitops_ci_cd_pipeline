#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.0"



"""
This is a template for a RESTful API server deployed to Google Cloud Run service.


FastAPI is utilized to create the REST API server.

This script will be packaged into a container and configured to run as a Cloud Run Job.
A Cloud Storage volume mount is used to create a bridge between the Cloud Storage bucket
and the Cloud Run container's file system.
Volume mounts allow a container (this script) to access files stored in persistent disks or NFS shares as if they were local.
The feature leverages Cloud Storage FUSE to provide this file system interface.  
When a Cloud Run GCS mount is configured, the bucket name and munt path are explicitly specified.



Overall architecture implemented for Cloud Run deployment:
- The application requires access to persistent files, like the .env configuration, which are stored in a Google Cloud Storage (GCS) Bucket. 
  Since GCS is object storage (not a file system), a bridge is needed.  
  GCS FUSE (Filesystem in Userspace) is a feature provided by Cloud Run that mounts the GCS bucket. 
  It makes the remote bucket contents appear as a local directory (e.g., /mnt/storage) inside the container.
- The Python FastAPI application, running with Uvicorn, provides the necessary control flow to handle the FUSE delay.
- The Dockerfile's CMD command starts the Uvicorn web server immediately. 
  This allows the server to start listening on port 8080 right away, preventing the immediate "nothing listening" timeout.
- The gcloud run deploy command starts the container and hits /ready. The /ready endpoint returns 503 until the FUSE mount is ready.
- Once /ready returns 200 OK, Cloud Run considers the deployment healthy and proceeds with the application startup sequence, which includes calling the lifespan function.
- The lifespan function executes, and initializes all your application components.
- Only after the lifespan block successfully completes does the application truly yield, allowing the server to accept live user traffic.


Google Cloud Run local, ephemeral /tmp directory:
- The /tmp directory is ephemeral, meaning it does not persist across container lifetimes.
- The /tmp directory is a tmpfs (temporary file system) that uses the container's allocated RAM, not separate disk space.
  Therefore, the size of the files in /tmp directly counts against your Cloud Run instance's total memory limit.
  If the total memory usage (App RAM + /tmp files) exceeds the container's memory limit, the container will be terminated with an Out-of-Memory error.
  The maximum memory for a Cloud Run instance is 32 GiB.
- Files in /tmp are not shared between different running container instances of your service.
- While using /tmp is much faster than GCSFUSE, the I/O operations still consume your container's CPU and memory resources.


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


FastAPI is built on the OpenAPI (formerly Swagger) and JSON Schema standards, it generates interactive documentation automatically without you having to write any extra code.
When the app is deployed to Google Cloud Run, these features will be available at specific sub-paths of the main URL.
    Swagger UI (at /docs)
    ReDoc (at /redoc)
"""

# ----------------------------------------------------------------------
# Imports

from pathlib import Path
#from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import sys
import time
from contextlib import asynccontextmanager
import asyncio

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

DEBUG = True

# __file__ is /app/src/main.py
# .parent is /app/src
# .parent.parent is /app
PATH_BASE = Path(__file__).resolve().parent.parent
PATH_GCP = PATH_BASE / "gcp"
PATH_SRC = PATH_BASE / "src"
# Define the data directory: /app/data
PATH_DATA = PATH_BASE / "data"

app_config = {
    "llm_provider": "openai",                                           # The LLM provider we are using
    "embedding_model": "text-embedding-3-small",                        # The model for creating document embeddings
    "max_step_iterations": 3,                                           # The maximum number iterations per master plan step. 
    "bucket_mount_path": None                                           # Google Storage bucket mount path
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


# ---------------------------------------------------------------------------
# FastAPI Lifespan (Startup/Shutdown)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    IMPORTANT: 
    
    "lifespan" is executed every time a Cloud Run instance scales up.
    Google Cloud Run automatically adds instances based on demand.  

    This lifespan function checks for the presence of 'startup_probe.txt' in the GCS FUSE mount path.
    This file acts as a signal that the GCS bucket has been successfully mounted and is accessible.
    The 'startup_probe.txt' file MUST be created by the deployment process (e.g., Cloud Build, init container)
    before the Cloud Run service is considered ready to handle requests that depend on the GCS mount.
    """

    logger.info("Application lifespan startup sequence initiated.")
    
    if gcp_json_credentials_exist():
        # Anything here executes only in local development environment.
        
        path_bucket_mount = Path(Path.cwd())
        # load_dotenv()
        
    else:
        # Anything here only executes in Cloud Run / VM / Docker container

        path_bucket_mount = Path(os.environ.get('MOUNT_PATH', '/mnt/storage'))
        path_file_startup_probe = path_bucket_mount.joinpath("startup_probe.txt")

        # WAIT/CHECK FOR FUSE CONFIGURATION (Required for GCS FUSE latency)
        max_checks = 10
        check_period = 0.5  # seconds
        
        for i in range(max_checks):
            if path_file_startup_probe.is_file():
                logger.info("INFO: GCS FUSE mount confirmed ready.")
                break
            
            # The startup_probe should handle the waiting, but this acts as a final guard
            logger.warn(f"INFO: Waiting for FUSE mount in lifespan... Attempt {i+1}/{max_checks}")
            await asyncio.sleep(check_period)
        else:
            logger.error("CRITICAL WARNING: FUSE file not found in lifespan after checks. Application may be misconfigured or the mount failed.")
            # Application will proceed without the .env keys, likely leading to errors in the / or /api/* endpoints.

    # -------------------------------------
    # INITIALIZE DEPENDENT COMPONENTS HERE 
    # -------------------------------------

    # Ensure all keys are initialized before use
    app.state.app_config = {
        "llm_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "max_step_iterations": 3,
        "bucket_mount_path": path_bucket_mount,
    }

    # Application endpoints are now ready to serve traffic.
    yield 

    # 4. SHUTDOWN LOGIC (runs when server is shutting down)
    logger.info("Application shutdown sequence initiated.")

 
# FastAPI Application Initialization
# The 'title' and 'description' fields are important for the auto-generated
# OpenAPI documentation (accessible at /docs), which is crucial for
# any REST API server.
app = FastAPI(
    title="Simple REST API Server",
    description="A basic REST API server template ready to be extended for your project needs.  It includes access to a Google Cloud Storage bucket. ",
    version=f"{__version__}",
    lifespan=lifespan,       # Attach the lifespan handler
)


# ----------------------------------------------------------------------
# Pydantic Models for Data Validation

class CalculatorInput(BaseModel):
    num1: float
    num2: float
    operation: str = "add"


# ----------------------------------------------------------------------
# Path Operations (API Endpoints)


# Use a simple flag to ensure the probe stops logging once successful
probe_succeeded = False 

@app.get("/healthz")
def liveness_check():
    """
    This is a simple liveness probe for the Google Cloud Load Balancer. It should be as fast as possible.
    """
    return {"status": "alive"}


@app.get("/readyz")
def readiness_check():
    """Checks if the environment and storage are fully ready."""
    if not probe_succeeded:
        raise HTTPException(status_code=503, detail="Service initializing")
    return {"status": "ready"}


@app.get("/ready")
def startup_probe():
    """
    Cloud Run Startup Probe: Checks FUSE readiness.
    """
    global probe_succeeded
    
    # No need to check FUSE every time if we already passed.
    if probe_succeeded:
        return {"status": "ok", "message": "FUSE mount and probe confirmed ready."}

    # Safely define paths
    logger.info(f"os.environ.get('MOUNT_PATH'): {os.environ.get('MOUNT_PATH')}")
    path_bucket_mount = Path(os.environ.get('MOUNT_PATH', '/mnt/storage'))
    path_file_startup_probe = path_bucket_mount.joinpath("startup_probe.txt")

    if path_file_startup_probe.is_file():
        # FUSE mount is ready. Signal Cloud Run to send traffic.
        logger.info(f"Startup probe succeeded. FUSE file found at: {path_file_startup_probe}. Starting Lifespan...")

        # Verify bucket
        # Use path_bucket_mount directly here to avoid race conditions with app.state (app.state.app_config['bucket_mount_path'])
        logger.info(f"Running I/O validation tests on: {path_bucket_mount}")
        gcp_fileio_test(path_bucket_mount)

        # Test Google Cloud Run in-memory temporary storage (local, ephemeral /tmp directory).
        path_gcp_tmp_ephemeral = Path("/tmp")
        if not path_gcp_tmp_ephemeral.is_dir(): path_gcp_tmp_ephemeral.mkdir(parents=True, exist_ok=True)
        logger.info(f"Running I/O validation tests on: {path_gcp_tmp_ephemeral}")
        gcp_fileio_test(path_gcp_tmp_ephemeral)
        
        logger.info("Startup probe and I/O tests succeeded.")
        probe_succeeded = True
        return {"status": "ok", "message": "FUSE mount ready, application is starting up."}
    else:
        # FUSE mount is not ready yet. Return a 503 to fail the probe and retry.
        logger.error(f"Startup probe and/or I/O tests failed!")
        raise HTTPException(status_code=503, detail="Waiting for GCS FUSE mount to stabilize.")
    

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
        # 4) Execute the following:  uvicorn rest_api_server:app --reload

