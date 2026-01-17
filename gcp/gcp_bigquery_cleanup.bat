@echo off
echo %~n0%~x0   version 0.0.0
echo.

rem Created by Gemini AI (Argument-Based BigQuery Cleanup)
rem
rem LICENSE: MIT


rem Batch files: https://steve-jansen.github.io/guides/windows-batch-scripting/
rem Batch files: https://tutorialreference.com/batch-scripting/batch-script-tutorial
rem Scripting Google CLI:  https://cloud.google.com/sdk/docs/scripting-gcloud

rem --- ARGUMENT CHECK ---
rem Check if the Dataset ID was passed as the first argument (%1)
IF "%1"=="" (
    echo ERROR: Missing required argument!
    echo Usage: %~n0%~x0 <BigQuery_Dataset_ID>
    echo Example: %~n0%~x0 my_test_data
    EXIT /B 1
)
SET GCP_BQ_DATASET_ID=%1

rem Verify that CLOUDSDK_PYTHON has already been set permanently for the user by gcp_part1.bat
IF NOT EXIST "%CLOUDSDK_PYTHON%" (
echo ERROR: CLOUDSDK_PYTHON path not found.  %CLOUDSDK_PYTHON%
echo Did you previously run gcp_part1.bat ?
EXIT /B 1
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
EXIT /B 1
)



SETLOCAL

rem Define the working folder to Google Cloud CLI (gcloud) | Google Cloud SDK Shell
rem derived from the USERPROFILE environment variable.
rem This requires that the Google CLI/SKD has already been installed.
SET PATH_GCLOUD=%USERPROFILE%\AppData\Local\Google\Cloud SDK
IF NOT EXIST "%PATH_GCLOUD%\."
(
	echo ERROR: PATH_GCLOUD path not found.  %PATH_GCLOUD%
	echo Did you install Google CLI / SKD? 
	EXIT /B 1
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
  EXIT /B 1
)


rem ----------------------------------------------------------------------
rem Show the project variables related to this task

rem set the Google Cloud Platform Project ID
echo GCP_PROJ_ID: %GCP_PROJ_ID%
echo GCP_REGION: %GCP_REGION%
echo GCP_USER: %GCP_USER%
SET GCP_SVC_ACT=%GCP_SVC_ACT_PREFIX%@%GCP_PROJ_ID%.iam.gserviceaccount.com
echo GCP_SVC_ACT: %GCP_SVC_ACT%
echo BIGQUERY DATASET: %GCP_BQ_DATASET_ID%

echo.
echo BigQuery Datasets:
CALL gcloud bigquery datasets list

echo.
echo This batch file will:
echo - Delete the BigQuery dataset "%GCP_BQ_DATASET_ID%" (and all tables inside it).
echo Press ENTER to continue, or CTRL-C to abort.
pause


rem --- BIGQUERY CLEANUP EXECUTION ---

rem Delete the specified BigQuery dataset (which deletes all contained tables and views).
rem The '--force' flag is required to delete a non-empty dataset.
@echo on
CALL gcloud bigquery datasets delete %GCP_BQ_DATASET_ID% --project=%GCP_PROJ_ID% --force --quiet
@echo off
rem ERRORLEVEL will be 0 if the dataset was successfully deleted or was already missing
IF %ERRORLEVEL% NEQ 0 (
	rem Note: ERRORLEVEL can be 1 if the dataset was not found, but we proceed anyway 
    rem unless a more serious error occurred. For cleanup, we can treat 1 as "done".
    EXIT /B 0 
)

echo.
echo Waiting 5 seconds for any delete to finish
timeout /t 5 /nobreak


ENDLOCAL

echo.
echo This batch file %~n0%~x0 has ended normally (no errors).
echo You may repeat running this batch file if necessary.
