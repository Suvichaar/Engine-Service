# Azure Backend Report

Date: 2026-04-03

## What We Did

We set up Azure App Service deployment for both backend services:

1. Updated the existing News backend Azure App Service
2. Deployed the Curious backend to Azure App Service for the first time

Both backends are now live on separate Azure URLs, so the UI can use:

- News mode -> News backend URL
- Curious mode -> Curious backend URL

## Azure Resources Used

We used the existing Azure setup under the same resource group and App Service plan.

### Resource Group

- `engine-rg`

### App Service Plan

- `engine-service-plan`
- SKU: `B1`
- Linux container App Service plan

### Azure Container Registry

- `engineservice2026`
- Login server: `engineservice2026.azurecr.io`

## News Backend

### Existing Resource Updated

- Web App: `engine-service`
- URL: `https://engine-service.azurewebsites.net`

### Container Image Used

- Image: `engineservice2026.azurecr.io/newsengine-backend:latest`

### What We Did

- Built the latest News backend image in Azure Container Registry
- Pushed the updated image to ACR
- Refreshed the Azure Web App container config
- Restarted the Azure Web App

### Health Check

- `https://engine-service.azurewebsites.net/health`
- Response: `{"status":"ok"}`

## Curious Backend

### New Resource Created

- Web App: `curious-engine-service`
- URL: `https://curious-engine-service.azurewebsites.net`

### Container Image Used

- Image: `engineservice2026.azurecr.io/curious-backend:latest`

### What We Did

- Built the Curious backend image in Azure Container Registry
- Pushed the image to ACR
- Created a new Azure Web App on the existing App Service plan
- Connected the new Web App to the Curious container image
- Applied runtime app settings
- Restarted the Azure Web App

### Health Check

- `https://curious-engine-service.azurewebsites.net/health`
- Response: `{"status":"ok"}`

## What Was Created vs Reused

### Reused

- Resource Group: `engine-rg`
- App Service Plan: `engine-service-plan`
- Azure Container Registry: `engineservice2026`
- Existing News Web App: `engine-service`

### Created New

- New Curious Web App: `curious-engine-service`
- New ACR image: `curious-backend:latest`

### Updated

- News ACR image: `newsengine-backend:latest`
- News Web App container deployment

## Runtime Config Used

For the Curious backend, we reused the working News backend runtime configuration pattern.

### Main App Settings Used

- `WEBSITES_PORT=8000`
- `STARTUP_COMMAND=uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `DATABASE_URL`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `AI_IMAGE_ENDPOINT`
- `AI_IMAGE_API_KEY`
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
- `PEXELS_API_KEY`
- `SERPER_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `VOICE_BUCKET`
- `VOICE_PREFIX`
- `STORY_BASE_URL`
- `HTML_BUCKET`
- `CORS_ALLOWED_ORIGINS`

### Base URL Setup

- News backend `BASE_URL` is currently set to:
  - `https://engine-service.azurewebsites.net`
- News backend live Azure App Service URL is:
  - `https://engine-service.azurewebsites.net`
- This means News is now fully aligned: live URL and `BASE_URL` are the same
- Curious backend `BASE_URL` was set to:
  - `https://curious-engine-service.azurewebsites.net`
- Curious backend live Azure App Service URL is also:
  - `https://curious-engine-service.azurewebsites.net`
- This means Curious is fully aligned: live URL and `BASE_URL` are the same

## CORS Used

The backend config includes these frontend origins:

- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `https://suvichaar-storygenerator.vercel.app`

If the frontend is deployed on another domain later, that domain must also be added.

## Deployment Method Used

We used Azure Container Registry remote builds instead of local Docker builds.

Reason:

- Local Docker daemon was not available
- So images were built directly in Azure using `az acr build`

## Final Live Backend URLs

- News backend: `https://engine-service.azurewebsites.net`
- Curious backend: `https://curious-engine-service.azurewebsites.net`

## How UI Should Use Them

- If user selects News mode:
  - call `https://engine-service.azurewebsites.net`

- If user selects Curious mode:
  - call `https://curious-engine-service.azurewebsites.net`

## Final Status

Both backend Azure services are running and responding successfully.
