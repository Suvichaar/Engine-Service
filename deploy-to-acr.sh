#!/bin/bash
# Quick deployment script for ACR

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-newslab-rg}"
ACR_NAME="${ACR_NAME:-newslabacr}"
ENV_NAME="${ENV_NAME:-newslab-env}"

echo "🚀 Starting ACR Deployment..."
echo "Resource Group: $RESOURCE_GROUP"
echo "ACR Name: $ACR_NAME"
echo "Environment: $ENV_NAME"
echo ""

# Check if ACR exists
if ! az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &>/dev/null; then
    echo "❌ ACR not found. Please create it first:"
    echo "   az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic"
    exit 1
fi

# Login to ACR
echo "📦 Logging in to ACR..."
az acr login --name $ACR_NAME

# Build and push backend
echo "🔨 Building backend image..."
docker build -t $ACR_NAME.azurecr.io/newslab-backend:latest .

echo "📤 Pushing backend image..."
docker push $ACR_NAME.azurecr.io/newslab-backend:latest

# Build and push frontend
echo "🔨 Building frontend image..."
docker build -f Dockerfile.streamlit -t $ACR_NAME.azurecr.io/newslab-frontend:latest .

echo "📤 Pushing frontend image..."
docker push $ACR_NAME.azurecr.io/newslab-frontend:latest

echo "✅ Images pushed successfully!"
echo ""
echo "Next steps:"
echo "1. Deploy backend: See ACR_DEPLOYMENT_GUIDE.md Step 5"
echo "2. Deploy frontend: See ACR_DEPLOYMENT_GUIDE.md Step 6"

