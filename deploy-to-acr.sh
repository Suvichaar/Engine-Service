#!/bin/bash

# Azure Container Registry Deployment Script
# This script builds and pushes the Docker image to ACR

set -e  # Exit on error

# Configuration - UPDATE THESE VALUES
ACR_NAME="your-acr-name"  # Replace with your ACR name (e.g., "myregistry")
IMAGE_NAME="newsengine-backend"
IMAGE_TAG="${1:-latest}"  # Use first argument as tag, default to "latest"
RESOURCE_GROUP="your-resource-group"  # Replace with your resource group name

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting deployment to Azure Container Registry...${NC}"
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${YELLOW}❌ Azure CLI not found. Please install it first.${NC}"
    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}❌ Docker not found. Please install it first.${NC}"
    exit 1
fi

# Login to Azure (if not already logged in)
echo -e "${BLUE}🔐 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Azure. Logging in...${NC}"
    az login
fi

# Login to ACR
echo -e "${BLUE}🔐 Logging in to Azure Container Registry: ${ACR_NAME}...${NC}"
az acr login --name $ACR_NAME

# Build Docker image
echo ""
echo -e "${BLUE}🏗️  Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}...${NC}"
docker build -t $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG .

# Push image to ACR
echo ""
echo -e "${BLUE}📤 Pushing image to ACR...${NC}"
docker push $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG

echo ""
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo -e "${GREEN}📍 Image location: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo ""
echo -e "${BLUE}📝 Next steps:${NC}"
echo "1. Update your Azure Container App to use this image"
echo "2. Set environment variable: AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/"
echo "3. Enable Managed Identity on your Container App"
echo "4. Grant Key Vault access to the Container App's Managed Identity"
echo ""
echo -e "${BLUE}To deploy to Azure Container Apps, run:${NC}"
echo "az containerapp update \\"
echo "  --name your-app-name \\"
echo "  --resource-group $RESOURCE_GROUP \\"
echo "  --image $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG"
