(This repository is a template for creating and deploying projects to the Google Cloud.  See gcp/README.md)
(This file is intended to be edited by the user and serve as a reference and description of the Python project created from this template)

# Project Name

Short, clear description of what the project does and who it’s for.

---

## Overview

This project solves the problem of ...
It was created to make it easier to ...
Typical use cases include ...

---

## Features

- Feature one that provides clear value
- Feature two that improves performance or usability
- Cross-platform support (Windows, macOS, Linux)

---

## Requirements

- Python 3.10+
- pip
- Any additional system dependencies (if applicable)

---

## Installation


---


## Quick Start


---


## Usage


---


## Configuration

This project supports configuration via environment variables injected into the deployed container from a .env file.

---

## Project Structure

D:\Documents\..\projects\py_project\
│   README.md						← Information about the project.
│   .dockerignore
│   .gcloudignore					← Critical for managing the size of the upload to Google Cloud (.dockerignore is not enough).
│
└── src\							← Python source code folder.
    └── mcp_fastapi_server.py		← The Python script to deploy to Google Cloud Run. MUST specify in gcp_constant.txt under PYTHON_FILENAME.
    └── mcp_fastapi_client.py		← Python client script that tests access to the Model Context Protocol (MCP) Server (mcp_fastapi_server.py).
    └── .env						← File must exist, but can be empty. Any API Keys will be injected into the container as environment variables.
│
└── data\							← Read-only static data files available in the container to the app when deployed.
│
└── gcp\							← Setup, configuration, and deployment related files. 
    └── gcp_constants.txt			← Names for the various Google Cloud items to create and configure (user, project, billing, region, etc.)
    └── pip_install.txt				← Python libraries to "pip install" by the batch file "make_py_venv.bat".
    └── make_py_venv.bat			← Batch file to create a Python virtual environment with the libraries installed from the list in "pip_install.txt".
    └── gcp_generator.py			← Python script that reads the constants from "gcp_constants.txt" and writes "main.tf", "cloudbuild.yaml", "gcp_bootstrap.bat", and "requirements.txt".
    └── gcp_cleanup.bat				← Batch file to delete the Google Cloud project and all associated resources. 
    └── README.md					← This file.


---

## Tests


---

## Troubleshooting


---

## License

MIT License


---

## Author

Mark Kiehl


---

## Acknowledgments




