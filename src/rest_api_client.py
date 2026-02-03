#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.0"


"""

This script is a template for a client that interacts with an RESTful API Server that has been deployed to Google Cloud Run service.
Deploy the script 'rest_fastapi_server.py' to Google Cloud Run.
Update BASE_URL in this script with the Google Cloud Run URL. 


This script implements FastAPI, which is built on an ASGI (Asynchronous Server Gateway Interface) framework (Starlette) and runs on an ASGI server (Uvicorn). 
This whole ecosystem is asynchronous.  FastAPI is smart enough to detect a synchronous function and to prevent it from blocking the main asynchronous event loop.  


"""

from pathlib import Path
# pip install
import httpx
import asyncio
import sys


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

DEBUG = True

# __file__ is /app/src/main.py
# .parent is /app/src
# .parent.parent is /app
PATH_BASE = Path(__file__).resolve().parent.parent
PATH_GCP = PATH_BASE / "gcp"
PATH_SRC = PATH_BASE / "src"
# Define the data directory: /app/data
PATH_DATA = PATH_BASE / "data"


# Configure the REST API server URL

use_localhost = False
if use_localhost:
    # The base URL of the FastAPI server. 
    # This should match the host and port defined in rest_fastapi_server.py (0.0.0.0:8000).
    BASE_URL = "http://localhost:8000"
else:
    # Google Cloud Platform GCP Cloud Run  
    # Update BASE_URL below with the URL reported after running "gcp_bootstrap.bat"). 
    BASE_URL = "https://ci-cd-pipeline-##########-uk.a.run.app"
if DEBUG: logger.info(f"BASE_URL: {BASE_URL}")


async def get_server_status(client: httpx.AsyncClient) -> bool:
    """
    Checks the server status using a shared client. 
    Returns True if the server responds successfully, False otherwise.
    """
    try:
        # We check the OpenAPI spec as a heartbeat
        response = await client.get(f"{BASE_URL}/openapi.json", timeout=2.0)
        if response.status_code == 200:
            spec = response.json()
            title = spec.get("info", {}).get("title", "Unknown")
            logger.info(f"--- Server '{title}' is ONLINE ---")
            return True
        return False
    except (httpx.RequestError, httpx.HTTPStatusError):
        logger.error(f"--- Server is OFFLINE at {BASE_URL} ---")
        return False


async def run_calculator_tool(client: httpx.AsyncClient, num1: float, num2: float, operation: str = "add"):
    """
    Executes the calculator tool using a shared client.
    """
    logger.info(f"--- Executing Tool: {operation} ---")
    
    url = f"{BASE_URL}/api/calculator"
    payload = {
        "num1": num1,
        "num2": num2,
        "operation": operation
    }

    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result_data = response.json()
        
        logger.info(f"Output Message: {result_data.get('message')}")
        logger.info(f"Output Result: {result_data.get('result')}")
        logger.info("-" * 20)
    except Exception as e:
        logger.error(f"ERROR: Failed to execute tool call. Details: {e}")



async def main():
    # Initialize the client once to enable connection pooling
    async with httpx.AsyncClient() as client:
        # Pass the shared client to all functions

        # Check if the REST API server is up
        server_online = await get_server_status(client)
        if not server_online: return None
        
        # Test run_calculator_tool()
        await run_calculator_tool(client, 5.5, 10.2, "add")
        await run_calculator_tool(client, 10, 3, "multiply")

if __name__ == "__main__":
    asyncio.run(main())
