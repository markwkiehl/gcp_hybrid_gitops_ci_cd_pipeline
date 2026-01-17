@echo off
echo %~n0%~x0   version 0.0.0
echo.

rem Created by Mechatronic Solutions LLC
rem Mark W Kiehl
rem
rem LICENSE: MIT


rem Batch files: https://steve-jansen.github.io/guides/windows-batch-scripting/
rem Batch files: https://tutorialreference.com/batch-scripting/batch-script-tutorial
rem Scripting Google CLI:  https://cloud.google.com/sdk/docs/scripting-gcloud

rem Verify that CLOUDSDK_PYTHON has already been set permanently for the user by gcp_part1.bat
IF NOT EXIST "%CLOUDSDK_PYTHON%" (
echo ERROR: CLOUDSDK_PYTHON path not found.  %CLOUDSDK_PYTHON%
echo Did you previously run gcp_part1.bat ?
EXIT /B
)


rem Make sure GOOGLE_APPLICATION_CREDENTIALS is not set so that Google ADC flow will work properly.
IF NOT "%GOOGLE_APPLICATION_CREDENTIALS%"=="" (
echo .
echo ERROR: GOOGLE_APPLICATION_CREDENTIALS has been set!
echo GOOGLE_APPLICATION_CREDENTIALS=%GOOGLE_APPLICATION_CREDENTIALS%
echo The environment variable GOOGLE_APPLICATION_CREDENTIALS must NOT be set in order to allow Google ADC to work properly.
echo Press RETURN to unset GOOGLE_APPLICATION_CREDENTIALS, CTRL-C to abort. 
pause
@echo on
SET GOOGLE_APPLICATION_CREDENTIALS=
CALL SETX GOOGLE_APPLICATION_CREDENTIALS ""
@echo off
echo Restart this file %~n0%~x0
EXIT /B
)



SETLOCAL

rem Define the working folder to Google Cloud CLI (gcloud) | Google Cloud SDK Shell
rem derived from the USERPROFILE environment variable.
rem This requires that the Google CLI/SKD has already been installed.
SET PATH_GCLOUD=%USERPROFILE%\AppData\Local\Google\Cloud SDK
IF NOT EXIST "%PATH_GCLOUD%\." (
	echo ERROR: PATH_GCLOUD path not found.  %PATH_GCLOUD%
	echo Did you install Google CLI / SKD? 
	EXIT /B
)
rem echo PATH_GCLOUD: %PATH_GCLOUD%

rem The current working directory for this script should be the same as the Python virtual environment for this project.
SET PATH_SCRIPT=%~dp0
rem echo PATH_SCRIPT: %PATH_SCRIPT%


echo.
echo PROJECT LOCAL VARIABLES:
echo.


rem import the GCP project constants from file gcp_constants.txt
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)


rem ----------------------------------------------------------------------
rem Show the project variables related to this task

rem set the Google Cloud Platform Project ID
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_REGION: %GCP_REGION%
echo GCP_USER: %GCP_USER%
SET GCP_SVC_ACT=%GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com
echo GCP_SVC_ACT: %GCP_SVC_ACT%

echo.
echo This batch file will:
echo .
echo Press ENTER to continue, or CTRL-C to abort.
pause


rem Enable the Cloud Firestore API.
rem NOTE: Enabling the API (firestore.googleapis.com) allows your project to USE Firestore, but it does not automatically create the database instance.
@echo on
CALL gcloud services enable firestore.googleapis.com --project=%GCP_PROJ_ID%
@echo off
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%
	EXIT /B
)


rem Delete any provisioned database that already exists.
@echo on
CALL gcloud alpha firestore databases delete --database="(default)" --quiet
@echo off
echo ERRORLEVEL: %ERRORLEVEL%
IF %ERRORLEVEL% == 0 (
	echo Waiting 35 seconds for any delete to finish
	timeout /t 35 /nobreak
)


rem Provision the default Firestore Native database in the region %GCP_REGION%
@echo on
CALL gcloud alpha firestore databases create --database="(default)" --location="%GCP_REGION%" --project="mcp-noaa-v0-3"
@echo off
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%
	EXIT /B
)


rem Grant the service account permission to read/write the database data.
rem roles/datastore.user is the standard role for Firestore data access
@echo on
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/datastore.user"
@echo off
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%
	EXIT /B
)
	
	
rem Grant Impersonation Permission
rem Add role roles/iam.serviceAccountTokenCreator
rem gcloud iam service-accounts add-iam-policy-binding SVC_ACT_EMAIL --member='user:USER_EMAIL' --role='roles/iam.serviceAccountTokenCreator'
rem gcloud iam service-accounts add-iam-policy-binding svc-act-mcp-fastapi@mcp-fastapi-v0-3.iam.gserviceaccount.com --member='user:markwkiehl@gmail.com' --role='roles/iam.serviceAccountTokenCreator' --project='mcp-fastapi-v0-3'
@echo on
CALL gcloud iam service-accounts add-iam-policy-binding %GCP_SVC_ACT% --member=user:%GCP_USER% --role=roles/iam.serviceAccountTokenCreator --project=%GCP_PROJ_ID%
@echo off
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%
	EXIT /B
)

rem Update local Application Default Credentials (ADC)
echo.
echo Google user %GCP_USER% must authorize the addition of the roles and enabled APIs.
echo You may close the browser when authorization is complete and then return to this window.
pause
@echo on
CALL gcloud auth application-default login --impersonate-service-account %GCP_SVC_ACT%
@echo off
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%
	EXIT /B
)




ENDLOCAL

echo.
echo This batch file %~n0%~x0 has ended normally (no errors).  
echo You may repeat running this batch file if necessary. 
