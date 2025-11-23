# Azure Container Registry (ACR) Deployment Guide

Complete guide for deploying FastAPI backend and Streamlit frontend to Azure using ACR and Container Apps.

## 📋 Prerequisites

1. **Azure Account** with active subscription
2. **Azure CLI** installed and logged in
3. **Docker** installed locally
4. **ACR** (Azure Container Registry) created

## 🏗️ Architecture

```
┌─────────────────┐
│  ACR Registry   │
│  (Container     │
│   Images)       │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌───▼────┐
│Backend│ │Frontend│
│Container│ │Container│
│  App   │ │  App   │
└────────┘ └────────┘
```

## 🚀 Step-by-Step Deployment

### Step 1: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="newslab-rg"
LOCATION="eastus"
ACR_NAME="newslabacr"  # Must be globally unique, lowercase only
ENV_NAME="newslab-env"

# Login to Azure
az login

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create ACR (Basic tier - $5/month)
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
```

### Step 2: Build and Push Backend Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build backend image
docker build -t $ACR_NAME.azurecr.io/newslab-backend:latest .

# Push to ACR
docker push $ACR_NAME.azurecr.io/newslab-backend:latest

# Verify
az acr repository list --name $ACR_NAME --output table
```

### Step 3: Build and Push Frontend Image

```bash
# Build frontend image
docker build -f Dockerfile.streamlit -t $ACR_NAME.azurecr.io/newslab-frontend:latest .

# Push to ACR
docker push $ACR_NAME.azurecr.io/newslab-frontend:latest

# Verify
az acr repository show-tags --name $ACR_NAME --repository newslab-frontend --output table
```

### Step 4: Create Container Apps Environment

```bash
# Create Container Apps environment
az containerapp env create \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)
```

### Step 5: Deploy Backend (FastAPI)

```bash
# Deploy backend container app
az containerapp create \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/newslab-backend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --env-vars \
    "DATABASE_URL=postgresql://user:pass@host:5432/db" \
    "AWS_ACCESS_KEY=your-key" \
    "AWS_SECRET_KEY=your-secret" \
    "AWS_REGION=us-east-1" \
    "AWS_BUCKET=your-bucket" \
    "AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/" \
    "AZURE_OPENAI_API_KEY=your-key" \
    "AZURE_OPENAI_DEPLOYMENT=your-deployment" \
    "AZURE_OPENAI_API_VERSION=2024-02-15-preview"

# Get backend URL
BACKEND_URL=$(az containerapp show \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)
echo "Backend URL: https://$BACKEND_URL"
```

### Step 6: Deploy Frontend (Streamlit)

```bash
# Deploy frontend container app
az containerapp create \
  --name newslab-frontend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image $ACR_NAME.azurecr.io/newslab-frontend:latest \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8501 \
  --ingress external \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 2 \
  --env-vars \
    "FASTAPI_BASE_URL=https://$BACKEND_URL"

# Get frontend URL
FRONTEND_URL=$(az containerapp show \
  --name newslab-frontend \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)
echo "Frontend URL: https://$FRONTEND_URL"
```

## 🔧 Update Environment Variables

### Update Backend Environment Variables

```bash
az containerapp update \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    "KEY1=value1" \
    "KEY2=value2"
```

### Update Frontend Environment Variables

```bash
az containerapp update \
  --name newslab-frontend \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    "FASTAPI_BASE_URL=https://new-backend-url"
```

## 🔄 Update Images (Redeploy)

```bash
# Rebuild and push
docker build -t $ACR_NAME.azurecr.io/newslab-backend:latest .
docker push $ACR_NAME.azurecr.io/newslab-backend:latest

# Restart container app to pull new image
az containerapp update \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_NAME.azurecr.io/newslab-backend:latest
```

## 📊 Monitoring

### View Logs

```bash
# Backend logs
az containerapp logs show \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --follow

# Frontend logs
az containerapp logs show \
  --name newslab-frontend \
  --resource-group $RESOURCE_GROUP \
  --follow
```

### View Metrics

```bash
# List container apps
az containerapp list --resource-group $RESOURCE_GROUP --output table

# Get details
az containerapp show \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --query properties.template.scale
```

## 🗑️ Cleanup

```bash
# Delete container apps
az containerapp delete \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --yes

az containerapp delete \
  --name newslab-frontend \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete environment
az containerapp env delete \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete ACR (optional)
az acr delete \
  --name $ACR_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete resource group (deletes everything)
az group delete --name $RESOURCE_GROUP --yes
```

## 🔐 Security Best Practices

### 1. Use Azure Key Vault for Secrets

```bash
# Create Key Vault
az keyvault create \
  --name newslab-kv \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Store secrets
az keyvault secret set \
  --vault-name newslab-kv \
  --name "aws-access-key" \
  --value "your-key"

# Reference in Container App
az containerapp update \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    "AWS_ACCESS_KEY=secretref:aws-access-key"
```

### 2. Enable Managed Identity

```bash
# Enable managed identity for Container App
az containerapp identity assign \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --system-assigned
```

### 3. Use Private Endpoints (for production)

```bash
# Create private endpoint for ACR
az network private-endpoint create \
  --name acr-pe \
  --resource-group $RESOURCE_GROUP \
  --vnet-name your-vnet \
  --subnet your-subnet \
  --private-connection-resource-id $(az acr show --name $ACR_NAME --query id --output tsv) \
  --connection-name acr-connection \
  --group-id registry
```

## 💰 Cost Estimation

### Basic Setup (Development)
- **ACR Basic**: ~$5/month
- **Container Apps Environment**: ~$0.000012/vCPU-second
- **Backend (1 vCPU, 2GB RAM)**: ~$30-50/month
- **Frontend (0.5 vCPU, 1GB RAM)**: ~$15-25/month
- **Total**: ~$50-80/month

### Production Setup
- **ACR Standard**: ~$25/month
- **Backend (2 vCPU, 4GB RAM, auto-scale)**: ~$100-200/month
- **Frontend (1 vCPU, 2GB RAM)**: ~$50-100/month
- **Total**: ~$175-325/month

## 🚨 Troubleshooting

### Image Pull Errors

```bash
# Check ACR credentials
az acr credential show --name $ACR_NAME

# Verify image exists
az acr repository show-tags --name $ACR_NAME --repository newslab-backend
```

### Container App Not Starting

```bash
# Check logs
az containerapp logs show \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --tail 100

# Check revision
az containerapp revision list \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP
```

### Health Check Failing

```bash
# Test health endpoint
curl https://$BACKEND_URL/health

# Check container app health
az containerapp show \
  --name newslab-backend \
  --resource-group $RESOURCE_GROUP \
  --query properties.runningStatus
```

## 📝 Quick Reference Commands

```bash
# List all container apps
az containerapp list --resource-group $RESOURCE_GROUP --output table

# Get URLs
az containerapp show --name newslab-backend --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn --output tsv

# Scale manually
az containerapp update --name newslab-backend --resource-group $RESOURCE_GROUP --min-replicas 2 --max-replicas 5

# Restart
az containerapp revision restart --name newslab-backend --resource-group $RESOURCE_GROUP --revision <revision-name>
```

## ✅ Deployment Checklist

- [ ] ACR created and accessible
- [ ] Backend image built and pushed
- [ ] Frontend image built and pushed
- [ ] Container Apps environment created
- [ ] Backend deployed with all environment variables
- [ ] Frontend deployed with backend URL
- [ ] Health checks passing
- [ ] Logs accessible
- [ ] URLs working
- [ ] Test story generation end-to-end

## 🎯 Next Steps

1. Set up CI/CD pipeline (GitHub Actions)
2. Configure auto-scaling policies
3. Set up monitoring and alerts
4. Configure custom domains
5. Enable HTTPS/TLS
6. Set up backup and disaster recovery

