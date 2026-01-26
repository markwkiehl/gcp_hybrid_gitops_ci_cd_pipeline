
#   Written by:  Mark W Kiehl
#   http://mechatronicsolutionsllc.com/
#   http://www.savvysolutions.info/savvycodesolutions/


# Define the script version in terms of Semantic Versioning (SemVer)
# when Git or other versioning systems are not employed.
__version__ = "0.0.6"
# v0.0.0    14 Jan 2026
# v0.0.1    Removed [cite: *] that AI added during audit. Revised path_file_py_script_for_cloud_run
# v0.0.2    Several minor optimizations to gcp_bootstrap.bat
# v0.0.3    Added command gcloud config set project
# v0.0.4    Revised generate_dockerfile() for non-Streamlit app.  Added BigQuery CLI install if needed.
# v0.0.5    Added service account (SA) permissions for read/metadata access to BigQuery.
# v0.0.6    Added check that project GCP_BQ_PROJ_ID exists. 

import os
from pathlib import Path
import re

print(f"'{Path(__file__).stem}.py' v{__version__}")

# __file__ is /app/src/main.py
# .parent is /app/src
# .parent.parent is /app
PATH_BASE = Path(__file__).resolve().parent.parent

PATH_GCP = PATH_BASE / "gcp"
PATH_SRC = PATH_BASE / "src"

print(f"PATH_BASE: {PATH_BASE}")
print(f"PATH_GCP: {PATH_GCP}")
print(f"PATH_SRC: {PATH_SRC}")

if not Path(PATH_BASE).is_dir(): raise Exception(f"Folder not found: {PATH_BASE}")
if not Path(PATH_GCP).is_dir(): raise Exception(f"Folder not found: {PATH_GCP}")
if not Path(PATH_SRC).is_dir(): raise Exception(f"Folder not found: {PATH_SRC}")

def get_app_version(file_path: Path):
    """Parses the version string from the Python script."""
    if not file_path.is_file():
        return "unknown"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Looks for __version__ = "0.2.7" or similar
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            return match.group(1) if match else "0.0.0"
    except Exception:
        return "error"
    

def generate_dockerfile(path_file_dockerfile:Path, path_file_py_script_for_cloud_run:str):
    """
    Generates a Dockerfile and specifies 'path_file_py_script_for_cloud_run' at the end for the CMD command.
    """

    # Get just the Python filename (no filename extension) from path_file_py_script_for_cloud_run
    filename_only = path_file_py_script_for_cloud_run.split("/")[-1].strip()
    filename_only = filename_only.split(".")[0].strip()
    #print(f"filename_only: '{filename_only}'")

    # Delete the Dockerfile if it already exists (makes sure it can be overwritten later).
    if path_file_dockerfile.is_file(): 
        try:
          path_file_dockerfile.unlink()
        except Exception as e:
            print(e)
            return False
    
    # Create the Dockerfile content.
    dockerfile_content = f"""# syntax=docker/dockerfile:1 

# Define a default value for the argument PY_VER
ARG PY_VER=3.12

# slim version of Python 3.## to minimize the size of the container 
FROM python:${{PY_VER}}-slim

# Set the working directory inside the container 
WORKDIR /app

# Copy the requirements file into the container at /app 
COPY requirements.txt /app

# Copy the data folder from root to /app/data 
COPY data /app/data

# Copy the source code directory into the container at /app/src 
COPY src /app/src

# Sometimes Cloud Run instances have strict "User" permissions. 
# Fix that: 
RUN chmod -R 755 /app/data

# Set the environment variable so Python can find the modules in /app/src 
ENV PYTHONPATH="/app/src"

# Optimize pip 
ENV PIP_DEFAULT_TIMEOUT=100 \\
    # Allow statements and log messages to immediately appear 
    PYTHONUNBUFFERED=1 \\
    # disable a pip version check to reduce run-time & log-spam 
    PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    # cache is useless in docker image, so disable to reduce image size 
    PIP_NO_CACHE_DIR=1

# Install any needed packages specified in requirements.txt 
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080 for both Flask and Gunicorn server 
EXPOSE 8080

# If app is FastAPI, use Uvicorn.
# It’s faster, lighter, and Cloud Run handles scaling. 
# If app is (Flask, Django WSGI): Use Gunicorn (pure WSGI). 
# For Gunicorn: 
# Use ENTRYPOINT to definitively launch Gunicorn with Uvicorn workers. 
# This ensures the command is executed as the primary process. 
# Cloud Run expects your application to listen on the port specified by the PORT environment variable. 
# Use 0.0.0.0 to bind to all available network interfaces.

# IMPORTANT: The container must read the $PORT variable and bind its server to it. 
# Using the shell form of CMD to allow environment variable expansion. 

# Below is only for a streamlit app
# Added --server.enableXsrfProtection false because Cloud Run already terminates connections safely.  This removes overhead on every interaction.
#CMD streamlit run {path_file_py_script_for_cloud_run} --server.address 0.0.0.0 --server.port $PORT --server.enableXsrfProtection false\n

# Below is for uvicorn
CMD uvicorn src.{filename_only}:app --host 0.0.0.0 --port $PORT\n
"""

    try:
        with open(path_file_dockerfile, "w", encoding="utf-8") as f:
            f.write(dockerfile_content)
        print(f"Successfully generated {path_file_py_script_for_cloud_run}")
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    return True


def validate_constants(c):
    """Validates GCP naming conventions for specific constants."""
    errors = []

    # 1. Project ID: 6-30 chars, letters, numbers, hyphens. Must start with letter.
    if not re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', c.get('GCP_PROJ_ID', '')):
        errors.append(f"Invalid GCP_PROJ_ID: '{c.get('GCP_PROJ_ID')}' (Must be 6-30 chars, lowercase, numbers, or hyphens)")

    # 2. BigQuery Dataset: ONLY letters, numbers, and underscores. No hyphens.
    if not re.match(r'^[a-zA-Z0-9_]+$', c.get('GCP_BQ_DATASET_ID', '')):
        errors.append(f"Invalid GCP_BQ_DATASET_ID: '{c.get('GCP_BQ_DATASET_ID')}' (Hyphens not allowed, use underscores)")

    # 3. Bucket Name: 3-63 chars, lowercase, numbers, dots, hyphens.
    if not re.match(r'^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$', c.get('GCP_GS_BUCKET', '')):
        errors.append(f"Invalid GCP_GS_BUCKET: '{c.get('GCP_GS_BUCKET')}'")

    # 4. Artifact Repo: 1-63 chars, lowercase, numbers, hyphens.
    if not re.match(r'^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$', c.get('GCP_REPOSITORY', '')):
        errors.append(f"Invalid GCP_REPOSITORY: '{c.get('GCP_REPOSITORY')}'")

    if errors:
        print("\n!!! VALIDATION FAILED !!!")
        for err in errors:
            print(f" - {err}")
        return False
    
    print("✓ All constants validated successfully.")
    return True


def load_constants(filepath):
    constants = {}
    if not os.path.exists(filepath):
        print(f"ERROR: {filepath} not found.")
        return None
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                constants[key.strip()] = value.strip()
    return constants


def generate_files():
    # Make sure required files exist
    path_file_gcp_constants = PATH_GCP.joinpath("gcp_constants.txt")
    if not path_file_gcp_constants.is_file(): raise Exception(f"File not found: {path_file_gcp_constants}")

    path_file_terraform = PATH_BASE.joinpath("main.tf")
    #if not path_file_terraform.is_file(): raise Exception(f"File not found: {path_file_terraform}")

    path_file_cloudbuild_yaml = PATH_BASE.joinpath("cloudbuild.yaml")
    #if not path_file_cloudbuild_yaml.is_file(): raise Exception(f"File not found: {path_file_cloudbuild_yaml}")

    path_file_pip_install = PATH_GCP.joinpath("pip_install.txt")
    if not path_file_gcp_constants.is_file(): raise Exception(f"File not found: {path_file_gcp_constants}")

    path_file_env = PATH_SRC.joinpath(".env")
    if not path_file_env.is_file(): raise Exception(f"The file /src/.env is required to exist.  It can be empty, but if not empty it will inject all contents to the container as environment")

    # READ THE .ENV FILE IN PYTHON
    env_vars_list = []
    if path_file_env.is_file():
        with open(path_file_env, 'r') as e:
            for line in e:
                line = line.strip()
                # Exclude comments and empty lines
                if line and not line.startswith('#') and '=' in line:
                    env_vars_list.append(line)
    
    # Create the comma-separated string for the cloudbuild.yaml file written later.
    # Example: "KEY1=VAL1,KEY2=VAL2"
    env_string = ",".join(env_vars_list)

    # Consider the need to delete an existing terraform.tfstate in PATH_BASE if it exists.

    if path_file_pip_install.exists():
        with open(path_file_pip_install, 'r') as src_file:
            requirements_content = src_file.read()
        
        # Write contents from pip_install.txt to the Project Root as requirements.txt (where Docker expects it)
        with open(PATH_BASE / "requirements.txt", 'w') as dest_file:
            dest_file.write(requirements_content)
        print("✓ Successfully published requirements.txt to project root from /gcp/pip_install.txt")
    else:
        print(f"ERROR: {path_file_pip_install} not found. Build will fail.")


    c = load_constants(path_file_gcp_constants)
    if not c: return

    # Validate the constants in gcp_constants.txt against Google Cloud requirements. 
    if not validate_constants(c):
            return

    # Verify the Python script exists in /src
    path_file_py_script_for_cloud_run = PATH_SRC.joinpath(c['PYTHON_FILENAME'])
    if not path_file_py_script_for_cloud_run.is_file(): 
        raise Exception(f"The Python script specified for 'PYTHON_FILENAME' in 'gcp_constants.txt' doesn't exist in the folder /src")

    # Get the version from the source code
    app_script_path = PATH_SRC / c['PYTHON_FILENAME']
    current_version = get_app_version(app_script_path)
    print(f"Python script version: {current_version}")

    # Use a string representing the internal container path instead of the Windows Path object for purposes of the Dockerfile
    path_file_py_script_for_cloud_run = f"src/{c['PYTHON_FILENAME']}"
    path_file_dockerfile = PATH_BASE.joinpath("Dockerfile")
    # Write the Dockerfile
    if not generate_dockerfile(path_file_dockerfile, path_file_py_script_for_cloud_run):
        raise Exception(f"ERROR generating the Dockerfile")

    # Generate main.tf (Infrastructure) in project root
    with open(path_file_terraform, 'w') as f:
        f.write(f'''# Generated by gcp_generator.py
provider "google" {{
  project = "{c['GCP_PROJ_ID']}"
  region  = "{c['GCP_REGION']}"
}}

resource "google_storage_bucket" "app_bucket" {{
  name          = "{c['GCP_GS_BUCKET']}"
  location      = "{c['GCP_GS_BUCKET_LOCATION']}"
  force_destroy = true
  lifecycle_rule {{
    condition {{ age = 1 }}
    action {{ type = "Delete" }}
  }}
}}

resource "google_bigquery_dataset" "dataset" {{
  dataset_id                 = "{c['GCP_BQ_DATASET_ID']}"
  location                   = "{c['GCP_REGION']}"
  delete_contents_on_destroy = true
}}
''')

    # Generate cloudbuild.yaml (Pipeline) in project root
    # Note the double braces {{ }} to escape the Python f-string
    # Added :${BUILD_ID} to the image name to bypass all registry caching
    with open(path_file_cloudbuild_yaml, 'w') as f:
        f.write(f'''# Generated by gcp_generator.py
steps:
  # Create the probe file startup_probe.txt used to determine when the FUSE bucket is ready and upload it directly to the bucket
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'bash'
    args: 
      - '-c'
      - |
        echo "ready" > startup_probe.txt
        gcloud storage cp startup_probe.txt gs://${{_BUCKET}}/startup_probe.txt

  # Build the image with a unique tag
  # Note that argument '--no-cache' was added to force Docker to ignore caches during the build (so that updates to the Python file in /src will be recognized).
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '--no-cache', '-t', '${{_REGION}}-docker.pkg.dev/${{PROJECT_ID}}/${{_REPO}}/${{_IMAGE}}:${{BUILD_ID}}', '.']

  # Push the image with a unique tag
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${{_REGION}}-docker.pkg.dev/${{PROJECT_ID}}/${{_REPO}}/${{_IMAGE}}:${{BUILD_ID}}']

  # Deploy to Cloud Run with a unique tag
  # Arguments for quick startup: --min-instances=1,--concurrency=2,--cpu=1,--memory=1Gi,--no-cpu-throttling
  # BUILD_ID is a built-in substitution variable provided automatically by Google Cloud Build.
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        # Deploy to Cloud Run (Note the '\\' for line continuation)
        gcloud run deploy ${{_SERVICE_NAME}} \\
          --image ${{_REGION}}-docker.pkg.dev/${{PROJECT_ID}}/${{_REPO}}/${{_IMAGE}}:${{BUILD_ID}} \\
          --region ${{_REGION}} \\
          --add-volume name=${{_VOL_NAME}},type=cloud-storage,bucket=${{_BUCKET}} \\
          --add-volume-mount mount-path=${{_MOUNT_PATH}},volume=${{_VOL_NAME}} \\
          --service-account ${{_SVC_ACCOUNT}} \\
          --timeout 300s \\
          --cpu-boost \\
          --startup-probe httpGet.port=8080,httpGet.path=/ready,initialDelaySeconds=10,failureThreshold=15,periodSeconds=20,timeoutSeconds=5 \\
          --set-env-vars "MOUNT_PATH=${{_MOUNT_PATH}},DEPLOYED_VERSION={current_version},{env_string}" \\
          --platform managed \\
          --allow-unauthenticated \\
          --min-instances=1 \\
          --concurrency=1 \\
          --cpu=2 \\
          --memory=2Gi \\
          --no-cpu-throttling \\
          
substitutions:
  _REGION: {c['GCP_REGION']}
  _REPO: {c['GCP_REPOSITORY']}
  _IMAGE: {c['GCP_IMAGE']}
  _SERVICE_NAME: {c['GCP_RUN_JOB']}
  _VOL_NAME: {c['GCP_RUN_JOB_VOL_NAME']}
  _MOUNT_PATH: {c['GCP_RUN_JOB_VOL_MT_PATH']}
  _BUCKET: {c['GCP_GS_BUCKET']}
  _SVC_ACCOUNT: {c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com

options:
  logging: CLOUD_LOGGING_ONLY
''')

    # Generate Version-Specific Bootstrap in /gcp
    ver = "v" + c['GCP_PROJ_ID'].split("-v")[-1].strip()
    #bootstrap_name = f"gcp_bootstrap_{ver}.bat"
    bootstrap_name = f"gcp_bootstrap.bat"
    path_file_bootstrap = PATH_GCP.joinpath(bootstrap_name)
    with open(path_file_bootstrap, 'w') as f:
        f.write(f'''@echo off
echo Bootstrapping Project: {c['GCP_PROJ_ID']}

rem GCP_PROJ_ID check
CALL gcloud projects describe {c['GCP_PROJ_ID']} >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo WARNING: Project {c['GCP_PROJ_ID']} already exists!
    echo This is okay if it is a repeat execution of gcp_bootstrap.bat  CTRL-C to abort
    pause
)

:: Verify that Project ID GCP_BQ_PROJ_ID exists.
CALL gcloud projects describe {c['GCP_BQ_PROJ_ID']} >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: The project {c['GCP_BQ_PROJ_ID']} for BigQuery specified by GCP_BQ_PROJ_ID in gcp_constants.txt does NOT exist!
    echo If you don't need BigQuery or you want to create a BigQuery dataset under project {c['GCP_PROJ_ID']}, then use GCP_BQ_PROJ_ID={c['GCP_PROJ_ID']}
    EXIT /B
)


:: Make sure the .env file exists
if NOT EXIST "{PATH_SRC}\.env" (
  echo ERROR: File not found "{PATH_SRC}\.env"
  EXIT /B
)

:: Update local gcloud components (if needed).
echo.
echo Checking if gcloud components need to be updated..
CALL gcloud components update --quiet

:: Only need to do the following once per project.
if NOT EXIST "{PATH_GCP}\gcp_bootstrap.bat" (
  :: Sets the identity for gcloud commands.
  CALL gcloud auth login

  :: Sets the identity for Terraform to use.  (user-based ADC)
  CALL gcloud auth application-default login
)

:: Switch the active Google Cloud Command Line Interface (CLI) project to GCP_PROJ_ID
echo.
echo Switching the active Google Cloud Command Line Interface (CLI) project to {c['GCP_PROJ_ID']}.  
echo Ignore any messages about: 'environment' tag
CALL gcloud config set project {c['GCP_PROJ_ID']}
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR trying to switch the active Google CLI project to {c['GCP_PROJ_ID']}.  
    EXIT /B
)

:: PROJECT CREATION
echo.
CALL gcloud projects create {c['GCP_PROJ_ID']}
IF %ERRORLEVEL% NEQ 0 (
    echo The Google project {c['GCP_PROJ_ID']} could not be created, or it already exists.
    pause
)

:: IDENTITY SETUP
:: Note: 'gcloud auth login' is for the CLI. 
:: '--update-adc' does both (CLI and Terraform) in one window.
CALL gcloud auth login --update-adc

:: BILLING & CONFIG
:: Link the new project to your billing account
CALL gcloud billing projects link {c['GCP_PROJ_ID']} --billing-account={c['GCP_BILLING_ACCOUNT']}
:: Set the local CLI to point to the new project
echo Setting local CLI context and quota project...
CALL gcloud config set project {c['GCP_PROJ_ID']}

:: ADC QUOTA (Crucial for Terraform)
:: Tell Google which project to bill for Terraform's API calls.
CALL gcloud auth application-default set-quota-project {c['GCP_PROJ_ID']}


echo Enabling Services...
:: iam.googleapis.com 
:: iamcredentials.googleapis.com 
:: cloudresourcemanager.googleapis.com 
:: cloudbuild.googleapis.com 
:: run.googleapis.com 
:: artifactregistry.googleapis.com 
:: storage.googleapis.com
:: apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com
CALL gcloud services enable iam.googleapis.com iamcredentials.googleapis.com cloudresourcemanager.googleapis.com cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com --project={c['GCP_PROJ_ID']}
CALL gcloud services enable bigquery.googleapis.com --project={c['GCP_PROJ_ID']}

rem API Gateway
call gcloud services enable apigateway.googleapis.com --project={c['GCP_PROJ_ID']}
call gcloud services enable servicemanagement.googleapis.com --project={c['GCP_PROJ_ID']}
call gcloud services enable servicecontrol.googleapis.com --project={c['GCP_PROJ_ID']}
call gcloud services enable apikeys.googleapis.com --project={c['GCP_PROJ_ID']}

rem Project Service Account
rem %GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com
rem {c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com

:: Create the Service Account
echo Creating Project-Local Service Account {c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com ..
CALL gcloud iam service-accounts create {c['GCP_SVC_ACT_PREFIX']} --project={c['GCP_PROJ_ID']}

echo.
echo Waiting 60 seconds for API and IAM propagation...
timeout /t 60 /nobreak


:: Verify BigQuery CLI is installed.  Install if needed.
echo.
echo Verifying BigQuery CLI (bq) is installed (ignore any reported errors here).
CALL bq version
IF %ERRORLEVEL% NEQ 0 (
	CALL gcloud components install bq --quiet
)
:: ERRORLEVEL=1 even after successful install.  Use bq version to check installation.
CALL bq version
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR: install of BigQuery CLI failed.   
	EXIT /B
)


echo Granting Permissions to Service Account...
@echo on

:: Grant Storage Admin (derived from your discovery)
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/storage.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Service Account User role to the service account:
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant BigQuery Admin (integrated from gcp_bigquery.bat logic)
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Storage Admin role to the service account:
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/storage.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Cloud Run Developer role to the service account:
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/run.developer
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant the SA permission to READ BigQuery data via GCP_BQ_PROJ_ID
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.dataViewer
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant the SA permission to BigQuery metadata GCP_BQ_PROJ_ID
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.metadataViewer
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant the SA permission to BigQuery jobs
CALL gcloud projects add-iam-policy-binding {c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.jobUser
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant the specific cross-project permissions required for the Cloud Run service in mcp-noaa-v#-# to query data in bq-noaa-v0-0.
:: The service account must be granted access inside the BigQuery data project (bq-noaa-v0-0) so it can read the tables and run query jobs there.
CALL gcloud projects add-iam-policy-binding {c['GCP_BQ_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.jobUser
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)
CALL gcloud projects add-iam-policy-binding {c['GCP_BQ_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/bigquery.dataViewer
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

@echo off

echo Deleting Artifact Registry repository: {c['GCP_REPOSITORY']} in {c['GCP_REGION']} - only exists if first time execution...
CALL gcloud artifacts repositories delete {c['GCP_REPOSITORY']} --location={c['GCP_REGION']} --project={c['GCP_PROJ_ID']} --quiet
IF %ERRORLEVEL% EQU 0 (
    echo Registry deleted successfully.
) ELSE (
    echo Registry deletion failed or it does not exist.
    pause
)

echo Creating Artifact Registry...
CALL gcloud artifacts repositories create {c['GCP_REPOSITORY']} --repository-format=docker --location={c['GCP_REGION']} --project={c['GCP_PROJ_ID']}
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo Artifact Registry creation failed. This is often due to propagation delay, or because it already exists.
    pause
)

CALL cd..

echo.
echo This batch file %~n0%~x0 has succeeeded so far without no errors.  
echo Ready for Infrastructure (Terraform) and Deployment (Cloud Build).
echo - Run: terraform init from /
echo - Run: terraform apply from /
echo - Run: gcloud builds submit --config cloudbuild.yaml --project={c['GCP_PROJ_ID']} .

@echo on
CALL terraform init
CALL terraform apply -auto-approve
CALL gcloud builds submit --config cloudbuild.yaml --project={c['GCP_PROJ_ID']} .
IF %ERRORLEVEL% NEQ 0 (
    echo Use this command to see the Cloud Build Log:
    echo gcloud builds log BUILD_ID --project={c['GCP_PROJ_ID']}
    echo Use this command to see the Container Logs:
    echo gcloud run services logs read {c['GCP_RUN_JOB']} --region={c['GCP_REGION']} --limit=100
    pause
)

echo Waiting 30 more seconds...
timeout /t 30 /nobreak

:: Grant Cloud Run Invoker role so external users can access the Cloud Run service via the URL (must execute AFTER the Cloud Run service is created)
:: IMPORTANT: To only allow a Google API Gateway access, use:  --member="serviceAccount:YOUR-GATEWAY-SA@PROJECT_ID.iam.gserviceaccount.com"
CALL gcloud run services add-iam-policy-binding {c['GCP_RUN_JOB']} --member="allUsers" --role=roles/run.invoker --project={c['GCP_PROJ_ID']} --region={c['GCP_REGION']}
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORLEVEL: %ERRORLEVEL%:
    pause
)

:: Grant Storage Object Admin role for the bucket (must be done after the bucket is created)
CALL gcloud storage buckets add-iam-policy-binding gs://{c['GCP_GS_BUCKET']} --project={c['GCP_PROJ_ID']} --member=serviceAccount:{c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com --role=roles/storage.objectAdmin
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORLEVEL: %ERRORLEVEL%:
    pause
)

:: Show the Cloud Run logs
CALL gcloud run services logs read {c['GCP_RUN_JOB']} --region={c['GCP_REGION']} --project={c['GCP_PROJ_ID']}

echo.
echo Environment variables available to the app running in Cloud Run:
CALL gcloud run services describe {c['GCP_RUN_JOB']} --region={c['GCP_REGION']} --format="yaml(spec.template.spec.containers[0].env)"

:: Show the Cloud Run URL
echo.
echo Cloud Run URL:
CALL gcloud run services describe {c['GCP_RUN_JOB']} --project={c['GCP_PROJ_ID']} --region={c['GCP_REGION']} --format=\"value(status.url)\"

CALL cd gcp
echo.
echo Execute the following batch file to see useful commands:  gcp_show_commands.bat
echo.
''')

    print(f"\nDONE: Generated files for {c['GCP_PROJ_ID']}")
    print(f"Next steps:")
    print(f"Open a Windows command prompt / Terminal window and navigate to the folder /gcp")
    print(f"Run: gcp_bootstrap.bat")

    # Generate batch file to show commands with gcp_constants.txt already populated
    path_file_bootstrap = PATH_GCP.joinpath("gcp_show_commands.bat")
    with open(path_file_bootstrap, 'w') as f:
        f.write(f'''@echo off
echo.
echo GCP_PROJ_ID: {c['GCP_PROJ_ID']}
echo Cloud Run: {c['GCP_RUN_JOB']}
echo Region: {c['GCP_REGION']}
echo Project-Local Service Account: {c['GCP_SVC_ACT_PREFIX']}@{c['GCP_PROJ_ID']}.iam.gserviceaccount.com
echo GCP_BQ_DATASET_ID: {c['GCP_BQ_DATASET_ID']}
echo Cloud Storage Bucket: {c['GCP_GS_BUCKET']}

echo.
echo Cloud Run URL:
echo gcloud run services describe {c['GCP_RUN_JOB']} --project={c['GCP_PROJ_ID']} --region={c['GCP_REGION']} --format="value(status.url)"

echo.
echo Cloud Run Log:
echo gcloud run services logs read {c['GCP_RUN_JOB']} --project={c['GCP_PROJ_ID']} --region={c['GCP_REGION']} --limit 50

echo.
echo Cloud Storage Bucket Contents
echo gcloud storage ls gs://{c['GCP_GS_BUCKET']}

echo.
echo Show environment variables available to the Cloud Run app
echo gcloud run services describe {c['GCP_RUN_JOB']} --region={c['GCP_REGION']} --format="yaml(spec.template.spec.containers[0].env)"

echo.
echo How to copy file from /data to Storage Bucket
rem Get the project folder path
for %%I in ("%~dp0..") do set "PROJ_DIR=%%~fI"
SET DATA_DIR=%PROJ_DIR%\data
echo gcloud storage cp "%DATA_DIR%\README.txt" gs://%GCP_GS_BUCKET%
echo.
''')

    print(f"\nDONE: Generated files for {c['GCP_PROJ_ID']}")


if __name__ == "__main__":
    generate_files()
