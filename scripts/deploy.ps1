# Script de déploiement LVMH Pipeline sur Google Cloud Run
# Usage: ./scripts/deploy.ps1

Write-Host "🚀 Début du déploiement vers GCP (Cloud Run)..." -ForegroundColor Cyan

# Vérification de gcloud
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Error "❌ Commande 'gcloud' introuvable. Veuillez installer Google Cloud SDK et redémarrer le terminal."
    exit 1
}

# 1. Configuration du projet (Optionnel, décommentez si besoin)
# gcloud config set project VOTRE_PROJET_ID

# 2. Déploiement
# Note: On utilise les backticks (`) pour le multiline en PowerShell
gcloud run deploy lvmh-pipeline `
    --source . `
    --region europe-west9 `
    --allow-unauthenticated `
    --port 8080

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Déploiement terminé avec succès !" -ForegroundColor Green
} else {
    Write-Host "`n❌ Erreur lors du déploiement." -ForegroundColor Red
}
