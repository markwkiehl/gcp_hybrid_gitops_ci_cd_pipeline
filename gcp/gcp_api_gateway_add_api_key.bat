@echo off
cls

rem ---------------------------------------------------------------------
rem --- IMPORT CONSTANTS ---
rem ---------------------------------------------------------------------
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)

rem --- DEFINE NEW KEY NAME ---
rem Assign the first command line argument passed to this batch file as the new API Key Display Name
IF "%1"=="" (
    ECHO ERROR: An argument for the new API Gateway API Key was not provided as an argument.
    EXIT /B
)

SET GCP_API_KEY_DISPLAY_NAME_NEW=%1%
SET API_KEY_NAME=


echo Generate new API Gateway API Key for:
echo.
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_API_ID: %GCP_API_ID%
echo GCP_CONFIG_ID: %GCP_CONFIG_ID%
echo GCP_GATEWAY_ID: %GCP_GATEWAY_ID%
echo GCP_API_KEY_DISPLAY_NAME (original): %GCP_API_KEY_DISPLAY_NAME%
echo NOTE: The default limit is 50 API Keys per Google Cloud project (can be increased by request).
echo.
echo Existing API Gateway Keys:
CALL gcloud services api-keys list --project=%GCP_PROJ_ID% --format="table(name.basename(),displayName,createTime)"
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%: 
	EXIT /B
)
echo.
echo The NEW API Key Display Name (GCP_API_KEY_DISPLAY_NAME_NEW): %GCP_API_KEY_DISPLAY_NAME_NEW%

echo.
echo Press ENTER to continue, CTRL-C to abort.
pause

echo.
echo --- Creating new API Key: %GCP_API_KEY_DISPLAY_NAME_NEW% ---
CALL gcloud services api-keys create --display-name="%GCP_API_KEY_DISPLAY_NAME_NEW%" --project=%GCP_PROJ_ID%
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%: 
	EXIT /B
)


rem --- CAPTURE NEW KEY DETAILS ---
echo.
echo --- Capturing Internal Key Name and Key String ---

rem ** FIX: Enable Delayed Expansion to ensure variables set inside loops are visible outside. **
SETLOCAL ENABLEDELAYEDEXPANSION

rem Capture the internal Key Name (full resource path)
rem Capture the internal Key Name (full resource path)
FOR /F "tokens=*" %%i IN ('gcloud services api-keys list --filter="displayName:!GCP_API_KEY_DISPLAY_NAME_NEW!" --format="value(name)"') DO (
    SET "API_KEY_NAME=%%i"
)
echo Internal API Key Name: %API_KEY_NAME%


rem Use the internal Key Name to retrieve the actual Key String
FOR /F "tokens=*" %%i IN ('gcloud alpha services api-keys get-key-string %API_KEY_NAME% --format="value(keyString)"') DO (
    SET NEW_API_KEY_STRING=%%i
)
echo New API Key String: %NEW_API_KEY_STRING%



rem ------------------------------------------------------------------------------------------------------
rem --- APPLY SERVICE RESTRICTION (Using the working gcloud CLI command) ---
rem ------------------------------------------------------------------------------------------------------
echo.
echo --- Patching API Key Restrictions ---

rem Get the Managed Service Name (GCP_ENDPOINT_SERVICE_NAME) from the API Config Output.
for /f "delims=" %%A in ('gcloud endpoints services list --sort-by=NAME') do (
    set GCP_ENDPOINT_SERVICE_NAME=%%A
)
echo Endpoint Service Name (GCP_ENDPOINT_SERVICE_NAME): %GCP_ENDPOINT_SERVICE_NAME%

rem Use the captured internal key name (%API_KEY_NAME%) for the update command.
CALL gcloud services api-keys update %API_KEY_NAME% --api-target="service=%GCP_ENDPOINT_SERVICE_NAME%" --location=%GCP_REGION%
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%: 
	EXIT /B
)
echo.
echo API Key restriction applied via gcloud CLI (Check the output above for confirmation).
echo.


rem ------------------------------------------------------------------------------------------------------
rem --- MANDATORY WAIT FOR PROPAGATION (5 minutes) ---
rem ------------------------------------------------------------------------------------------------------
echo.
echo Waiting 30 seconds for API Key Restriction to propagate..
timeout /t 30 /nobreak


echo.
echo ==============================================================================
echo.  New API Key String (use this in your client): %NEW_API_KEY_STRING%
echo ==============================================================================


echo.
echo This batch file %~n0%~x0 has ended normally (no errors).  
echo You can repeat running this batch file again if needed.
echo.
echo When you are finished with the project, execute the batch file "gcp_api_gateway_cleanup.bat".
