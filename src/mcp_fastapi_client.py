#
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/

#   Source files:  https://github.com/markwkiehl/medium_gcp_mcp_fastapi
#   See public article "Deploying an MCP Server on Google Cloud Run" at: https://medium.com/@markwkiehl/deploying-an-mcp-server-on-google-cloud-run-6faebe26500e


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.0"
from pathlib import Path
print("'" + Path(__file__).stem + ".py'  v" + __version__)


"""

MCP Server via FastAPI & GCP Cloud Run 

This script is a template for a client that interacts with an MCP Server that has been deployed to Google Cloud Run service.
Deploy the script 'api_mcp_fastapi_server.py' to Google Cloud Run using the Windows OS batch files gcp_1_venv.bat .. gcp_8_bucket_runsvc.bat to create that MCP Server.
Batch file gcp_8_bucket_runsvc.bat will provide the BASE_URL needed by this script to connect to the MCP Server running on Google Cloud Run.
Update BASE_URL in this script and then run it to see it call the MCP Server endpoints. 


This script implements FastAPI, which is built on an ASGI (Asynchronous Server Gateway Interface) framework (Starlette) and runs on an ASGI server (Uvicorn). 
This whole ecosystem is asynchronous.
FastAPI is smart enough to detect a synchronous function and to prevent it from blocking the main asynchronous event loop.  


PIP INSTALL:

google-cloud-storage
google-cloud-run
python-dotenv
rich
fastapi
uvicorn


"""

import requests
import os
import json
from typing import Dict, Any

# ----------------------------------------------------------------------
# Configure the MCP server URL

use_localhost = False
if use_localhost:
    # The base URL of the FastAPI server. 
    # This should match the host and port defined in api_mcp_fastapi_server.py (0.0.0.0:8000).
    BASE_URL = "http://localhost:8000"
else:
    # Google Cloud Platform GCP Cloud Run  
    # Update BASE_URL below with the URL reported after running "gcp_8_bucket_runsvc.bat"). 
    BASE_URL = "https://ci-cd-pipeline-##########-uk.a.run.app"
print(f"BASE_URL: {BASE_URL}")



def get_server_status():
    """
    Checks the server status by requesting the OpenAPI specification 
    and retrieves the MCP server title, description, and version.
    """
    try:
        # Request the OpenAPI specification (FastAPI's documentation endpoint)
        response = requests.get(f"{BASE_URL}/openapi.json")
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        
        openapi_spec = response.json()
        # The metadata is stored under the 'info' key in the OpenAPI spec
        info = openapi_spec.get('info', {})

        print(f"--- MCP Server Metadata & Status ---")
        print(f"Server Status: UP (Confirmed via /openapi.json)")
        print(f"Title: {info.get('title', 'N/A')}")
        print(f"Description: {info.get('description', 'N/A')}")
        print(f"Version: {info.get('version', 'N/A')}")
        print("-" * 20)
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the server.")
        print("Please ensure your FastAPI server is running with: uvicorn mcp_server:app --reload")
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: Failed to retrieve /openapi.json. Server responded with an error.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during status check: {e}")


def run_calculator_tool(num1: float, num2: float, operation: str = "add"):
    """
    Calls the /api/calculator endpoint with structured input.

    :param num1: The first number.
    :param num2: The second number.
    :param operation: The operation to perform (e.g., 'add').
    """
    endpoint = f"{BASE_URL}/api/calculator"

    # Data structure must match the Pydantic 'ToolInput' model in the server
    payload: Dict[str, Any] = {
        "num1": num1,
        "num2": num2,
        "operation": operation
    }

    print(f"--- Executing Tool: {operation} ---")
    print(f"Input: {payload}")

    try:
        # Send the POST request with JSON payload
        response = requests.post(endpoint, json=payload)
        
        # Check for successful response status codes (2xx)
        response.raise_for_status() 

        # Parse the JSON response, which matches the 'ToolOutput' model
        result_data = response.json()
        
        print(f"Output Message: {result_data.get('message')}")
        print(f"Output Result: {result_data.get('result')}")
        print("-" * 20)

    except requests.exceptions.RequestException as e:
        # Handle connection errors or bad server responses
        print(f"ERROR: Failed to execute tool call.")
        print(f"Details: {e}")
        if response is not None and response.text:
            # If server sent back detailed error (e.g., Pydantic validation error)
            print(f"Server Response Content: {response.text}")
        print("-" * 20)


if __name__ == "__main__":
    # 1. Check if the server is up
    get_server_status()
    
    # 2. Run the simple calculator tool
    run_calculator_tool(num1=5.5, num2=10.2, operation="add")
    
    # 3. Test with a different set of numbers
    run_calculator_tool(num1=100, num2=25, operation="add")

    # 4. Test an unsupported operation to see the server's fallback response
    run_calculator_tool(num1=10, num2=3, operation="multiply")