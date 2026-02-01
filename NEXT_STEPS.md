# Prochaines Étapes : Déploiement GCP 🚀

L'application est entièrement prête pour le Cloud (Docker & Kubernetes/Cloud Run).

## 1. Lancer le Déploiement
Exécutez simplement le script PowerShell fourni :
```powershell
.\scripts\deploy.ps1
```

## 2. Ce qu'il va se passer :
- **Authentification** : Le script vérifiera votre connexion `gcloud`.
- **Configuration** : Il vous demandera votre `PROJECT_ID` Google Cloud.
- **Build** : Il enverra le code à **Cloud Build** pour créer l'image Docker distante.
- **Deploy** : Il déploiera le service sur **Cloud Run** (Region: `europe-west1`).

## 3. Accès
Une fois terminé, le script affichera l'URL sécurisée (HTTPS) de votre application.

---
**Note** : Assurez-vous que l'API **Cloud Run** et **Cloud Build** sont activées sur votre projet GCP.
