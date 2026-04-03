# Azure App Service Deployment

This repo contains a containerized FastAPI backend in `backend/Dockerfile`. The clean deployment path is to run it as a Linux custom container on Azure App Service backed by Azure Container Registry.

## What Gets Deployed

- FastAPI curious backend on Azure App Service for Linux
- Docker image stored in Azure Container Registry
- App Service pulls that image from ACR

## Prerequisites

- Azure CLI installed: `az`
- Docker installed and running
- Azure subscription selected with `az login`

## One-Command Deploy

Use the script at `deploy-to-appservice.sh`:

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
  curious-rg \
  curious-linux-plan \
  curious-service-api \
  curiousacr \
  latest \
  centralindia
```

Defaults used by the script:

- `LOCATION=centralindia`
- `IMAGE_NAME=curious-backend`
- `APP_SERVICE_SKU=B1`
- `STARTUP_COMMAND=uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Runtime App Settings

Set real runtime secrets with `set-backend-appsettings.sh`.

Required:

- `DATABASE_URL`
- `AI_IMAGE_ENDPOINT`
- `AI_IMAGE_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`

Common optional settings:

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
- `HTML_S3_PREFIX`
- `CDN_PREFIX_MEDIA`
- `CDN_HTML_BASE`
- `CDN_BASE`
- `DEFAULT_ERROR_IMAGE`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `PEXELS_API_KEY`
- `SERPER_API_KEY`
- `VOICE_BUCKET`
- `VOICE_PREFIX`
- `CORS_ALLOWED_ORIGINS`

Example:

```bash
export DATABASE_URL='postgresql+psycopg://...'
export AI_IMAGE_ENDPOINT='https://...'
export AI_IMAGE_API_KEY='...'
export AZURE_OPENAI_ENDPOINT='https://<your-openai-resource>.openai.azure.com/'
export AZURE_OPENAI_API_KEY='...'
export AZURE_OPENAI_DEPLOYMENT='gpt-4o-mini'
export CORS_ALLOWED_ORIGINS='http://localhost:3000,http://127.0.0.1:3000,https://your-frontend.vercel.app'

./set-backend-appsettings.sh <resource-group> <app-name>
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

## Repo Notes

- The backend listens on port `8000`, so App Service must have `WEBSITES_PORT=8000`.
- Production should rely on App Service settings or Key Vault-backed injection instead of checked-in secrets.
- `backend/app/core/settings.toml` is for local placeholder defaults only.
