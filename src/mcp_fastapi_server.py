#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/

#   Source files:  https://github.com/markwkiehl/medium_gcp_mcp_fastapi
#   See public article "Deploying an MCP Server on Google Cloud Run" at: https://medium.com/@markwkiehl/deploying-an-mcp-server-on-google-cloud-run-6faebe26500e


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.0"



"""
This is a template for a MCP server deployed to Google Cloud Run service.


A Model Context Protocol (MCP) compatible server providing two endpoints: 
    /api/search_local_docs for hybrid search (Chroma Vector + BM25) against a local document store.
    /api/search_web for external web search using Tavily.

FastAPI is utilized to create the MCP server.

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
- The lifespan function executes, and initializes all your application components such as load_dotenv based on the environment variables.
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

    

PIP INSTALL:

google-cloud-storage
google-cloud-run
python-dotenv
rich
fastapi
uvicorn

"""

# ----------------------------------------------------------------------
# Imports

from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import sys
import shutil
import json
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
# API Keys

api_key_openai = os.environ.get("OPENAI_API_KEY")
if api_key_openai:
    logger.info(f"OpenAI API Key check: Key is SET. sk-...{api_key_openai[-4:]}")
else:
    logger.error("OpenAI API key not set!  Set OPENAI_API_KEY in Cloud Run environment variables.")

# ----------------------------------------------------------------------
# Constants

DEBUG = True


# __file__ is /app/src/main.py
# .parent is /app/src
# .parent.parent is /app
PATH_BASE = Path(__file__).resolve().parent.parent

# Define the data directory: /app/data
PATH_DATA = PATH_BASE / "data"

app_config = {
    "llm_provider": "openai",                                           # The LLM provider we are using
    "embedding_model": "text-embedding-3-small",                        # The model for creating document embeddings
    "max_step_iterations": 3,                                           # The maximum number iterations per master plan step. 
    "path_chroma_db": None,                                             # Folder for the Chroma db vector store
    "chroma_collection_name": "Biography_of_Christopher_Diaz",          # Chroma db collection name
    "bucket_mount_path": None                                           # Google Storage bucket mount path
}
# Note: after lifespan(), access 'app_config' this way:
# print(f"chroma_collection_name: {app.state.app_config['chroma_collection_name']}")
# print(f"path_chroma_db: {app.state.app_config['path_chroma_db']}")
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
            if verbose: print("WARNING:  Google CLI folder not found: " + str(path_gcloud))
            #raise Exception("Google CLI has not been installed!")
            return False
        if verbose: print(f"path_gcloud: {path_gcloud}")
        path_file_json = path_gcloud.joinpath("application_default_credentials.json")
        if not path_file_json.exists() or not path_file_json.is_file():
            if verbose: print("WARNING: Application Default Credential JSON file missing: "+ str(path_file_json))
            #raise Exception("File not found: " + str(path_file_json))
            return False
        
        if verbose: print(str(path_file_json))
        return True
    else:
        # Linux, macOS: 
        # $HOME/.config/gcloud/application_default_credentials.json
        # //root/.config/gcloud/application_default_credentials.json
        path_gcloud = Path(Path.home()).joinpath(".config/gcloud/")
        if not path_gcloud.exists():
            if verbose: 
                print("Path.home(): ", str(Path.home()))
                print("WARNING:  Google CLI folder not found: " + str(path_gcloud))
            # WARNING:  Google CLI folder not found: /.config/gcloud
            #raise Exception("Google CLI has not been installed!")
            return False
        if verbose: print(f"path_gcloud: {path_gcloud}")

        path_file_json = path_gcloud.joinpath("application_default_credentials.json")
        if not path_file_json.exists() or not path_file_json.is_file():
            if verbose: print("WARNING: Application Default Credential JSON file missing: "+ str(path_file_json))
            # /root/.config/gcloud/application_default_credentials.json
            #os.environ['GOOGLE_APPLICATION_CREDENTIALS'] ='$HOME/.config/gcloud/application_default_credentials.json'
            #raise Exception("File not found: " + str(path_file_json))
            return False
        
        if verbose: print(str(path_file_json))
        # /root/.config/gcloud/application_default_credentials.json
        return True


def gcp_fileio_test(path_mount:Path, verbose:bool=False):
    """
    Creates a file 'text_file_utf8.txt' in the drive/folder path_mount and writes series of random strings to it.
    Reads back the strings to confirm read operation functionality. 
    """
    # Define the text filename to write/read to.
    path_file = path_mount.joinpath("text_file_utf8.txt")
    print(f"path_file: {path_file}")
    if path_file.is_file():  path_file.unlink()     # Delete the file if it already exists
    if path_file.is_file(): raise Exception(f"Unable to delete file {path_file}")

    # Generate random strings and write them to path_file
    import random
    import string
    length = 40
    characters = string.ascii_letters + string.digits
    
    # Write the file
    print(f"Writing line by line utf-8 text file: {path_file}")
    with open(file=path_file, mode="w", encoding='utf-8') as f:
        for l in range(0, 5):
            rnd_str = ''.join(random.choice(characters) for i in range(length))
            f.write(rnd_str + "\n")
    
    # Read the file
    if not path_file.is_file(): raise Exception(f"File not found {path_file}")
    print(f"Reading line by line utf-8 text file: {path_file}")
    i = 0
    with open(file=path_file, mode="r", encoding='utf-8') as f:
        for line in f.readlines():
            i += 1
            # Only process lines that are not blank by using: if len(line.strip()) > 0:
            if len(line.strip()) > 0: print(f"{i}  {line.strip()}")        # .strip() removes \n


# ---------------------------------------------------------------------------
# FastAPI Lifespan (Startup/Shutdown)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application lifespan startup sequence initiated.")
    
    if gcp_json_credentials_exist():
            # -------------------------------------------------------------------
            # A. LOCAL DEVELOPMENT ENVIRONMENT PATH
            # -------------------------------------------------------------------
            path_bucket_mount = Path(Path.cwd())
            #dotenv_path = path_bucket_mount.joinpath(".env")
            #print(f"INFO: Detected Local Development environment. .env path: {dotenv_path}")

            #if not dotenv_path.is_file(): raise Exception(f"CRITICAL: .env file not found locally at {dotenv_path}. Cannot start.")
            
            # Load environment variables from the local .env file
            #load_dotenv(dotenv_path=dotenv_path) 
            #print("INFO: Local environment variables loaded successfully.")
        
    else:
        # -------------------------------------------------------------------
        # B. CLOUD RUN DEPLOYMENT ENVIRONMENT PATH
        # -------------------------------------------------------------------
        path_bucket_mount = Path(os.environ.get('MOUNT_PATH', '/mnt/storage'))
        path_file_startup_probe = path_bucket_mount.joinpath("startup_probe.txt")
        #dotenv_path = path_bucket_mount.joinpath(".env")
        #print(f"INFO: Detected Cloud Run/Deployment environment. .env path: {dotenv_path}")

        # WAIT/CHECK FOR FUSE CONFIGURATION (Required for GCS FUSE latency)
        max_checks = 10
        check_period = 0.5  # seconds
        
        for i in range(max_checks):
            if path_file_startup_probe.is_file():
                # Load environment variables from the FUSE mount
                #load_dotenv(dotenv_path=dotenv_path) 
                print("INFO: GCS FUSE mount confirmed ready.")
                break
            
            # The startup_probe should handle the waiting, but this acts as a final guard
            print(f"INFO: Waiting for FUSE mount in lifespan... Attempt {i+1}/{max_checks}")
            await asyncio.sleep(check_period)
        else:
            print("CRITICAL WARNING: FUSE file not found in lifespan after checks. Application may be misconfigured or the mount failed.")
            # Application will proceed without the .env keys, likely leading to errors in the / or /api/* endpoints.

    # -------------------------------------------------------------------
    # INITIALIZE DEPENDENT COMPONENTS HERE (Runs after load_dotenv is successful in EITHER path)
    # -------------------------------------------------------------------

    # Attach config to app.state and then update config.
    # NOTE:  path_chroma_db is configured below to use the local, ephemeral /tmp directory from the Cloud Run VM rather than the 
    #        Cloud Storage FUSE mount (used by bucket_mount_path) because GCSFUSE is an object storage interface, not a POSIX-compliant filesystem, 
    #        and it is not designed to support the high-frequency, random, transactional disk operations required by SQLite / ChromaDB / other datbases. 
    #        Failure to do this will result in a "disk I/O error."
    #
    #        bucket_mount_path uses the Cloud Storage FUSE mount for connection to a Google Cloud Storage bucket. 
    #        See the beginning of the script for notes on "Google Cloud Storage FUSE Mount".
    app.state.app_config = {
        "llm_provider": "openai",                                                   # The LLM provider we are using
        "embedding_model": "text-embedding-3-small",                                # The model for creating document embeddings
        "max_step_iterations": 3,                                                   # The maximum number iterations per master plan step. 
        "path_chroma_db": Path("/tmp").joinpath("chroma_langchain_db"),             # Folder for the Chroma db vector store (databases should not reside on Google Cloud Storage FUSE mount) 
        "chroma_collection_name": "Biography_of_Christopher_Diaz",                  # Chroma db collection name
        "bucket_mount_path": path_bucket_mount                                      # Google Storage bucket mount path
    }

    # Verify app.state.app_config contents are valid
    print(f"chroma_collection_name: {app.state.app_config['chroma_collection_name']}")
    print(f"path_chroma_db: {app.state.app_config['path_chroma_db']}")
    print(f"bucket_mount_path: {app.state.app_config['bucket_mount_path']}")

    # Test Google Cloud Storage bucket read/write
    gcp_fileio_test(app.state.app_config['bucket_mount_path'])
    
    if not gcp_json_credentials_exist():
        # Test Google Cloud Run in-memory temporary storage 
        path_chroma_db = Path(str(app.state.app_config['path_chroma_db']))
        if not path_chroma_db.is_dir(): path_chroma_db.mkdir(parents=True, exist_ok=True)
        gcp_fileio_test(path_chroma_db)

    # Example: Initialize the Chroma DB connection now that the environment vars are set
    # database_client = get_chroma_db_connection()
    # print("INFO: Application dependencies initialized successfully.")

    # Application endpoints are now ready to serve traffic.
    yield 

    # 4. SHUTDOWN LOGIC (runs when server is shutting down)
    print("Application shutdown sequence initiated.")

 
# FastAPI Application Initialization
# The 'title' and 'description' fields are important for the auto-generated
# OpenAPI documentation (accessible at /docs), which is crucial for
# any Model Context Protocol (MCP) tool.
app = FastAPI(
    title="Simple MCP Base Server",
    description="A basic FastAPI template ready to be extended into an MCP tool.  It includes access to a Google Cloud Storage bucket. ",
    version=f"{__version__}",
    lifespan=lifespan,       # Attach the lifespan handler
)

# ----------------------------------------------------------------------
# Pydantic Models for Data Validation (Input/Output Schemas)

# Pydantic models define the structure of data for requests (input)
# and responses (output), providing automatic validation and documentation.

class ToolInput(BaseModel):
    """Schema for the input data for the example tool."""
    num1: float
    num2: float
    operation: str = "add"

class ToolOutput(BaseModel):
    """Schema for the output data from the example tool."""
    result: float
    message: str

# ---------------------------------------------------------------------------
# Endpoint Functions

def get_chroma_db_connection():
    """
    Use 'path_bucket_mount' and connect to the Chroma db.
    """
    print(f"get_chroma_db_connection()")
    # dummy return for now
    return None


# ----------------------------------------------------------------------
# Path Operations (API Endpoints)

# Use a simple flag to ensure the probe stops logging once successful
probe_succeeded = False 

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
    print(f"os.environ.get('MOUNT_PATH'): {os.environ.get('MOUNT_PATH')}")
    path_bucket_mount = Path(os.environ.get('MOUNT_PATH', '/mnt/storage'))
    path_file_startup_probe = path_bucket_mount.joinpath("startup_probe.txt")
        
    if path_file_startup_probe.is_file():
        # FUSE mount is ready. Signal Cloud Run to send traffic.
        print(f"INFO: Startup probe succeeded. FUSE file found at: {path_file_startup_probe}. Starting Lifespan...")
        probe_succeeded = True
        return {"status": "ok", "message": "FUSE mount ready, application is starting up."}
    else:
        # FUSE mount is not ready yet. Return a 503 to fail the probe and retry.
        print(f"INFO: Startup probe failed: {path_file_startup_probe} not found. Waiting...")
        raise HTTPException(status_code=503, detail="Waiting for GCS FUSE mount to stabilize.")
    

@app.get("/")
def read_root() -> Dict[str, str]:
    """
    Root endpoint for a simple health check.
    """

    # Verify config contents are valid
    config = app.state.app_config
    print(f"config['chroma_collection_name']: {config['chroma_collection_name']}")
    print(f"config['path_chroma_db']: {config['path_chroma_db']}")
    print(f"config['bucket_mount_path']: {config['bucket_mount_path']}")

    # Check db connection
    vector_store = get_chroma_db_connection()
    # ...

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
def simple_calculator(input_data: ToolInput) -> ToolOutput:
    """
    An example endpoint that simulates a simple tool operation.
    It takes two numbers and performs addition (for simplicity).
    
    In a real MCP server, this would be a specific, well-defined tool.
    """
    if input_data.operation == "add":
        total = input_data.num1 + input_data.num2
        message = f"Successfully calculated the sum of {input_data.num1} and {input_data.num2}."
        return ToolOutput(result=total, message=message)
    else:
        # For a full implementation, you would handle subtraction, multiplication, etc.
        message = f"Operation '{input_data.operation}' not supported yet. Defaulting to addition."
        total = input_data.num1 + input_data.num2
        return ToolOutput(result=total, message=message)

# ----------------------------------------------------------------------
# Programmatic Server Run (Optional, for running as a Python script)

# If you run the file directly as 'python api_mcp_fastapi_server.py', this block 
# will start the Uvicorn server programmatically. This is an alternative 
# to running the server from the command line using 'uvicorn api_mcp_fastapi_server:app'.

if __name__ == "__main__":
    pass

    """
    import uvicorn
    # The programmatic call to uvicorn.run()
    # It tells uvicorn to run the 'app' instance found in the 'api_mcp_fastapi_server' module.
    # host="0.0.0.0" makes the server accessible externally (useful for deployment/containers).
    # port=8000 is the default port.
    uvicorn.run("api_mcp_fastapi_server:app", host="0.0.0.0", port=8000, reload=True)

    # Note: For production use, remove the 'reload=True' option and manage 
    # workers using a process manager like Gunicorn with Uvicorn workers.
    """

    # Assuming the file is named api_mcp_fastapi_server.py, you can start the application using the following Uvicorn command after venv activate:
    # The format is uvicorn [file_name]:[fastapi_app_instance_name] --reload.
    # uvicorn api_mcp_fastapi_server:app --reload
