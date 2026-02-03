@echo off
cls
echo %~n0%~x0   version 0.1.2
echo.

rem	v0.0.0	initial release
rem	v0.1.0	Revised to accommodate separate Python scripts (src) from Python virtual environment (.venv) and GCP batch files in 'gcp'.
rem			gcp_constants.bat renamed to gcp_constants.txt
rem	v0.1.0	New Python project structure 13 Dec 2025
rem v0.1.1	Removed unneeded constants referenced from gcp_constants.txt
rem v0.1.2	Revised last echo


rem Created by Mechatronic Solutions LLC
rem Mark W Kiehl
rem
rem LICENSE: MIT


rem Batch files: https://steve-jansen.github.io/guides/windows-batch-scripting/
rem Batch files: https://tutorialreference.com/batch-scripting/batch-script-tutorial
rem Scripting Google CLI:  https://cloud.google.com/sdk/docs/scripting-gcloud



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


rem import the GCP project constants from file gcp_constants.txt
if EXIST "gcp_constants.txt" (
  for /F "tokens=*" %%I in (gcp_constants.txt) do set %%I
) ELSE (
  echo ERROR: unable to find gcp_constants.txt
  EXIT /B
)



rem CLOUDSDK_PYTHON is used by Google Cloud CLI & SDK
rem Using %GCP_PYTHON_VERSION%, define a path to python.exe for that version and assign to CLOUDSDK_PYTHON.
rem py --list-paths will show what Python versions are installed.
rem Path example: C:\Users\[username]\AppData\Local\Programs\Python\Python312\python.exe
SET CLOUDSDK_PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python%GCP_PYTHON_VERSION:.=%\python.exe
IF NOT EXIST "%CLOUDSDK_PYTHON%" (
	echo.
	echo ERROR: CLOUDSDK_PYTHON path not found.  %CLOUDSDK_PYTHON%
	echo Is Python version %GCP_PYTHON_VERSION% installed?
	EXIT /B
)

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


SET PATH_SCRIPT=%~dp0
rem echo PATH_SCRIPT: %PATH_SCRIPT%


rem Get the project folder path
for %%I in ("%~dp0..") do set "PROJ_DIR=%%~fI"
rem echo PROJ_DIR: %PROJ_DIR%

rem get the src path
SET SRC_DIR=%PROJ_DIR%\src
IF NOT EXIST "%PROJ_DIR%" (
echo ERROR: PROJ_DIR path not found.  %PROJ_DIR%
EXIT /B
)
rem echo SRC_DIR: %SRC_DIR%

rem SET VENV_DIR=%PROJ_DIR%\.venv
for %%I in ("%PROJ_DIR%\.venv") do set "VENV_DIR=%%~fI"
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
rem echo VENV_DIR: %VENV_DIR%



rem ----------------------------------------------------------------------
echo.
echo PROJECT LOCAL VARIABLES:
echo.

rem Variable defined earlier
echo CLOUDSDK_PYTHON: %CLOUDSDK_PYTHON%

echo GCP_PYTHON_VERSION: %GCP_PYTHON_VERSION%


echo.
echo Review the settings listed above carefully.
echo The values for GCP_PYTHON_VERSION, and CLOUDSDK_PYTHON must be valid.
echo The Python version referenced by GCP_PYTHON_VERSION has been verified to already exist and the  
echo variable CLOUDSDK_PYTHON will be permanently configured to reference that Python installation location. 
echo The other local variable assignments shown will be used later by the other batch files.
echo.
echo This script will:
echo 1) Configure the environment variable CLOUDSDK_PYTHON (required for GCP SDK).
echo 2) Upgrade PIP for Python version %GCP_PYTHON_VERSION%.
echo 3) Install Python packages defined in the file pip_install.txt:
rem CALL type pip_install.txt
echo.
REM echo Press ENTER to continue, or CTRL-C to abort so you can edit the file gcp_constants.txt.
pause

rem ----------------------------------------------------------------------

rem Finalize and make permanent the environment variable CLOUDSDK_PYTHON for the user. 
echo Making the environment variable CLOUDSDK_PYTHON permanent..
CALL setx CLOUDSDK_PYTHON "%CLOUDSDK_PYTHON%"
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)

rem Make sure PIP is installed / upgraded to the latest for Python v3.12
echo.
echo Upgrading PIP
CALL py -%GCP_PYTHON_VERSION% -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)


rem Create a virtual envrionment in the folder %VENV_DIR%
echo.
echo Creating a Python virtual environment in folder '%VENV_DIR%'..
CALL py -%GCP_PYTHON_VERSION% -m venv %VENV_DIR%
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)

rem Navigate to the %VENV_DIR% folder
CALL cd /D %VENV_DIR%


rem Activate the virtual environment
echo.
echo Activating the Python virtual environment..
CALL scripts\activate
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)
CALL py -V

rem Check if PIP needs to be upgraded for the virtual environment (it always seems to need to be upgraded).
CALL py -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)



rem Make sure the pip_install.txt file exists.
SET PIP_INSTALL="%PATH_SCRIPT%\pip_install.txt"
IF NOT EXIST "%PIP_INSTALL%" (
	echo ERROR: File not found.  %PIP_INSTALL%
	EXIT /B
)


rem Show the currently installed Python packages
echo.
echo Installed Python packages before installation from pip_install.txt:
CALL py -m pip list


rem Install Python packages as specified in pip_install.txt
echo Installing Python packages as specified in pip_install.txt
CALL py -m pip install -r "%PIP_INSTALL%"


echo.
echo Installed Python packages after installation from pip_install.txt:
CALL py -m pip list



rem Deactivate the virtual environment
echo Deactivating the Python virtual environment..@echo on
CALL scripts\deactivate
IF %ERRORLEVEL% NEQ 0 (
	echo ERROR %ERRORLEVEL%:
	EXIT /B
)


ENDLOCAL


echo.
echo This batch file %~n0%~x0 has ended normally (no errors).  
echo Next, execute the Python script `gcp_generator.py` located in the /gcp folder.
EXIT /B


