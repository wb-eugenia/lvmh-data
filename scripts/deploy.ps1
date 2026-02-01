# Script de déploiement LVMH Pipeline sur Google Cloud Run (Docker V2)
# Usage: ./scripts/deploy.ps1

Write-Host "🚀 LVMH Voice-to-Tag: Déploiement Cloud Native (Docker)" -ForegroundColor Cyan

# Vérification de gcloud
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Error "❌ Commande 'gcloud' introuvable. Installez Google Cloud SDK."
    exit 1
}

# 1. Configuration du Projet
$currentProject = gcloud config get-value project 2>$null
if ([string]::IsNullOrWhiteSpace($currentProject)) {
    $PROJECT_ID = Read-Host -Prompt "Entrez votre Google Cloud PROJECT_ID"
    gcloud config set project $PROJECT_ID
} else {
    $PROJECT_ID = $currentProject
    Write-Host "✅ Projet détecté: $PROJECT_ID" -ForegroundColor Green
}

$SERVICE_NAME = "lvmh-voice-tag"
$REGION = "europe-west1"

# 2. Build de l'image Docker (Cloud Build)
Write-Host "`n📦 Construction de l'image Docker sur Google Cloud Build..." -ForegroundColor Yellow
$IMAGE_URI = "gcr.io/$PROJECT_ID/$SERVICE_NAME"
gcloud builds submit --tag $IMAGE_URI .

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Erreur lors du build Docker."
    exit 1
}

# 3. Déploiement sur Cloud Run
Write-Host "`n🚀 Déploiement du conteneur sur Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_URI `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 1Gi `
    --port 8080 `
    --set-env-vars "GROQ_API_KEY=RemplacerParVotreCle,MISTRAL_API_KEY=RemplacerParVotreCle"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ DÉPLOIEMENT TERMINÉ AVEC SUCCÈS !" -ForegroundColor Green
    Write-Host "🌍 Votre application est live sur l'URL ci-dessus."
} else {
    Write-Host "`n❌ Erreur lors du déploiement." -ForegroundColor Red
}
