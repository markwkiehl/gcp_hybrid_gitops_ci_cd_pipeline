@echo off
echo Bootstrapping Project: ci-cd-pipeline-v0-8

rem --- VERSION CHECK ---
CALL gcloud projects describe ci-cd-pipeline-v0-8 >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo WARNING: Project ci-cd-pipeline-v0-8 already exists!
    pause
)

:: Make sure the .env file exists
if NOT EXIST "D:\Documents\computer\Python\projects\hybrid_gitops_ci_cd_pipeline\src\.env" (
  echo ERROR: File not found "D:\Documents\computer\Python\projects\hybrid_gitops_ci_cd_pipeline\src\.env"
  EXIT /B
)

:: Update local gcloud components (if needed).
CALL gcloud components update --quiet

:: Only need to do the following once per project.
if NOT EXIST "D:\Documents\computer\Python\projects\hybrid_gitops_ci_cd_pipeline\gcp\gcp_bootstrap.bat" (
  :: Sets the identity for gcloud commands.
  CALL gcloud auth login

  :: Sets the identity for Terraform to use.  (user-based ADC)
  CALL gcloud auth application-default login
)

:: PROJECT CREATION
CALL gcloud projects create ci-cd-pipeline-v0-8

:: IDENTITY SETUP
:: Note: 'gcloud auth login' is for the CLI. 
:: '--update-adc' does both (CLI and Terraform) in one window.
CALL gcloud auth login --update-adc

:: BILLING & CONFIG
:: Link the new project to your billing account
CALL gcloud billing projects link ci-cd-pipeline-v0-8 --billing-account=014A74-1E1E07-BF009D
:: Set the local CLI to point to the new project
echo Setting local CLI context and quota project...
CALL gcloud config set project ci-cd-pipeline-v0-8

:: ADC QUOTA (Crucial for Terraform)
:: Tell Google which project to bill for Terraform's API calls.
CALL gcloud auth application-default set-quota-project ci-cd-pipeline-v0-8


echo Enabling Services...
:: iam.googleapis.com 
:: iamcredentials.googleapis.com 
:: cloudresourcemanager.googleapis.com 
:: cloudbuild.googleapis.com 
:: run.googleapis.com 
:: artifactregistry.googleapis.com 
:: storage.googleapis.com
:: apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com
CALL gcloud services enable iam.googleapis.com iamcredentials.googleapis.com cloudresourcemanager.googleapis.com cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com --project=ci-cd-pipeline-v0-8
CALL gcloud services enable bigquery.googleapis.com --project=ci-cd-pipeline-v0-8

rem API Gateway
call gcloud services enable apigateway.googleapis.com --project=ci-cd-pipeline-v0-8
call gcloud services enable servicemanagement.googleapis.com --project=ci-cd-pipeline-v0-8
call gcloud services enable servicecontrol.googleapis.com --project=ci-cd-pipeline-v0-8
call gcloud services enable apikeys.googleapis.com --project=ci-cd-pipeline-v0-8

rem Project Service Account
rem %GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com
rem svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com

:: Create the Service Account
echo Creating Project-Local Service Account svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com ..
CALL gcloud iam service-accounts create svc-act-ci-cd-pipeline --project=ci-cd-pipeline-v0-8

echo.
echo Waiting 60 seconds for API and IAM propagation...
timeout /t 60 /nobreak

echo Granting Permissions to Service Account...
@echo on

:: Grant Storage Admin (derived from your discovery)
CALL gcloud projects add-iam-policy-binding ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/storage.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Service Account User role to the service account:
CALL gcloud projects add-iam-policy-binding ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant BigQuery Admin (integrated from gcp_bigquery.bat logic)
CALL gcloud projects add-iam-policy-binding ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/bigquery.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Storage Admin role to the service account:
CALL gcloud projects add-iam-policy-binding ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/storage.admin
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

:: Grant Cloud Run Developer role to the service account:
CALL gcloud projects add-iam-policy-binding ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/run.developer
IF %ERRORLEVEL% NEQ 0 (
    echo %ERRORLEVEL%
    EXIT /B
)

@echo off

echo Creating Artifact Registry...
CALL gcloud artifacts repositories create repo-ci-cd-pipeline --repository-format=docker --location=us-east4 --project=ci-cd-pipeline-v0-8
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
echo - Run: gcloud builds submit --config cloudbuild.yaml --project=ci-cd-pipeline-v0-8 .

@echo on
CALL terraform init
CALL terraform apply -auto-approve
CALL gcloud builds submit --config cloudbuild.yaml --project=ci-cd-pipeline-v0-8 .

echo Waiting 30 more seconds...
timeout /t 30 /nobreak

:: Grant Cloud Run Invoker role so external users can access the Cloud Run service via the URL (must execute AFTER the Cloud Run service is created)
:: IMPORTANT: To only allow a Google API Gateway access, use:  --member="serviceAccount:YOUR-GATEWAY-SA@PROJECT_ID.iam.gserviceaccount.com"
CALL gcloud run services add-iam-policy-binding ci-cd-pipeline --member="allUsers" --role=roles/run.invoker --project=ci-cd-pipeline-v0-8 --region=us-east4

:: Grant Storage Object Admin role for the bucket (must be done after the bucket is created)
CALL gcloud storage buckets add-iam-policy-binding gs://ci-cd-pipeline-v0-8 --project=ci-cd-pipeline-v0-8 --member=serviceAccount:svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com --role=roles/storage.objectAdmin

pause
:: Show the Cloud Run logs
CALL gcloud run services logs read ci-cd-pipeline --region=us-east4 --project=ci-cd-pipeline-v0-8

echo.
echo Environment variables available to the app running in Cloud Run:
CALL gcloud run services describe ci-cd-pipeline --region=us-east4 --format="yaml(spec.template.spec.containers[0].env)"

:: Show the Cloud Run URL
echo.
echo Cloud Run URL:
CALL gcloud run services describe ci-cd-pipeline --project=ci-cd-pipeline-v0-8 --region=us-east4 --format="value(status.url)"

CALL cd gcp
echo.
echo Execute the following batch file to see useful commands:  gcp_show_commands.bat
echo.
