# Script de déploiement LVMH Pipeline sur Google Cloud Run (Docker V2)
# Usage: ./scripts/deploy.ps1

Write-Host "[INFO] LVMH Voice-to-Tag: Deploiement Cloud Native (Docker)" -ForegroundColor Cyan

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

$SERVICE_NAME = "lvmh-voice-tag"
$REGION = "europe-west1"

# 2. Build de l'image Docker (Cloud Build)
Write-Host "`n[INFO] Construction de l'image Docker sur Google Cloud Build..." -ForegroundColor Yellow
$IMAGE_URI = "gcr.io/$PROJECT_ID/$SERVICE_NAME"
gcloud builds submit --tag $IMAGE_URI .

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
    --memory 1Gi `
    --port 8080 `
    --set-env-vars "GROQ_API_KEY=RemplacerParVotreCle,MISTRAL_API_KEY=RemplacerParVotreCle"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] DEPLOIEMENT TERMINE AVEC SUCCES !" -ForegroundColor Green
    Write-Host "[INFO] Votre application est live sur l'URL ci-dessus."
} else {
    Write-Host "`n[ERROR] Erreur lors du deploiement." -ForegroundColor Red
}
