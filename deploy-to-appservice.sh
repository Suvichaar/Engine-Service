#!/bin/bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./deploy-to-appservice.sh <resource-group> <plan-name> <app-name> <acr-name> [image-tag] [location]

Example:
  ./deploy-to-appservice.sh curious-rg curious-plan curious-api curiousacr latest centralindia

Required tools:
  - az
  - docker

Environment variables:
  LOCATION          Azure region. Default: centralindia
  APP_SERVICE_SKU   App Service plan SKU. Default: B1
  IMAGE_NAME        Docker image repository name. Default: curious-backend
  IMAGE_PLATFORM    Docker target platform. Default: linux/amd64
  STARTUP_COMMAND   Linux startup command. Default: uvicorn app.main:app --host 0.0.0.0 --port 8000
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 4 || $# -gt 6 ]]; then
  usage
  exit 1
fi

RESOURCE_GROUP="$1"
PLAN_NAME="$2"
APP_NAME="$3"
ACR_NAME="$4"
IMAGE_TAG="${5:-latest}"
LOCATION="${6:-${LOCATION:-centralindia}}"

APP_SERVICE_SKU="${APP_SERVICE_SKU:-B1}"
IMAGE_NAME="${IMAGE_NAME:-curious-backend}"
IMAGE_PLATFORM="${IMAGE_PLATFORM:-linux/amd64}"
STARTUP_COMMAND="${STARTUP_COMMAND:-uvicorn app.main:app --host 0.0.0.0 --port 8000}"
IMAGE_REF="${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd az
require_cmd docker

echo "Checking Azure login..."
if ! az account show >/dev/null 2>&1; then
  az login
fi

echo "Using Azure location: $LOCATION"

echo "Ensuring resource group exists..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

echo "Ensuring ACR exists..."
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output none
fi

echo "Logging in to ACR..."
az acr login --name "$ACR_NAME"

echo "Building and pushing image for platform $IMAGE_PLATFORM: $IMAGE_REF"
docker buildx build \
  --platform "$IMAGE_PLATFORM" \
  -f backend/Dockerfile \
  -t "$IMAGE_REF" \
  --push \
  .

echo "Ensuring Linux App Service plan exists..."
if ! az appservice plan show --name "$PLAN_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az appservice plan create \
    --name "$PLAN_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --is-linux \
    --sku "$APP_SERVICE_SKU" \
    --output none
fi

echo "Fetching ACR credentials..."
ACR_USERNAME="$(az acr credential show --name "$ACR_NAME" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)"

echo "Ensuring Web App exists..."
if ! az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az webapp create \
    --resource-group "$RESOURCE_GROUP" \
    --plan "$PLAN_NAME" \
    --name "$APP_NAME" \
    --deployment-container-image-name "$IMAGE_REF" \
    --output none
fi

echo "Configuring container settings..."
az webapp config container set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --container-image-name "$IMAGE_REF" \
  --container-registry-url "https://${ACR_NAME}.azurecr.io" \
  --container-registry-user "$ACR_USERNAME" \
  --container-registry-password "$ACR_PASSWORD" \
  --output none

echo "Configuring runtime app settings..."
az webapp config appsettings set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    WEBSITES_PORT=8000 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=false \
    STARTUP_COMMAND="$STARTUP_COMMAND" \
  --output none

echo "Restarting Web App..."
az webapp restart \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output none

APP_URL="https://${APP_NAME}.azurewebsites.net"
echo ""
echo "Deployment complete."
echo "App URL: $APP_URL"
echo "Health check: ${APP_URL}/health"
echo ""
echo "Next step: set real application secrets with"
echo "  ./set-backend-appsettings.sh $RESOURCE_GROUP $APP_NAME"
