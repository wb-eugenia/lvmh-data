# 🚀 Lancement du Déploiement GCP

Tout est prêt pour le déploiement sur Google Cloud.

## Étapes pour déployer :

1.  **Ouvrez un terminal** dans ce dossier.
2.  **Exécutez le script** PowerShell suivant :
    ```powershell
    .\scripts\deploy.ps1
    ```

## Ce que va faire le script :
1.  Vous demander votre **ID de Projet Google Cloud** (si pas configuré).
2.  Envoyer le code sur **Google Cloud Build** pour créer l'image Docker.
3.  Déployer l'image sur **Cloud Run** (Service : `lvmh-voice-tag`).
4.  Afficher l'**URL HTTPS** de votre application en ligne.

> **Note**: Assurez-vous d'avoir `gcloud` installé et d'être authentifié (`gcloud auth login`).
