# Script de déploiement LVMH Pipeline sur Google Cloud Run (Docker V2)
# Usage: ./scripts/deploy.ps1

Write-Host "[INFO] LVMH Data API: Deploiement Cloud Native (Docker)" -ForegroundColor Cyan

# Vérification de gcloud
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Commande 'gcloud' introuvable. Installez Google Cloud SDK."
    exit 1
}

# 1. Configuration du Projet
$currentProject = gcloud config get-value project 2>$null
if ([string]::IsNullOrWhiteSpace($currentProject)) {
    $PROJECT_ID = Read-Host -Prompt "Entrez votre Google Cloud PROJECT_ID"
    gcloud config set project $PROJECT_ID
} else {
    $PROJECT_ID = $currentProject
    Write-Host "[OK] Projet detecte: $PROJECT_ID" -ForegroundColor Green
}

$SERVICE_NAME = "lvmh-api"
$REGION = "europe-west9"

# Load environment variables from .env file
$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, [EnvironmentVariableTarget]::Process)
        }
    }
    Write-Host "[OK] Variables d'environnement chargees" -ForegroundColor Green
}

# Get API keys from environment
$MISTRAL_KEY = $env:MISTRAL_API_KEY
$OPENAI_KEY = $env:OPENAI_API_KEY

if ([string]::IsNullOrWhiteSpace($MISTRAL_KEY)) {
    Write-Host "[ERROR] MISTRAL_API_KEY non trouvee dans .env" -ForegroundColor Red
    exit 1
}

# 2. Build de l'image Docker (Cloud Build)
Write-Host "`n[INFO] Construction de l'image Docker sur Google Cloud Build..." -ForegroundColor Yellow
$IMAGE_URI = "gcr.io/$PROJECT_ID/$SERVICE_NAME"
gcloud builds submit --tag $IMAGE_URI . --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Erreur lors du build Docker."
    exit 1
}

# 3. Déploiement sur Cloud Run
Write-Host "`n[INFO] Deploiement du conteneur sur Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_URI `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 2Gi `
    --port 8080 `
    --set-env-vars "MISTRAL_API_KEY=$MISTRAL_KEY,LVMH_USE_ZVEC=true,OPENAI_API_KEY=$OPENAI_KEY,use_langextract_tier2=true,USE_CLOUD_SQL=true,CLOUD_SQL_CONNECTION_NAME=$PROJECT_ID:$REGION:lvmh-pipeline-prod,DB_USER=lvmh_app" `
    --add-cloudsql-instances "$PROJECT_ID:$REGION:lvmh-pipeline-prod" `
    --project=$PROJECT_ID

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] DEPLOIEMENT TERMINE AVEC SUCCES !" -ForegroundColor Green
    Write-Host "[INFO] Votre application est live sur l'URL ci-dessus."
} else {
    Write-Host "`n[ERROR] Erreur lors du deploiement." -ForegroundColor Red
}
