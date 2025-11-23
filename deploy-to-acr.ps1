# PowerShell script for ACR deployment (Windows)

param(
    [string]$ResourceGroup = "newslab-rg",
    [string]$AcrName = "newslabacr",
    [string]$EnvName = "newslab-env"
)

Write-Host "🚀 Starting ACR Deployment..." -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroup"
Write-Host "ACR Name: $AcrName"
Write-Host "Environment: $EnvName"
Write-Host ""

# Check if ACR exists
try {
    az acr show --name $AcrName --resource-group $ResourceGroup | Out-Null
} catch {
    Write-Host "❌ ACR not found. Please create it first:" -ForegroundColor Red
    Write-Host "   az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic" -ForegroundColor Yellow
    exit 1
}

# Login to ACR
Write-Host "📦 Logging in to ACR..." -ForegroundColor Cyan
az acr login --name $AcrName

# Build and push backend
Write-Host "🔨 Building backend image..." -ForegroundColor Cyan
docker build -t "${AcrName}.azurecr.io/newslab-backend:latest" .

Write-Host "📤 Pushing backend image..." -ForegroundColor Cyan
docker push "${AcrName}.azurecr.io/newslab-backend:latest"

# Build and push frontend
Write-Host "🔨 Building frontend image..." -ForegroundColor Cyan
docker build -f Dockerfile.streamlit -t "${AcrName}.azurecr.io/newslab-frontend:latest" .

Write-Host "📤 Pushing frontend image..." -ForegroundColor Cyan
docker push "${AcrName}.azurecr.io/newslab-frontend:latest"

Write-Host "✅ Images pushed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Deploy backend: See ACR_DEPLOYMENT_GUIDE.md Step 5"
Write-Host "2. Deploy frontend: See ACR_DEPLOYMENT_GUIDE.md Step 6"

