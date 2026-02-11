# Documentation Technique Ultra-Détaillée : LVMH Voice-to-Tag Pipeline 👜 ✨

## 📝 1. Introduction & Vision Stratégique
Le **LVMH Voice-to-Tag Pipeline** est une infrastructure cognitive conçue pour combler le fossé entre l'expérience client en boutique (donnée non structurée) et l'intelligence CRM (donnée structurée). Dans un contexte de luxe, la qualité de la saisie par les Client Advisors (CA) est souvent entravée par le manque de temps. Cette pipeline automatise l'extraction de insights critiques tout en préservant la souveraineté des données et en injectant une couche de gamification pour stimuler l'adoption terrain.

---

## ⚙️ 2. Architecture Technique et Flux de Données

Le système repose sur une architecture "Event-Driven" asynchrone, optimisée pour le traitement par lots (Batch) et le temps réel.

### 2.1 Étape 1 : Data Cleaning & Normalisation (Pre-processing)
Le nettoyage ne se limite pas à la suppression d'espaces. Il s'agit d'une normalisation sémantique profonde :
- **Normalisation Multilingue** : Utilisation de dictionnaires de "Pure Fillers" (euh, alors, donc, basically, you know) pour réduire le bruit.
- **Dédoublonnage Sémantique** : Identification et suppression des répétitions bégayées (ex: "je je cherche un sac sac") via des algorithmes de type N-grams.
- **Protection des Zones (Placeholders)** : Les entités comme les codes produits (LVMH-SKU-123) ou les montants (4500€) sont temporairement remplacées par des jetons `{PROTECTED_0}` pour éviter que le nettoyage sémantique ne les corrompe.
- **Anonymisation PII de Surface** : 
    - **Emails** : Masking via Regex `[A-Z0-9._%+-]+@[...].com`.
    - **Phones** : Détection des formats internationaux (+33, 0033) et français.
    - **Noms Propres** : Algorithme basé sur les civilités et les majuscules adjacentes.

### 2.2 Étape 2 : Smart Routing & Complexité ML
Le composant `SmartRouterV3` agit comme un trieur de courrier intelligent. Il évalue la "complexité cognitive" d'une note sur une échelle de 0 à 100.

| Dimension | Poids | Description |
| :--- | :--- | :--- |
| **Complexité Textuelle** | 30 pts | Longueur de la note et diversité du vocabulaire. |
| **Qualité Linguistique** | 20 pts | Ratio fillers/mots utiles et structure grammaticale. |
| **Criticité Business** | 25 pts | Présence de mots-clés stratégiques (VIC, VIP, Plainte, Urgent). |
| **Intention ML** | 15 pts | Classification de l'intention (Achat, Cadeau, SAV). |
| **Risques RGPD** | 10 pts | Détection de thèmes sensibles nécessitant un traitement spécial. |

**Mécanisme de Routage Hybrid :**
Le router utilise d'abord une approche heuristique (Scoring Engine), puis valide la décision via un modèle **Random Forest** (entrainé en local via `sklearn`). Si la confiance ML est > 0.85, la décision est validée automatiquement. Sinon, on suit les seuils :
- **Tier 1 (<25)** : Règles Regex strictes. Coût : 0€. Vitesse : <10ms.
- **Tier 2 (25-75)** : Mistral Balanced (7B/12B). Le "Workhorse" de la pipeline.
- **Tier 3 (>75)** : Mistral Large (premium). Pour les notes longues ou stratégiques.

### 2.3 Étape 3 : Extraction Multi-Piliers (Taxonomie LVMH V2)
L'extraction transforme le texte en un objet JSON structuré selon les 4 piliers fondamentaux définis par le Data Office :

#### Pilier 1 : Univers Produit
- **Catégories** : Maroquinerie, Horlogerie, Joaillerie, Prêt-à-porter.
- **Style & Usage** : Casual, Soirée, Travail, Voyage.
- **Préférences Détails** : Couleurs favorites, types de cuir, finitions métal.

#### Pilier 2 : Profil Client
- **Purchase Context** : Nouveau client, Prospect chaud, Fidèle.
- **Socio-Pro** : Secteur d'activité, centre d'intérêts (Golf, Art, Mode).
- **Statut** : Client occasionnel vs VIC (Very Important Client).

#### Pilier 3 : Hospitalité & Care
- **Occasions** : Anniversaire, Mariage, Célébration professionnelle.
- **Allergies/Restricions** : Santé sémantique (Allergie nickel, gluten) - crucial pour le retail de luxe.

#### Pilier 4 : Action Business
- **NBA (Next Best Action)** : Recommandation générée par le `RecommenderEngine`.
- **Urgence** : Date butoir pour un cadeau ou une relance.

### 2.4 Étape 4 : RAG (Retrieval-Augmented Generation)
Le `ProductMatcher` connecte les désirs flous à la réalité du catalogue.
- **Indexing** : Utilisation de `SentenceTransformers` (`paraphrase-multilingual-MiniLM-L12-v2`) pour transformer 50,000 références produits en vecteurs.
- **Querying** : Quand un client dit "un sac bleu élégant", le RAG cherche les 3 produits les plus proches dans l'espace vectoriel.
- **Validation** : Seul un score de similarité cosinus > 0.40 permet un appariement automatique dans le CRM.

### 2.5 Étape 5 : Recommandation & Gamification
- **NBA Engine** : Un moteur de règles métier croise le pilier 3 (Occasion) et le pilier 1 (Produits matchés) pour suggérer : *"Appeler le client pour son anniversaire et proposer le Sac Capucines matché."*
- **Gamification (Super Note Score)** :
  - Chaque note reçoit un score de 0 à 100 sur sa qualité.
  - La détection d'une allergie ou d'une occasion spéciale donne un bonus de +20 pts.
  - Ces points sont intégrés dans un leaderboard Advisor pour stimuler la collecte de données.

---

## 💻 3. Infrastructure & Performance

### 3.1 Benchmarks de Performance (Dataset 400 notes)
| Métrique | Valeur | Commentaires |
| :--- | :--- | :--- |
| **Latence Moyenne** | 1.2s | Temps du cycle complet (Cleaning -> RAG). |
| **Throughput Max** | 45 notes/min | Limité par les Rate Limits Mistral API. |
| **Précision Tier 1** | 88% | Sur les notes courtes et formatées. |
| **Précision Tier 2** | 96% | Sur la taxonomie complexe. |
| **Coût Moyen** | 0.0004€ / note | Mix Tier 1/2/3 optimisé. |

### 3.2 Stack Technologique
- **Backend** : Python 3.10+, FastAPI (Asynchrone).
- **IA/LLM** : Mistral AI (Tier 2/3 extraction), OpenAI (Whisper + RGPD contextuel), HuggingFace (Local NER).
- **Vector DB** : Local Pickle/FAISS Index (lv_index.pkl).
- **Frontend** : React.js, Vite, TailwindCSS, Lucide Icons.
- **DevOps** : Docker, Docker-Compose, scripts PowerShell de déploiement.

---

## 🔒 4. Sécurité & Conformité RGPD

### 4.1 Stratégie de Protection
LVMH Data Office impose une politique de "Privacy by Design" :
1. **Anonymisation en Amont** : Aucune donnée PII (nom, tel) n'est envoyée aux LLM dans le Tier 2/3.
2. **Détection du Risque** : Le Tier 2 scanne spécifiquement les "Risques RGPD" (Article 9 : opinions politiques, santé mentale). Si détecté, la note est immédiatement nettoyée ou supprimée.
3. **Souveraineté** : Utilisation prioritaire de Mistral AI hébergé en Europe pour garantir que les données ne sortent pas de la juridiction EU.

---

## 🚀 5. Roadmap & Evolutions Futures (Vision 2026)

### Court Terme (Q1 2026)
- **Fuzzy Regex Engine** : Intégration de `RapidFuzz` dans le Tier 1 pour gérer les fautes de frappe sans passer au Tier 2 (économie de coût de ~30%).
- **NER SpaCy Local** : Remplacer l'anonymisation Regex par un modèle NLP `fr_core_news_lg` pour une détection des entités nommées plus précise.

### Moyen Terme (Q2 2026)
- **Déploiement GCP (Cloud Run)** : Passage à une infrastructure sans serveur pour gérer des pics de charge saisonniers (Noël, Fashion Week).
- **Multi-Brand Support** : Adaptation de la taxonomie (Piliers) pour s'adapter dynamiquement à chaque Maison (Louis Vuitton, Dior, Givenchy).

### Long Terme (2026+)
- **Speech-to-Text Intégré** : Couche Whisper fine-tunée sur le lexique LVMH (termes techniques cuir, noms de collections spécifiques).
- **Feedback Loop Automatisée** : Le système se ré-entraîne chaque semaine sur les notes ayant nécessité une correction manuelle par les managers.

---

## 🛠️ 6. Guide d'Installation & Maintenance

### 6.1 Pré-requis
- **Docker Desktop** (recommandé).
- **Python 3.10** (si installe locale).
- **Clés API** : Mistral, OpenAI.

### 6.2 Démarrage Rapide
```bash
# 1. Cloner et configurer
cp .env.example .env

# 2. Lancer l'infrastructure (API + DB + UI)
docker-compose up --build -d

# 3. Vérifier les logs
docker logs -f lvmh-api
```

### 6.3 Maintenance du Cache & Index
- **Nettoyage Cache** : `python scripts/clear_cache.py` (Recommandé avant chaque nouveau batch de test).
- **Reconstruction Index RAG** : `python scripts/build_vector_store.py` (À faire après chaque mise à jour du catalogue produit).
- **Training ML Router** : `python -c "from src.smart_router import SmartRouterV3; SmartRouterV3().train_model()"`

### 6.4 Troubleshooting
- **Erreur `invalid_api_key`** : Vérifier le quota Mistral et la variable `MISTRAL_API_KEY` dans `.env`.
- **Lenteur Tier 2** : Vérifier le sémaphore asynchrone dans `config/config.py` (réduire `MAX_CONCURRENT_CALLS`).
- **RAG No Match** : Vérifier si `data/vector_store/lv_index.pkl` existe.

---

## 🛠️ 7. Outils de Démonstration & Monitoring (Control Room)

Pour maximiser l'impact lors des présentations (Jury/Direction), le projet inclut désormais deux interfaces distinctes.

### 7.1 Pipeline Monitor (Dashboard Standalone)
Une application dédiée (`/pipeline-monitor`) conçue pour être projetée sur grand écran pendant qu'un utilisateur effectue des tests sur mobile.

- **Fonctionnement** : Connectée via WebSocket (`/ws/pipeline`) au backend.
- **Visualisation** : Affiche chaque étape du traitement cognitive en temps réel avec des animations fluides.
- **Design** : Esthétique "Control Room" ultra-high-tech, mettant en avant la puissance du backend.
- **Lancement** : 
  ```bash
  cd pipeline-monitor
  npm run dev -- --port 3001
  ```

### 7.2 Interface Advisor (Frontend V2)
L'application métier utilisée par les Client Advisors en boutique.
- **Mode Record** : Capture vocale optimisée (PWA/Mobile friendly).
- **Mini-Visualizer** : Une version condensée du parcours IA est intégrée directement dans le flux de l'advisor pour valider le traitement.

---
**LVMH Data Office** - *Confidential & Proprietary* - Document Version 2.5 - 2026
