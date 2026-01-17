@echo off
echo %~n0%~x0   version 0.0.1
echo.


rem v0.0.0	13 Dec 2025
rem v0.0.1	Moved dataset delete and provision to the end of script as an option. 

rem Created by Mechatronic Solutions LLC
rem Mark W Kiehl
rem
rem LICENSE: MIT


rem Batch files: https://steve-jansen.github.io/guides/windows-batch-scripting/
rem Batch files: https://tutorialreference.com/batch-scripting/batch-script-tutorial
rem Scripting Google CLI:  https://cloud.google.com/sdk/docs/scripting-gcloud


rem Verify that CLOUDSDK_PYTHON has already been set permanently for the user by gcp_part1.bat
IF NOT EXIST "%CLOUDSDK_PYTHON%" (
echo ERROR: CLOUDSDK_PYTHON path not found  %CLOUDSDK_PYTHON%
EXIT /B
)


rem Make sure GOOGLE_APPLICATION_CREDENTIALS is not set so that Google ADC flow will work properly.
IF NOT "%GOOGLE_APPLICATION_CREDENTIALS%"=="" (
echo.
echo ERROR: GOOGLE_APPLICATION_CREDENTIALS has been set!
echo GOOGLE_APPLICATION_CREDENTIALS=%GOOGLE_APPLICATION_CREDENTIALS%
echo The environment variable GOOGLE_APPLICATION_CREDENTIALS must NOT be set in order to allow Google ADC to work properly
echo Press RETURN to unset GOOGLE_APPLICATION_CREDENTIALS, CTRL-C to abort
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
echo ERROR: PATH_GCLOUD path not found  "%PATH_GCLOUD%"
echo Did you install Google CLI / SKD
EXIT /B
)
rem echo PATH_GCLOUD: "%PATH_GCLOUD%"




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
echo BigQuery DatasetID (GCP_BQ_DATASET_ID): %GCP_BQ_DATASET_ID%

echo.
echo This batch file will:
echo - Enable the BigQuery API
echo - Install the BigQuery CLI (bq)
echo - Grant BigQuery Data Editor role to the service account
echo - Grant Impersonation Permission to the user
echo - Update local Application Default Credentials (ADC)
echo Press ENTER to continue, or CTRL-C to abort
pause


rem Make sure all existing gcloud components are updated.
echo.
echo Making sure all existing gcloud CLI components are updated
CALL gcloud components update
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem Enable the BigQuery API. (APIs for BigQuery are bigquery.googleapis.com and bigqueryconnection.googleapis.com)
echo.
echo Enabling the BigQuery API
CALL gcloud services enable bigquery.googleapis.com --project=%GCP_PROJ_ID%
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem Verify BigQuery CLI is installed.  Install if needed.
echo.
echo Verifying BigQuery CLI (bq) is installed (ignore any reported errors here).
CALL bq version
IF %ERRORLEVEL% NEQ 0 (
	CALL gcloud components install bq --quiet
)
rem ERRORLEVEL=1 even after successful install.  Use bq version to check installation.
CALL bq version
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR: install of BigQuery CLI failed.   
	EXIT /B
)


rem Grant the service account permission to read/write the BigQuery data.
rem roles/bigquery.dataEditor is the standard role for BigQuery data access (CRUD on data).
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.dataEditor"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)
	
	
rem Add BigQuery User role to the service account to allow job creation.
echo.
echo Granting BigQuery User role (bigquery.jobs.create) to the service account
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.user"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem roles/bigquery.dataViewer
echo.
echo Granting BigQuery User role roles/bigquery.dataViewer) to the service account
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.dataViewer"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem roles/bigquery.metadataViewer
echo.
echo Granting BigQuery User role roles/bigquery.metadataViewer to the service account
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.metadataViewer"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem roles/bigquery.readSessionUser
echo.
echo Granting BigQuery User role roles/bigquery.readSessionUser to the service account
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.readSessionUser"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem roles/bigquery.dataOwner
echo.
echo Granting BigQuery User role roles/bigquery.dataOwner to the service account
CALL gcloud projects add-iam-policy-binding %GCP_PROJ_ID% --member="serviceAccount:%GCP_SVC_ACT%" --role="roles/bigquery.dataOwner"
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)


	
rem Grant Impersonation Permission
rem Add role roles/iam.serviceAccountTokenCreator
CALL gcloud iam service-accounts add-iam-policy-binding %GCP_SVC_ACT% --member=user:%GCP_USER% --role="roles/iam.serviceAccountTokenCreator" --project=%GCP_PROJ_ID%
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)

rem Update local Application Default Credentials (ADC)
echo.
echo Google user %GCP_USER% must authorize the addition of the roles and enabled APIs
echo You may close the browser when authorization is complete and then return to this window
pause
CALL gcloud auth application-default login --impersonate-service-account %GCP_SVC_ACT%
IF %ERRORLEVEL% NEQ 0 (
echo ERROR %ERRORLEVEL%
EXIT /B
)


echo.
CALL gcloud services list --enabled | findstr bigquery


rem =========================================================================================================
rem Delete any existing dataset and create a new dataset

rem List datasets for a project
echo.
echo Datasets for %GCP_PROJ_ID%:
rem bq ls --format=pretty --project_id=projectId
CALL bq ls --format=pretty --project_id=%GCP_PROJ_ID%

echo.
echo If you continue, the dataset %GCP_BQ_DATASET_ID%" will be created (any existing will be deleted).
echo Press ENTER to continue, CTRL-C to abort
pause


rem Delete any dataset and tables that may already exist 
rem Delete a dataset and all of its tables (-r), with no confirmation (-f)
rem bq rm -r -f projectId:datasetId
echo.
echo Deleting any existing datasets and tables
CALL bq rm -r -f --quiet "%GCP_PROJ_ID%:%GCP_BQ_DATASET_ID%"


rem Create the dataset
echo.
echo Provisioning BigQuery Dataset: %GCP_BQ_DATASET_ID% in region %GCP_REGION%
rem Note: BigQuery tables do not expire by default.
rem CALL bq --location=%GCP_REGION% mk -d --default_table_expiration 86400 --description "dataset for %GCP_PROJ_ID%" %GCP_PROJ_ID%:%GCP_BQ_DATASET_ID%
rem CALL bq mk --dataset --project_id=%GCP_PROJ_ID% --location="%GCP_REGION%
CALL bq --location=%GCP_REGION% mk -d "%GCP_PROJ_ID%:%GCP_BQ_DATASET_ID%"
rem NOTE: This command will fail gracefully if the dataset already exists, resulting in a non-zero error code.
IF %ERRORLEVEL% NEQ 0 echo WARNING: Dataset creation failed or already exists (Error code %ERRORLEVEL%). Continuing...

rem List datasets for a project
echo.
echo Datasets for %GCP_PROJ_ID%:
rem bq ls --format=pretty --project_id=projectId
CALL bq ls --format=pretty --project_id=%GCP_PROJ_ID%




ENDLOCAL

echo.
echo This batch file %~n0%~x0 has ended normally (no errors).  
echo You may repeat running this batch file if necessary.