# Azure Container Registry (ACR) Deployment Guide

This guide explains how to deploy the NewsEngine backend to Azure Container Registry and use Azure Key Vault for secure secret management.

## Prerequisites

1. **Azure CLI** installed and configured
   ```bash
   # Install Azure CLI
   # Windows: https://aka.ms/installazurecliwindows
   # Mac/Linux: https://aka.ms/installazureclilinux
   
   # Login to Azure
   az login
   ```

2. **Docker** installed and running
   ```bash
   # Verify Docker is running
   docker --version
   ```

3. **Azure Resources**:
   - Azure Container Registry (ACR)
   - Azure Key Vault
   - Azure Container Apps (for hosting)

## Step 1: Create Azure Key Vault

```bash
# Set variables
RESOURCE_GROUP="your-resource-group"
KEYVAULT_NAME="your-keyvault-name"  # Must be globally unique
LOCATION="eastus"

# Create resource group (if not exists)
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Key Vault
az keyvault create \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --enable-rbac-authorization false  # Use access policies (easier for setup)
```

## Step 2: Add Secrets to Key Vault

Add all your application secrets to Key Vault:

```bash
# Azure OpenAI
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-openai-endpoint" --value "https://your-openai.openai.azure.com/"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-openai-api-key" --value "your-api-key"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-openai-deployment" --value "gpt-4"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-openai-api-version" --value "2024-02-15-preview"

# AI Image (DALL-E)
az keyvault secret set --vault-name $KEYVAULT_NAME --name "ai-image-endpoint" --value "https://your-dalle.openai.azure.com/"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "ai-image-api-key" --value "your-api-key"

# Pexels
az keyvault secret set --vault-name $KEYVAULT_NAME --name "pexels-api-key" --value "your-pexels-api-key"

# Azure Speech
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-speech-key" --value "your-speech-key"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-speech-region" --value "eastus"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "voice-name" --value "en-US-AriaNeural"

# Azure Document Intelligence
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-di-endpoint" --value "https://your-di.cognitiveservices.azure.com/"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "azure-di-key" --value "your-di-key"

# AWS (if using)
az keyvault secret set --vault-name $KEYVAULT_NAME --name "aws-access-key" --value "your-aws-access-key"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "aws-secret-key" --value "your-aws-secret-key"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "aws-region" --value "ap-south-1"
az keyvault secret set --vault-name $KEYVAULT_NAME --name "aws-bucket" --value "your-bucket-name"
```

## Step 3: Build and Push Docker Image to ACR

### Option A: Using the deployment script (Linux/Mac)

```bash
# Make script executable
chmod +x deploy-to-acr.sh

# Update the script with your ACR name and resource group
# Then run:
./deploy-to-acr.sh latest
```

### Option B: Using the deployment script (Windows PowerShell)

```powershell
# Update the script with your ACR name and resource group
# Then run:
.\deploy-to-acr.ps1 -ImageTag latest
```

### Option C: Manual deployment

```bash
# Set variables
ACR_NAME="your-acr-name"
IMAGE_NAME="newsengine-backend"
IMAGE_TAG="latest"

# Login to ACR
az acr login --name $ACR_NAME

# Build image
docker build -t $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG .

# Push image
docker push $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG
```

## Step 4: Deploy to Azure Container Apps

### 4.1 Create Container App (if not exists)

```bash
# Set variables
APP_NAME="newsengine-backend"
ENVIRONMENT_NAME="newsengine-env"
ACR_NAME="your-acr-name"
IMAGE_NAME="newsengine-backend"
IMAGE_TAG="latest"
KEYVAULT_NAME="your-keyvault-name"
RESOURCE_GROUP="your-resource-group"

# Create Container Apps environment
az containerapp env create \
  --name $ENVIRONMENT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location eastus

# Create Container App
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT_NAME \
  --image $ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG \
  --registry-server $ACR_NAME.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 3
```

### 4.2 Enable Managed Identity

```bash
# Enable system-assigned managed identity
az containerapp identity assign \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --system-assigned
```

### 4.3 Grant Key Vault Access

```bash
# Get the Container App's managed identity principal ID
PRINCIPAL_ID=$(az containerapp identity show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant access to Key Vault
az keyvault set-policy \
  --name $KEYVAULT_NAME \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

### 4.4 Set Environment Variable

```bash
# Set only the Key Vault URL - all other secrets will be loaded from Key Vault
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars AZURE_KEYVAULT_URL="https://${KEYVAULT_NAME}.vault.azure.net/"
```

## Step 5: Verify Deployment

```bash
# Get the Container App URL
az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn -o tsv

# Test the health endpoint
curl https://<your-app-url>/health
```

## Troubleshooting

### Issue: AIImageProvider not initializing

**Solution**: Check that secrets are correctly named in Key Vault:
- `ai-image-endpoint`
- `ai-image-api-key`

Verify in Container App logs:
```bash
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow
```

### Issue: Key Vault access denied

**Solution**: Verify Managed Identity has access:
```bash
# Check identity
az containerapp identity show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Re-grant access
PRINCIPAL_ID=$(az containerapp identity show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az keyvault set-policy \
  --name $KEYVAULT_NAME \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

### Issue: Secrets not loading

**Solution**: 
1. Verify `AZURE_KEYVAULT_URL` environment variable is set
2. Check Container App logs for Key Vault errors
3. Ensure secret names match the mapping in `azure_keyvault.py`

## Secret Name Mapping

The following Key Vault secret names are supported:

| Key Vault Secret Name | Config Section | Config Key |
|----------------------|----------------|------------|
| `azure-openai-endpoint` | `azure_api` | `endpoint` |
| `azure-openai-api-key` | `azure_api` | `api_key` |
| `azure-openai-deployment` | `azure_api` | `deployment` |
| `azure-openai-api-version` | `azure_api` | `api_version` |
| `ai-image-endpoint` | `ai_image` | `endpoint` |
| `ai-image-api-key` | `ai_image` | `api_key` |
| `pexels-api-key` | `pexels` | `api_key` |
| `azure-speech-key` | `azure_speech` | `api_key` |
| `azure-speech-region` | `azure_speech` | `region` |
| `voice-name` | `azure_speech` | `voice_name` |
| `azure-di-endpoint` | `azure_di` | `endpoint` |
| `azure-di-key` | `azure_di` | `api_key` |
| `aws-access-key` | `aws` | `access_key` |
| `aws-secret-key` | `aws` | `secret_key` |
| `aws-region` | `aws` | `region` |
| `aws-bucket` | `aws` | `bucket` |
| ... and more (see `app/config/azure_keyvault.py`) |

## Benefits

✅ **Secure**: Secrets stored in Azure Key Vault, not in code or environment variables  
✅ **Centralized**: All secrets managed in one place  
✅ **Automatic**: Managed Identity handles authentication automatically  
✅ **Auditable**: Key Vault provides audit logs for secret access  
✅ **Versioned**: Key Vault supports secret versioning  

## Next Steps

1. Set up monitoring and alerts
2. Configure auto-scaling based on traffic
3. Set up CI/CD pipeline for automated deployments
4. Configure custom domain and SSL certificate

