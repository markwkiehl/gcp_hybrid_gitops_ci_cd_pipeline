@echo off
cls

REM Version 0.0.3
REM
REM v0.0.0	Initial release
REM v0.0.1	Added option to take numerical argument that specifies the number of additional API keys to generate.
REM v0.0.2	Refactored to loop based on numeric argument and use existing display name.
REM v0.0.3	Fixed delayed expansion subshell issues and added key listing at the end.

rem ---------------------------------------------------------------------
rem --- IMPORT CONSTANTS ---
rem ---------------------------------------------------------------------
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)

rem --- DEFINE NUMBER OF KEYS TO CREATE ---
IF "%1"=="" (
    ECHO ERROR: Please provide the number of API Keys to generate as an argument.
    EXIT /B
)
SET NUM_KEYS=%1
SETLOCAL ENABLEDELAYEDEXPANSION

echo Generate new API Gateway API Keys for:
echo.
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_API_ID: %GCP_API_ID%
echo GCP_CONFIG_ID: %GCP_CONFIG_ID%
echo GCP_GATEWAY_ID: %GCP_GATEWAY_ID%
echo GCP_API_KEY_DISPLAY_NAME: %GCP_API_KEY_DISPLAY_NAME%
echo NOTE: The default limit is 50 API Keys per Google Cloud project (can be increased by request).
echo.
echo Existing API Gateway Keys:
CALL gcloud services api-keys list --project="%GCP_PROJ_ID%" --format="table(name.basename(),displayName,createTime)"
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%: 
	EXIT /B
)
echo.
echo Number of new API Keys to create: %NUM_KEYS%

echo.
echo Press ENTER to continue, CTRL-C to abort.
pause

rem ------------------------------------------------------------------------------------------------------
rem --- CREATE KEYS AND APPLY SERVICE RESTRICTION ---
rem ------------------------------------------------------------------------------------------------------

rem Get the Managed Service Name once before the loop
for /f "delims=" %%A in ('gcloud endpoints services list --sort-by=NAME --format="value(serviceName)"') do (
    set GCP_ENDPOINT_SERVICE_NAME=%%A
)
echo Endpoint Service Name: !GCP_ENDPOINT_SERVICE_NAME!

FOR /L %%X IN (1, 1, %NUM_KEYS%) DO (
    echo.
    echo --- Creating API Key %%X of %NUM_KEYS% using name: %GCP_API_KEY_DISPLAY_NAME% ---
    CALL gcloud services api-keys create --display-name="%GCP_API_KEY_DISPLAY_NAME%" --project="%GCP_PROJ_ID%"

    rem Capture the newest internal Key Name (%%K) and immediately use it to get the string (%%S)
    FOR /F "tokens=*" %%K IN ('gcloud services api-keys list --filter="displayName:%GCP_API_KEY_DISPLAY_NAME%" --sort-by="~createTime" --limit=1 --format="value(name)"') DO (
        SET "API_KEY_NAME=%%K"
        echo Internal API Key Name %%X: %%K

        rem Retrieve the actual Key String using %%K directly
        FOR /F "tokens=*" %%S IN ('gcloud alpha services api-keys get-key-string %%K --format="value(keyString)"') DO (
            SET "NEW_API_KEY_STRING=%%S"
        )
    )

    rem Apply restrictions
    CALL gcloud services api-keys update !API_KEY_NAME! --api-target="service=%GCP_ENDPOINT_SERVICE_NAME%" --location="%GCP_REGION%"
    
    echo.
    echo ==============================================================================
    echo New API Key String %%X ^(use this in your client^): !NEW_API_KEY_STRING!
    echo ==============================================================================
)

echo.
rem ------------------------------------------------------------------------------------------------------
rem --- MANDATORY WAIT FOR PROPAGATION (5 minutes) ---
rem ------------------------------------------------------------------------------------------------------
echo Waiting 30 seconds for API Key Restrictions to propagate..
timeout /t 30 /nobreak

echo.
echo ==============================================================================
echo --- All API Keys and Values ---
FOR /F "tokens=1,* delims=," %%A IN ('gcloud services api-keys list --project="%GCP_PROJ_ID%" --format="csv[no-heading](name,displayName)"') DO (
    FOR /F "tokens=*" %%C IN ('gcloud alpha services api-keys get-key-string %%A --project="%GCP_PROJ_ID%" --format="value(keyString)"') DO (
        echo %%~B: %%C
    )
)
echo ==============================================================================
echo.

echo This batch file %~n0%~x0 has ended normally (no errors).
echo You can repeat running this batch file again if needed.
echo.
echo When you are finished with the project, execute the batch file "gcp_api_gateway_cleanup.bat".