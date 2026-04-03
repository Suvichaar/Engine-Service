# Azure App Service Deployment

This repo already contains a containerized backend in [backend/Dockerfile](/Users/kumar_mayank/Desktop/Engine-Service/backend/Dockerfile). The clean App Service path is to deploy that backend as a Linux custom container backed by Azure Container Registry.

This guide covers the backend only. The Next.js frontend in [Suvichaar-Storygenerator](/Users/kumar_mayank/Desktop/Engine-Service/Suvichaar-Storygenerator) should be deployed separately.

## What Gets Deployed

- FastAPI backend on Azure App Service for Linux
- Docker image stored in Azure Container Registry
- App Service pulls that image from ACR

## Prerequisites

- Azure CLI installed: `az`
- Docker installed and running
- Azure subscription selected with `az login`

## One-Command Deploy

Use the script at [deploy-to-appservice.sh](/Users/kumar_mayank/Desktop/Engine-Service/deploy-to-appservice.sh):

```bash
chmod +x deploy-to-appservice.sh

./deploy-to-appservice.sh \
  <resource-group> \
  <plan-name> \
  <app-name> \
  <acr-name> \
  [image-tag] \
  [location]
```

Example:

```bash
./deploy-to-appservice.sh \
  engine-rg \
  engine-linux-plan \
  engine-service-api \
  engineacr \
  latest \
  centralindia
```

Defaults used by the script:

- `LOCATION=centralindia`
- `IMAGE_NAME=newsengine-backend`
- `APP_SERVICE_SKU=B1`
- `STARTUP_COMMAND=uvicorn app.main:app --host 0.0.0.0 --port 8000`

## What The Script Does

1. Ensures the Azure login is active
2. Creates the resource group if needed
3. Creates the Azure Container Registry if needed
4. Builds the Docker image from [backend/Dockerfile](/Users/kumar_mayank/Desktop/Engine-Service/backend/Dockerfile)
5. Pushes the image to ACR
6. Creates a Linux App Service plan if needed
7. Creates or updates the Web App
8. Configures the container registry credentials
9. Sets `WEBSITES_PORT=8000`
10. Restarts the app

## Required App Settings

After deployment, set the real runtime secrets. The simplest path is the helper script at [set-backend-appsettings.sh](/Users/kumar_mayank/Desktop/Engine-Service/set-backend-appsettings.sh).

Example with your shell environment:

```bash
export DATABASE_URL='postgresql+psycopg://...'
export AI_IMAGE_ENDPOINT='https://njnam-m3jxkka3-swedencentral.services.ai.azure.com/providers/blackforestlabs/v1/flux-2-pro?api-version=preview'
export AI_IMAGE_API_KEY='...'
export AZURE_OPENAI_ENDPOINT='https://<your-openai-resource>.openai.azure.com/'
export AZURE_OPENAI_API_KEY='...'
export AZURE_OPENAI_DEPLOYMENT='<your-text-model-deployment>'
export AZURE_OPENAI_API_VERSION='2025-01-01-preview'

./set-backend-appsettings.sh <resource-group> <app-name>
```

At minimum, this app usually needs some subset of:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`
- `AZURE_SPEECH_VOICE`
- `AZURE_DI_ENDPOINT`
- `AZURE_DI_KEY`
- `AWS_ACCESS_KEY`
- `AWS_SECRET_KEY`
- `AWS_REGION`
- `AWS_BUCKET`
- `S3_PREFIX`
- `CDN_PREFIX_MEDIA`
- `CDN_HTML_BASE`
- `CDN_BASE`
- `STORY_BASE_URL`
- `HTML_BUCKET`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `PEXELS_API_KEY`
- `AI_IMAGE_ENDPOINT`
- `AI_IMAGE_API_KEY`
- `DATABASE_URL`

Manual example:

```bash
az webapp config appsettings set \
  --name <app-name> \
  --resource-group <resource-group> \
  --settings \
    WEBSITES_PORT=8000 \
    AZURE_OPENAI_ENDPOINT="https://your-openai-resource.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="..." \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o-mini" \
    AZURE_OPENAI_API_VERSION="2025-01-01-preview" \
    DATABASE_URL="postgresql+psycopg://..."
```

## Verify

```bash
curl https://<app-name>.azurewebsites.net/health
```

Useful checks:

```bash
az webapp log tail --name <app-name> --resource-group <resource-group>
az webapp show --name <app-name> --resource-group <resource-group> --query defaultHostName -o tsv
```

## Important Repo-Specific Notes

- The backend listens on port `8000`, so App Service must have `WEBSITES_PORT=8000`.
- The app is image-based; do not use zip deploy for the backend as currently structured.
- The checked-in config file [backend/app/core/settings.toml](/Users/kumar_mayank/Desktop/Engine-Service/backend/app/core/settings.toml) contains placeholders. Production should rely on App Service app settings or Key Vault-backed injection.
- The current repo deployment docs mostly target Azure Container Apps, not App Service.

## Frontend

The frontend in [Suvichaar-Storygenerator](/Users/kumar_mayank/Desktop/Engine-Service/Suvichaar-Storygenerator) is a separate deployment concern. Recommended options:

- Azure Static Web Apps
- Vercel
- Azure App Service as a separate Node app

Do not try to deploy both backend and frontend into the same App Service instance unless you first restructure the repo around a single runtime entrypoint.
