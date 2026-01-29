# 🗺️ Roadmap V3: Vision & Futur (2026-2027)

> **Ambition** : Passer d'un "Pipeline Batch" performant à une **Plateforme d'Intelligence Client Temps Réel**, 100% intégrée à l'écosystème LVMH (GCP) et poussant les limites de l'IA (Multimodal, Edge).

---

## ☁️ 1. Architecture Cloud-Native (GCP Integration)
*Objectif : Scalabilité infinie et intégration Data Warehouse.*

- [ ] **Serverless Deployment (Cloud Run)** 🚀
    - Conteneurisation Docker du pipeline.
    - Déploiement sur **Google Cloud Run** pour un auto-scaling (0 à 1000 instances) et facturation à l'usage.
- [ ] **Data Warehouse (BigQuery)** 🗄️
    - Export automatique des tags structurés vers BigQuery.
    - Création de Dashboards **Looker Studio** (ex: *Top Produits demandés par les VIC en temps réel*).
- [ ] **Event-Driven Architecture (Pub/Sub)** ⚡
    - Passage du Batch au **Streaming**. Traitement de la note vocale en < 5 secondes via des triggers Google Pub/Sub à la réception du fichier audio.

## 🧠 2. Advanced AI & RAG
*Objectif : Précision chirurgicale et connaissances métier.*

- [ ] **Product Matching RAG (Vector DB)** 🛍️
    - **Problème** : L'IA extrait "Sac noir".
    - **Solution** : Connecter un **RAG (Retrieval-Augmented Generation)** sur le catalogue produit LVMH (Vector Search).
    - **Résultat** : L'IA identifie le SKU exact : *Capucines BB Taurillon Noir (M58700)*.
- [ ] **Fine-Tuning "LVMH-Mistral"** 🎨
    - Entraînement d'un modèle SLM (Small Language Model) spécifique sur le corpus LVMH.
    - Compréhension native du jargon maison, des collections passées et de la "Tonalité Maison".
- [ ] **Multimodalité (Image-to-Text)** 📸
    - Support des photos jointes aux notes vocales (ex: photo d'un magazine).
    - Utilisation de **Pixtral / GPT-4o** pour extraire les références visuelles.

## 🛡️ 3. Privacy & Security (State-of-the-Art)
*Objectif : Confidentialité absolue par design.*

- [ ] **Edge AI (On-Device)** 📱
    - Faire tourner le modèle de nettoyage PII (Anonymisation) directement sur l'iPad du vendeur.
    - **Garantie** : Les données identifiantes ne quittent *jamais* l'appareil, même cryptées.
- [ ] **Vertex AI Private Endpoint** 🔒
    - S'assurer que le trafic vers les LLM reste 100% interne au VPC Google Cloud de LVMH (Pas d'internet public).

## 👩‍💻 4. Experience Vendeur (UX)
*Objectif : Adoption massive par les Client Advisors.*

- [ ] **Gamification "Data Quality"** 🏆
    - Score de qualité pour chaque note dictée.
    - Challenge entre boutiques pour les meilleures remontées d'informations (« Pépite du mois »).
- [ ] **Feedback Loop "Human-in-the-loop"** 🤝
    - Interface de validation simplifiée pour les notes à faible confiance (<70%).
    - Les corrections des vendeurs ré-entraînent automatiquement le Smart Router en continu.

## 📈 Synthèse des Phases

| Phase | Focus | Technologies Clés | Statut |
|-------|-------|-------------------|--------|
| **V1** | POC | OpenAI, Scripts Python | 🏁 Terminé |
| **V2** | **Production (Actuel)** | **Mistral, Async Batch, PII Local** | ✅ **DEPLOYED** |
| **V3** | **Scale (Futur)** | **GCP (Cloud Run/BigQuery), RAG, Edge AI** | 🚧 Planned |

---
*Document de Vision Stratégique - LVMH Data Office*
