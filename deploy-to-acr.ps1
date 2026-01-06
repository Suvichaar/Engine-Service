# Azure Container Registry Deployment Script (PowerShell)
# This script builds and pushes the Docker image to ACR

param(
    [string]$ImageTag = "latest"
)

# Configuration - UPDATE THESE VALUES
$ACR_NAME = "your-acr-name"  # Replace with your ACR name (e.g., "myregistry")
$IMAGE_NAME = "newsengine-backend"
$RESOURCE_GROUP = "your-resource-group"  # Replace with your resource group name

Write-Host "🚀 Starting deployment to Azure Container Registry..." -ForegroundColor Blue
Write-Host ""

# Check if Azure CLI is installed
try {
    $null = Get-Command az -ErrorAction Stop
} catch {
    Write-Host "❌ Azure CLI not found. Please install it first." -ForegroundColor Yellow
    Write-Host "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Check if Docker is installed
try {
    $null = Get-Command docker -ErrorAction Stop
} catch {
    Write-Host "❌ Docker not found. Please install it first." -ForegroundColor Yellow
    exit 1
}

# Login to Azure (if not already logged in)
Write-Host "🔐 Checking Azure login status..." -ForegroundColor Blue
try {
    $null = az account show 2>$null
} catch {
    Write-Host "⚠️  Not logged in to Azure. Logging in..." -ForegroundColor Yellow
    az login
}

# Login to ACR
Write-Host "🔐 Logging in to Azure Container Registry: $ACR_NAME..." -ForegroundColor Blue
az acr login --name $ACR_NAME

# Build Docker image
Write-Host ""
Write-Host "🏗️  Building Docker image: ${IMAGE_NAME}:${ImageTag}..." -ForegroundColor Blue
docker build -t "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${ImageTag}" .

# Push image to ACR
Write-Host ""
Write-Host "📤 Pushing image to ACR..." -ForegroundColor Blue
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${ImageTag}"

Write-Host ""
Write-Host "✅ Deployment successful!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Image location: ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${ImageTag}" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Blue
Write-Host "1. Update your Azure Container App to use this image"
Write-Host "2. Set environment variable: AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/"
Write-Host "3. Enable Managed Identity on your Container App"
Write-Host "4. Grant Key Vault access to the Container App's Managed Identity"
Write-Host ""
Write-Host "To deploy to Azure Container Apps, run:" -ForegroundColor Blue
Write-Host "az containerapp update \"
Write-Host "  --name your-app-name \"
Write-Host "  --resource-group $RESOURCE_GROUP \"
Write-Host "  --image ${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${ImageTag}"
