#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/

# MIT License
# Copyright (c) 2026 Mechatronic Solutions LLC

"""
## Technical Implementation
- **Resilient Asynchronous Architecture:** Built using `httpx` and `asyncio` for true non-blocking Input/Output (I/O). This prevents threadpool exhaustion during unexpected National Oceanic and Atmospheric Administration (NOAA) National Centers for Environmental Information (NCEI) API latency spikes, ensuring the service remains highly concurrent and cost-effective when deployed to serverless environments like Google Cloud Run.

"""

__version__ = "0.0.0"
# v0.0.0    


from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import sys
from time import perf_counter
from datetime import datetime, timezone, timedelta, date
import pandas as pd
from google.cloud import firestore
import httpx
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

# ---------------------------------------------------------------------------
# API Keys

if os.environ.get("K_SERVICE"):
    pass
    # Environment variable K_SERVICE is automatically injected by Cloud Run.
    # gcp_bootstrap.bat will inject all .env contents into environment.
else:
    pass
    # Local non-Cloud Run environment
    if PATH_SRC.joinpath(".env").is_file():
        logger.info(f"Retrieving API keys from {PATH_SRC.joinpath(".env")}")
        # Retrieve API Keys stored in the local .env file (if it exists).
        try:
            # pip install python-dotenv
            from dotenv import load_dotenv
        except Exception as e:
            raise Exception(f"{e} \t Is dotenv module installed?  pip install python-dotenv")
        # Load environment variables from the .env file
        load_dotenv()
    else:
        logger.error(f"File not found: {PATH_SRC.joinpath(".env")}")

#openai_key_val = os.environ.get("OPENAI_API_KEY")
#if openai_key_val:
#    logger.info(f"OpenAI API Key check: Key is SET. sk-...{openai_key_val[-4:]}")
#else:
#    # Logging as ERROR/CRITICAL here confirms the root cause of the 500
#    logger.error("OpenAI API key not set!  Set OPENAI_API_KEY in Cloud Run environment variables.")
#    raise Exception("OpenAI API key not set!  Set OPENAI_API_KEY in Cloud Run environment variables or load the .env file.")

# ---------------------------------------------------------------------------

# Initialize Firestore Client
#project_id = os.environ.get("GCP_PROJECT_ID")
#project_id = "scenic-iq-v0-0"
#app.state.db = firestore.Client(project=project_id) if project_id else firestore.Client()




if __name__ == '__main__':
    pass



