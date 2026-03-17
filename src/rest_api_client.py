#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.1"
# v0.0.0    initial release
# v0.0.1    

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
import json


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

API_KEY = None

BASE_URL = "http://localhost:8000"

# If you are a paid subscriber, update the BASE_URL and API_KEY below with those provide to you with your subscription:
#API_KEY = "your-39-character-api-key-#############"
#BASE_URL = "https://weatherforensics.dev/api/pro"
#API_KEY = "AIzaSyB3b-GrcjZYNqnEsWSd3DM0od64h9DqoBU"

if DEBUG: logger.info(f"BASE_URL: {BASE_URL}")
if DEBUG: logger.info(f"API_KEY: {API_KEY}")



def decode_nested_json(data):
    """Recursively parses stringified JSON inside dictionaries or lists.
    
    Usage:

        # Parse the outer layer
        initial_dict = json.loads(json_str)
        # Decode any hidden JSON strings inside
        fully_decoded_dict = decode_nested_json(initial_dict)
        # Print beautifully
        print(json.dumps(fully_decoded_dict, indent=4))

    
    """
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            # If the decoded string is another dict or list, keep digging
            if isinstance(parsed, (dict, list)):
                return decode_nested_json(parsed)
            return parsed
        except (json.JSONDecodeError, TypeError):
            # It's just a normal string, leave it alone
            return data
    elif isinstance(data, dict):
        return {k: decode_nested_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [decode_nested_json(item) for item in data]
    else:
        return data


async def get_server_status(client: httpx.AsyncClient, verbose:bool=False) -> bool:
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


async def run_ext_api_call(client: httpx.AsyncClient, api_url: str = "add"):
    """
    Executes the calculator tool using a shared client.
    """
    logger.info(f"--- Executing Tool: {api_url} ---")
    
    url = f"{BASE_URL}/api/ext_api_call"
    payload = {
        "url": api_url,
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
    # Initialize the client once to enable connection pooling.
    # Inject the API key as a global query parameter for all requests.
    # Follow any redirects.
    async with httpx.AsyncClient(timeout=360.0, params={"key": API_KEY}, follow_redirects=True) as client:
        # Pass the shared client to all functions

        # Check if the REST API server is up
        server_online = await get_server_status(client, verbose=False)
        if server_online: 
            logger.info(f"The server is ONLINE  {BASE_URL}")
        else:
            raise Exception(f"The REST API server is offline!  {BASE_URL}")
        
        # Test run_calculator_tool()
        await run_calculator_tool(client, 5.5, 10.2, "add")
        #await run_calculator_tool(client, 10, 3, "multiply")

        # Test run_ext_api_call
        await run_ext_api_call(client, "https://httpbin.org/json")


if __name__ == "__main__":
    asyncio.run(main())
