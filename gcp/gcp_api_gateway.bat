@echo off
cls
echo Starting API Gateway Configuration
echo.

rem ==============================================================================
rem API GATEWAY DEPLOYMENT SCRIPT (test1.bat)
rem ==============================================================================
rem
rem PURPOSE: This script automates the full deployment of a Google Cloud API Gateway
rem          to secure a pre-deployed Cloud Run service using a restricted API Key.
rem
rem FLOW OF EXECUTION:
rem
rem 1. SETUP:
rem    - Imports all project constants (IDs, Names, Region) from gcp_constants.txt.
rem    - Calculates the Google-managed API Gateway Service Agent (SA) name.
rem
rem 2. ENABLE APIs:
rem    - Ensures all necessary GCP APIs (API Gateway, Service Management, Cloud Run) are enabled.
rem
rem 3. CREATE API RESOURCES:
rem    - Creates the top-level API resource (%GCP_API_ID%).
rem    - Creates the API Configuration (%GCP_CONFIG_ID%) from the OpenAPI YAML file.
rem      (This step automatically creates the required GCP Managed Service).
rem
rem 4. CRITICAL SECURITY STEPS (Permissions & Service Activation):
rem    - CRITICAL FIX 1 (IAM BINDING): Grants the API Gateway Service Agent the
rem      'roles/run.invoker' permission to ensure it can successfully call the Cloud Run backend.
rem    - NEW CRITICAL FIX (SERVICE ENABLEMENT): Explicitly runs 'gcloud services enable %GCP_ENDPOINT_SERVICE_NAME%'
rem      to ensure the Google Managed Service is fully registered. This is mandatory for API Key
rem      validation to work and prevents 403 errors.
rem
rem 5. GATEWAY DEPLOYMENT:
rem    - Creates and deploys the API Gateway (%GCP_GATEWAY_ID%) using the configuration.
rem      This makes the API accessible via a public URL (%GATEWAY_HOST%).
rem
rem 6. API KEY MANAGEMENT & RESTRICTION:
rem    - Creates a new API Key (%GCP_API_KEY_DISPLAY_NAME%).
rem    - Restricts the API Key using the REST API (curl/PowerShell) to ONLY be valid
rem      for the newly enabled Google Managed Service.
rem
rem 7. FINALIZATION:
rem    - Displays the final Gateway Host URL and the API Key String for use in client scripts.
rem
rem ==============================================================================


rem import the GCP project constants from file gcp_constants.txt
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)

echo.
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_REGION: %GCP_REGION%
echo GCP_RUN_JOB: %GCP_RUN_JOB%
echo GCP_API_KEY_DISPLAY_NAME: %GCP_API_KEY_DISPLAY_NAME%
echo GCP_API_ID: %GCP_API_ID%
echo GCP_CONFIG_ID: %GCP_CONFIG_ID%
echo GCP_GATEWAY_ID: %GCP_GATEWAY_ID%


set GCP_SVC_ACT=%GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com
echo Service Account (GCP_SVC_ACT): %GCP_SVC_ACT%

REM Get the GCP Project Number for the GCP Project ID.
rem The Project Number %GCP_PROJ_NO% is used for the Google-managed Service Account.
for /f "delims=" %%A in ('gcloud projects describe %GCP_PROJ_ID% --format="value(projectNumber)"') do (
    set GCP_PROJ_NO=%%A
)
echo Project Number (GCP_PROJ_NO): %GCP_PROJ_NO%

set API_GATEWAY_SA=service-%GCP_PROJ_NO%@gcp-sa-apigateway.iam.gserviceaccount.com
echo API Gateway SA (API_GATEWAY_SA): %API_GATEWAY_SA%



echo.
pause

rem --- ENABLE REQUIRED APIs ---
echo. --- Enabling Required APIs ---
call gcloud services enable apigateway.googleapis.com --project=%GCP_PROJ_ID%
call gcloud services enable servicemanagement.googleapis.com --project=%GCP_PROJ_ID%
call gcloud services enable servicecontrol.googleapis.com --project=%GCP_PROJ_ID%
call gcloud services enable apikeys.googleapis.com --project=%GCP_PROJ_ID%
echo.

rem --- CREATE API AND CONFIGURATION ---
echo. --- Creating API and API Configuration ---
rem Create the API resource
call gcloud api-gateway apis create %GCP_API_ID%


rem --- EDIT OpenAPI spec (openapi2-cloudrun.yaml) ---
echo.
echo. --- EDIT OpenAPI spec (openapi2-cloudrun.yaml) ---
echo Edit the file "openapi2-cloudrun.yaml" and update "address" and "jwt_audience" with the following:
rem gcloud run services describe mcp-fastapi --region=us-east4 --format="value(status.url)"
CALL gcloud run services describe %GCP_RUN_JOB% --region=%GCP_REGION% --format="value(status.url)"
echo .. and update the "host" at the top of the file with the following (changes with each execution of this script):
rem gcloud api-gateway apis describe my-cloudrun-api-v2-0 --project=mcp-fastapi-v0-3 --format="value(managedService)"
CALL gcloud api-gateway apis describe %GCP_API_ID% --project=%GCP_PROJ_ID% --format="value(managedService)"
rem NOTE: "host" in the file "openapi2-cloudrun.yaml" is the Managed Service Name (or Service Endpoint Name) registered in the Google Service Management API.
pause


rem --- Upload the OpenAPI spec and create the API Config ---
echo.
echo --- Upload the OpenAPI spec and create the API Config ---
CALL gcloud api-gateway api-configs create %GCP_CONFIG_ID% --api=%GCP_API_ID% --openapi-spec=openapi2-cloudrun.yaml --backend-auth-service-account=%GCP_SVC_ACT%
echo.

rem --- GRANT CLOUD RUN INVOKER ROLE ---
echo. --- Granting Cloud Run Invoker Role to Service Account ---
CALL gcloud run services add-iam-policy-binding %GCP_RUN_JOB% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/run.invoker" --region=%GCP_REGION%
echo.

rem --- DEPLOY THE API GATEWAY ---
echo --- Deploying API Gateway ---
CALL gcloud api-gateway gateways create %GCP_GATEWAY_ID% --api=%GCP_API_ID% --api-config=%GCP_CONFIG_ID% --location=%GCP_REGION%
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR %ERRORLEVEL%
    EXIT /B
)

rem --- Get the Gateway Hostname URL ---
rem Capture the Gateway Hostname URL for Python client script
echo.
echo --- Get the Gateway Hostname URL ---
FOR /F "tokens=*" %%i IN ('gcloud api-gateway gateways describe %GCP_GATEWAY_ID% --location=%GCP_REGION% --format="value(defaultHostname)"') DO (
    SET GATEWAY_HOST=%%i
)
echo GATEWAY_HOST URL: %GATEWAY_HOST%
echo.

rem --- Get the Endpoint Service Name ---
echo.
echo --- Endpoint Service Name ---
rem The output from below will show the endpoint service name of my-cloudrun-api-v0-4-25gk8k7u1uiw7.apigateway.mcp-fastapi-v0-3.cloud.goog
CALL gcloud endpoints services list --sort-by=NAME
rem Get the Managed Service Name (GCP_ENDPOINT_SERVICE_NAME) from the API Config Output.
for /f "delims=" %%A in ('gcloud endpoints services list --sort-by=NAME') do (
    set GCP_ENDPOINT_SERVICE_NAME=%%A
)
echo Endpoint Service Name (GCP_ENDPOINT_SERVICE_NAME): %GCP_ENDPOINT_SERVICE_NAME%
rem my-cloudrun-api-v0-4-25gk8k7u1uiw7.apigateway.mcp-fastapi-v0-3.cloud.goog


rem --- IAM ROLE BINDING of GCP_ENDPOINT_SERVICE_NAME to API Gateway
rem (Fixes "Service account does not exist" and initial 403 errors) 
echo. --- Granting servicemanagement.admin to API Gateway SA ---
CALL gcloud endpoints services add-iam-policy-binding %GCP_ENDPOINT_SERVICE_NAME% --member="serviceAccount:%API_GATEWAY_SA%" --role="roles/servicemanagement.admin"
echo.



rem =======================================================================================
rem LAST REVISION:  ENABLE MANAGED SERVICE (Fixes the Python script 403 error) ---
rem ----------------------------------------------------------------------------------
echo. --- Enabling the Managed API Service: %GCP_ENDPOINT_SERVICE_NAME% ---
@echo on
CALL gcloud services enable %GCP_ENDPOINT_SERVICE_NAME%
@echo off
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR %ERRORLEVEL%
    EXIT /B
)
rem =======================================================================================



rem --- 7. CREATE AND GET API KEY ---
echo. --- Creating API Key (Key string will be displayed) ---
rem The output of 'gcloud alpha services api-keys create' is verbose JSON.
rem We use CALL and @echo off immediately after to prevent batch parser issues.
CALL gcloud alpha services api-keys create --display-name="%GCP_API_KEY_DISPLAY_NAME%"
@echo off
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR %ERRORLEVEL%: Failed to create API key.
    EXIT /B
)

rem CRITICAL: Add a short delay. Even after creation is complete, there is a short 
rem period before the key is available to 'gcloud services api-keys list'.
echo.
echo Waiting 30 seconds for new API Key record to propagate...
timeout /t 30 /nobreak
echo.

rem ------------------------------------------------------------------------------------------------------
rem --- CAPTURE API KEY STRING (The actual value for the client script) ----------------------------------
rem ------------------------------------------------------------------------------------------------------
echo. --- Fetching API Key String for Client Script ---

rem Capture the internal Key Name (required for the next step)
FOR /F "tokens=*" %%i IN ('gcloud services api-keys list --filter="displayName:%GCP_API_KEY_DISPLAY_NAME%" --format="value(name)"') DO (
    SET API_KEY_NAME=%%i
)
echo Internal API Key Name: %API_KEY_NAME%

rem Use the internal Key Name to retrieve the actual Key String
FOR /F "tokens=*" %%i IN ('gcloud alpha services api-keys get-key-string %API_KEY_NAME% --format="value(keyString)"') DO (
    SET API_KEY_STRING=%%i
)
echo.
echo ==============================================================================
echo.  API Key String: %API_KEY_STRING%
echo ==============================================================================


rem ------------------------------------------------------------------------------------------------------
rem --- API KEY SERVICE RESTRICTION (Fixes "API is not enabled for the project" 403) ---
rem Use simple GCLOUD command + mandatory 5-minute propagation delay. 
rem PowerShell efforts did NOT work.  Must use gcloud CLI command. 
rem ------------------------------------------------------------------------------------------------------
echo. --- Patching API Key Restrictions ---

rem The official gcloud command is simpler and less prone to quoting errors.
rem The previous failures were almost certainly due to not allowing enough propagation time.
rem DOES NOT WORK: CALL gcloud services api-keys update %GCP_API_KEY_DISPLAY_NAME% --api-target="service=%GCP_ENDPOINT_SERVICE_NAME%"
@echo on
CALL gcloud services api-keys update %API_KEY_NAME% --api-target="service=%GCP_ENDPOINT_SERVICE_NAME%"
@echo off
echo.
echo API Key restriction applied via REST API (Check the output above for confirmation).
echo.


rem --- ADD MANDATORY WAIT FOR API KEY RESTRICTION PROPAGATION (5 minutes) ---
echo.
echo Waiting 30 seconds for API Key Restriction to propagate.
timeout /t 30 /nobreak
echo 30 second timeout expired.
echo NOTE: if an error occurs, wait 5 minutes and then try again. 
echo.


rem Generate Summary
rem IMPORTANT:  Each API Gateway points to exactly one API config, and that config belongs to one API.
echo.
echo. --- API Gateway Deployment and Configuration Complete ---
echo.
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_REGION: %GCP_REGION%
echo NOTE:	The API resource is the top-level, logical entity.
echo 		Each API Gateway points to exactly one API config, and that config belongs to one API.
echo 		BUT: a single API can have multiple API Configs
echo GCP_API_ID: %GCP_API_ID%
echo   GCP_CONFIG_ID: %GCP_CONFIG_ID%
echo     GCP_GATEWAY_ID: %GCP_GATEWAY_ID%
echo.
echo API_GATEWAY_SA: %API_GATEWAY_SA%
echo GCP_ENDPOINT_SERVICE_NAME: %GCP_ENDPOINT_SERVICE_NAME%


rem --- 9. DISPLAY FINAL HOST URL & API KEY STRING ---
echo.
echo Update your Python client script with:
echo   GATEWAY_HOST: %GATEWAY_HOST%
echo   API_KEY: %API_KEY_STRING%
echo.
pause


echo.
echo DIAGNOSTIC COMMANDS :
CALL gcloud services list --filter="name:(servicecontrol.googleapis.com OR servicemanagement.googleapis.com)" --project=%GCP_PROJ_ID%
CALL gcloud api-gateway gateways describe %GCP_GATEWAY_ID% --location=%GCP_REGION% --format="value(state)"
rem If the next command is NULL, then the Google Service Management API failed to ingest or register the security policies (API Key restriction) defined in your openapi2-cloudrun.yaml file, even though the Gateway itself is ACTIVE.
rem CALL gcloud endpoints services describe %GCP_ENDPOINT_SERVICE_NAME% --format="yaml(control, apikeys)"
CALL gcloud endpoints services describe %GCP_ENDPOINT_SERVICE_NAME% --format="yaml"
CALL gcloud api-gateway api-configs describe %GCP_CONFIG_ID% --api=%GCP_API_ID% --project=%GCP_PROJ_ID% --format="value(state)"

echo.
echo Do NOT repeat running this batch file without editing the file gcp_constants.txt first.
echo You can generate additional API Keys by running gcp_api_gateway_add_api_key.bat
echo.
echo When you are finished with the project, execute the batch file "gcp_api_gateway_cleanup" to delete everything created for the API Gateway.


EXIT /B 0
