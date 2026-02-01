# Hybrid GitOps CI / CD Pipeline

## Description

A "State-Based Logic" (Terraform) and "Event-Driven Logic" (Cloud Build) approach to a Continuous Integration/Continuous Deployment (CI/CD) pipeline. 
Creation, configuration, and deployment of an app is governed by versioned scripts that automatically provide traceable documentation and insure reproducibility.
Designed to be run in **Windows OS**.

### Project Architecture & Directory Structure
The project structure shown below separates the Python source code (/src) from the Python virtual environment (.venv).
The contents below is what exists after a project has been built and deployed. 

C:\Documents\..\projects\py_project\
│   README.md					← Information about the project.
│   requirements.txt        	← Created by "gcp_generator.py" for container build. 
│   Dockerfile					← Created by "gcp_generator.py"
│   .dockerignore
│   .gcloudignore				← Critical for managing the size of the upload to Google Cloud (.dockerignore is not enough).
│   cloudbuild.yaml         	← YAML file used by the command: gcloud builds submit --config cloudbuild.yaml
│   main.tf                 	← Terraform file.
│   terraform.tfstate			← Terraform will create this "state" file.
│
├── .venv\                  	← Python virtual environment | py -3 -m venv .venv  | .\.venv\Scripts\activate
│   ├── Scripts\python.exe
│   ├── Lib\
│   └── ...
│
└── src\						← Python source code folder.
    └── mcp_fastapi_server.py	← Python script to deploy to Google Cloud Run (filename may change).
    └── mcp_fastapi_client.py		← Python client script that tests access to the Model Context Protocol (MCP) Server (mcp_fastapi_server.py).
    └── .env					← File must exist, but can be empty. Any API Keys will be injected into the container as environment variables.
│
└── data\						← Read-only static data files available in the container to the app when deployed.
│
└── gcp\						← Setup, configuration, and deployment related files. 
    └── gcp_constants.txt		← Names for the various Google Cloud items to create and configure (user, project, billing, region, etc.)
    └── pip_install.txt			← Python libraries to "pip install" by the batch file "make_py_venv.bat".
    └── make_py_venv.bat		← Batch file to create a Python virtual environment with the libraries installed from the list in "pip_install.txt".
    └── gcp_generator.py		← Python script that reads the constants from "gcp_constants.txt" and writes "main.tf", "cloudbuild.yaml", "gcp_bootstrap.bat", and "requirements.txt".
    └── gcp_bootstrap.bat		← Batch file that creates the Google project, enables APIs, and sets the permissions.
    └── gcp_cleanup.bat			← Batch file to delete the Google Cloud project and all associated resources. 
    └── README.md				← This file.

The project root folder contains the primary deployment files: main.tf (Terraform), cloudbuild.yaml (Cloud Build), Dockerfile, .dockerignore, and requirements.txt.
All batch files are expected to run in a Windows OS command prompt / Terminal window. 

### The Python Generator Script (gcp_generator.py)
This script's core functions include:
- Valdiates GCP resource name / character restrictions from "gcp_constants.txt" .
- Dynamically generates main.tf, cloudbuild.yaml, gcp_bootstrap.bat, and Dockerfile based on versioned constants from "gcp_constants.txt".
- Any contents of the /src/.env file are injected into the cloudbuild.yaml file and created as environment variables for the deployed Python script.  
- Reads the manually constructed gcp/pip_install.txt and writes it to the root as requirements.txt to satisfy Docker's build context.
- **IMPORTANT: Re-run this script everytime you make a change to the Python script deployed to insure the latest version is deployed.***

### The Deployment Pipeline (cloudbuild.yaml)
The cloudbuild.yaml file is updated with values from gcp_constants.txt when the Python script `gcp_generator.py` is run. 

This single specification file handles the Docker build on Google's high-speed servers and deploys to Cloud Run in one go.
- Secrets from the /src/.env file are injected directly into environment variables during deployment.
- Startup Probe: We will configure the Cloud Run deployment to use a startup probe that waits for your GCS FUSE mount at your specified path /mnt/storage.
- Note that Google Cloud Build provides a built-in variable called ${PROJECT_ID} automatically.

### Automated Bootstrapping (gcp_bootstrap.bat)
A version-specific batch file that automates the Google Cloud Platform setup:
- Project Creation & Billing: Creates the GCP project and links it to the billing account.
- Creates the Project-Local Service Account. 
- Enables Cloud Build, Run, Artifact Registry, Storage, BigQuery, and other APIs.
- Configures both the local gcloud CLI and Google Cloud to the new project. This includes the Application Default Credentials (ADC). 
- Grants required permissions / roles to the Project-Local Service Account (%GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com) created for this project (only).
- Executes the Terraform commands to configure Google Cloud resources:  `terrafrom init`, `terraform apply`.
- Executes the Cloud Build `gcloud builds submit --config cloudbuild.yaml --project=%GCP_PROJ_ID% .`.
- Displays the Cloud Run log file. 
- Displays the environment variables (API Keys, etc.) available to the script running in Cloud Run. 
- Fetches the Cloud Run URL and displays it. 

### Containerization Logic (Dockerfile)
- Sets /app as the working directory and copies requirements.txt, /data, and /src.
- Optimization: Sets environment variables to disable pip caching and enable unbuffered logging for real-time monitoring in Cloud Build

### Infrastructure as Code (IaC) (main.tf)
Terraform translates the configuration defined in the main.tf file into actual Google Cloud resources. 
main.tf will be updated with values from gcp_constants.txt when the Python script `gcp_generator.py` is run. 

- State Management: It creates a terraform.tfstate file in the project root to keep track of exactly what it has built, so it doesn't try to recreate resources that already exist.
- Idempotency: `terraform apply` causes only the local changes to Google Cloud Resources to be updated in the Google Cloud Build. 
- Lifecycle Control: Terraform is configured to "force destroy" resources like buckets and datasets, which is essential for iterative development (v0-0 to v0-1).

[!ABOUT]
Terraform is an open-source Infrastructure as Code (IaC) tool that lets you define, provision, and manage cloud and on-premises resources (like virtual machines, networks, storage) using a declarative configuration language (HCL). It allows for consistent, automated, and version-controlled management of infrastructure across multiple providers (AWS, Azure, GCP) with a single workflow, reducing manual setup and preventing vendor lock-in. 

### Google Cloud Service Accounts
Two service accounts are created specifically for the project:
- Cloud Build Service Account: Automatically created by Cloud Build during the build.  [PROJECT_NUMBER]@cloudbuild.gserviceaccount.com
- Project-Local Service Account: Created to support the run time needs of the application. When Cloud Run starts the container, it "assumes the identity" of this account. %GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com

## Workflow

### Project Folder

- Open up a Windows command prompt / terminal window.
- Navigate to the parent folder that holds your Python projects ('projects' in the diagram below).
- Execute `git clone https://github.com/markwkiehl/gcp_hybrid_gitops_ci_cd_pipeline.git py_project` where "py_project" is the folder name for your new Python project.
- The folder contents and structure should look like what you see below. 

D:\Documents\..\projects\py_project\
│   README.md						← Information about the project.
│   .dockerignore
│   .gcloudignore					← Critical for managing the size of the upload to Google Cloud (.dockerignore is not enough).
│
└── src\							← Python source code folder.
    └── mcp_fastapi_server.py		← The Python script to deploy to Google Cloud Run. MUST specify in gcp_constant.txt under PYTHON_FILENAME.
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

### Create Python Virtual Environment
Edit the file `/gcp/pip_install.txt` with all anticipated "pip install" requirements.
 
From Windows command prompt and the /gcp folder, run make_py_venv.bat:
```
cd gcp
make_py_venv
```

### Edit gcp/gcp_constants.txt
Edit the file gcp_constants.txt to provide the Google Cloud billing account, define the primary Google Cloud user, and uniquely name all of the Google Cloud resources.
- Make sure that 'PYTHON_FILENAME' references the Python file you intend to deploy to Cloud Run.
- I typically create a short length prefix/suffix like "ci-cd-pipeline" and use that for: GCP_SVC_ACT_PREFIX, GCP_PROJ_ID, GCP_IMAGE, GCP_REPOSITORY, GCP_RUN_JOB, GCP_RUN_JOB_VOL_NAME, GCP_GS_BUCKET, GCP_BQ_DATASET_ID, GCP_API_ID
- Be very careful of the use of underscore _ and dash -.  Only apply them where permitted (checked by gcp_generator.py). 
- You do not need to edit the following unless you plan to deply an API Gateway:  GCP_API_KEY_DISPLAY_NAME, GCP_API_ID, GCP_CONFIG_ID, GCP_GATEWAY_ID

### Python gcp_generator.py
Execute the Python script `gcp_generator.py` located in the /gcp folder.

### Bootstrap (gcp_bootstrap.bat)
Run `gcp_bootstrap.bat` from the /gcp folder in a Windows command prompt window.  

After it triggers your Google Cloud infastructure build and deployment in Cloud Build, it will:
- Display the Cloud Run startup logs so you can verify the /mnt/storage and startup_probe.txt are working:
- Display the environment variables available to the script running in Cloud Run
- Display the Cloud Run URL. 

Your Model Context Protocol (MCP) Server is now deployed to Google Cloud Run as a service. 

### MCP Client Script (mcp_fastapi_client.py)
Update the "BASE_URL" variable in the script "mcp_fastapi_client.py" and run it. It will connect to the MCP Server you deployed to Cloud Run and execute several tests. 

### gcloud CLI Commands (gcp_show_commands.bat)
Execute the file `gcp_show_commands.bat` to see a list of helpful gcloud CLI commands populated with the project constants from `gcp_constants.txt`.

### Project Cleanup (gcp_cleanup.bat)
Execute `gcp_cleanup.bat` to delete the Google Project and all resources, and to clear any Terraform "state" files used locally.
```
gcp_cleanup
```

### Optional Google Cloud Resources
Thge following batch files make it easy to add more resources to your project:
- Configure BigQuery with `gcp_bigquery.bat`, and remove it with `gcp_bigquery_cleanup.bat`.
- Configure Firestore with `gcp_firestore.bat`, and remove it with `gcp_firestore_cleanup.bat`.
- Implement a Google API Gateway with `gcp_api_gateway.bat`, add API Keys with `gcp_api_gateway_add_api_key.bat`, and remove it with `gcp_api_gateway_cleanup.bat`.

## Cost
The Terraform CLI tool free to use for up to 500 resources for individuals and companies to manage their own infrastructure, BUT you cannot use Terraform to build a commercial product that competes with HashiCorp.
As of January 2026 the [Google free tier limits](https://cloud.google.com/free/docs/free-cloud-features#free-tier-usage-limits) are:
- Cloud Build has a Free Tier that consists of 2,500 build-minutes per month for free (on the default e2-standard-2 machine).
- Artifact Registry: 0.5 GB storage per month
- Cloud Storage: 5 GB-months of regional storage (US regions only) per month
- Cloud Run: 2 million requests per month; 360,000 GB-seconds of memory, 180,000 vCPU-seconds of compute time; 1 GB of outbound data transfer from North America per month. No charge for data transfer to Google Cloud resources in the same region.

## Installation
One time installation for a new Windows OS environment.

### Git
- Open [https://git-scm.com/](https://git-scm.com/) in a browser and download.
- When the download finishes, double-click the file (it will be named something like Git-2.xx.x-64-bit.exe)
- If Windows asks “Do you want to allow this app to make changes?” → click Yes
- Click through the installer options (choose the defaults).
- Confirm Git is installed correctly by opening up a Windows command prompt / Terminal window and executing: `git --version`.

### Google 
See the sections "Google Cloud", "Google Cloud CLI & SDK", and "Google Cloud Billing" in the following public article:
[Configure Windows for Python, Docker, & GCP](https://medium.com/@markwkiehl/configure-windows-for-python-docker-gcp-071d196fcbbd)

### Terraform
- Open a browser to [https://developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install).
- Download the Terraform Windows AMD64 Zip (64-bit Windows), extract terraform.exe, and place it in the folder C:\Program Files\terraform
- Make sure the Windows system PATH includes that folder.  Start > System > Advanced system settings > Environment Variables, select Path under System or User variables, click Edit, then New.
- From a Windows command prompt / Terminal, test it with:  `terraform -version`



