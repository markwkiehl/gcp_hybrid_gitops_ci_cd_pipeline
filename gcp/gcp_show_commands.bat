@echo off
echo.
echo GCP_PROJ_ID: ci-cd-pipeline-v0-8
echo Cloud Run: ci-cd-pipeline
echo Region: us-east4
echo Project-Local Service Account: svc-act-ci-cd-pipeline@ci-cd-pipeline-v0-8.iam.gserviceaccount.com
echo GCP_BQ_DATASET_ID: ci_cd_pipeline_v0_8
echo Cloud Storage Bucket: ci-cd-pipeline-v0-8

echo.
echo Cloud Run URL:
echo gcloud run services describe ci-cd-pipeline --project=ci-cd-pipeline-v0-8 --region=us-east4 --format="value(status.url)"

echo.
echo Cloud Run Log:
echo gcloud run services logs read ci-cd-pipeline --project=ci-cd-pipeline-v0-8 --region=us-east4 --limit 50

echo.
echo Cloud Storage Bucket Contents
echo gcloud storage ls gs://ci-cd-pipeline-v0-8

echo.
echo Show environment variables available to the Cloud Run app
echo gcloud run services describe ci-cd-pipeline --region=us-east4 --format="yaml(spec.template.spec.containers[0].env)"

echo.
echo How to copy file from /data to Storage Bucket
rem Get the project folder path
for %%I in ("%~dp0..") do set "PROJ_DIR=%%~fI"
SET DATA_DIR=%PROJ_DIR%\data
echo gcloud storage cp "%DATA_DIR%\README.txt" gs://%GCP_GS_BUCKET%
echo.
