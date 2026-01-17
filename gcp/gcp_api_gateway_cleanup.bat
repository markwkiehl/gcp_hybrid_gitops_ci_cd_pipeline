@echo off
cls
echo Starting API Gateway Cleanup
echo.


rem import the GCP project constants from file gcp_constants.txt
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)



echo All APIs
CALL gcloud api-gateway apis list
echo.

goto :skip0
rem --------------------------------------------------------
rem Uncomment out below to delete a specific gateway
set GCP_API_ID=my-cloudrun-api-v0-10
set GCP_CONFIG_ID=cloudrun-config-v0-10
set GCP_GATEWAY_ID=my-cloudrun-gateway-v0-10
rem --------------------------------------------------------
:skip0


echo.
echo This batch file will delete the API ID, API Config, API Gateway, and API Keys associated with: 
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
echo The GCP Project %GCP_PROJ_ID% will be unaffected.  Only the API Gateway will be deleted.
echo Press RETURN to continue, CTRL-C to abort.
pause



echo.
echo Delete the gateway %GCP_GATEWAY_ID% 
CALL gcloud api-gateway gateways delete %GCP_GATEWAY_ID% --location=%GCP_REGION% --project=%GCP_PROJ_ID% -q


echo.
echo Delete the API Config %GCP_CONFIG_ID%
CALL gcloud api-gateway api-configs delete %GCP_CONFIG_ID% --api=%GCP_API_ID% --quiet


echo.
echo Deleting the API %GCP_API_ID%
CALL gcloud api-gateway apis delete %GCP_API_ID% --quiet


echo.
echo Deleting ALL API Keys
@echo off
SETLOCAL EnableDelayedExpansion

REM --- Safety Check: Ensure the project ID is set ---
IF NOT DEFINED GCP_PROJ_ID (
    ECHO Error: GCP_PROJ_ID environment variable is not set.
    GOTO :EOF
)

ECHO Listing and deleting all API keys for project: %GCP_PROJ_ID%

REM --- Loop through all API Key UIDs and delete each one ---
FOR /F "delims=" %%A in ('gcloud services api-keys list --project=%GCP_PROJ_ID% --format="value(uid)"') DO (
    ECHO Deleting API Key UID: %%A    
    gcloud alpha services api-keys delete %%A --project=%GCP_PROJ_ID% --quiet    
    timeout /t 1 /nobreak >NUL
)

ECHO --- All listed API keys have been sent for deletion. ---
ENDLOCAL


echo.
echo ============================================
echo  ALL DONE
echo ============================================


echo.
echo APIs, Configs, Gateways


echo.
echo All APIs:
CALL gcloud api-gateway apis list


rem List API Configurations
echo.
echo API Configs:
CAll gcloud api-gateway api-configs list --format="table(name, api, createTime)"


rem Display all API Gateways
echo.
echo All API Gateways
rem CALL gcloud api-gateway gateways list --format="table(name,apiConfig)"
rem CALL gcloud api-gateway gateways list --format="table(name, apiConfig.basename())"
CALL gcloud api-gateway gateways list



rem List API Resources
echo.
echo API Resources:
CALL gcloud api-gateway apis list --format="table(name, state, createTime)"


rem list API Keys
rem gcloud services api-keys list --format="table(name.basename(), displayName, createTime, uid)"
rem gcloud services api-keys list --format="value(name)"
rem gcloud services api-keys list --format="table(name.basename(), displayName, uid)"
echo.
echo API Keys for project %GCP_PROJ_ID%:
CALL gcloud services api-keys list --project=%GCP_PROJ_ID% --format="table(name.basename(),displayName,createTime)"

ENDLOCAL
EXIT /B 0

