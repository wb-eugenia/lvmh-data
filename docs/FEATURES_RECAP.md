# LVMH Data Pipeline - Documentation Complète

**LVMH Data Pipeline V2.3** est un système AI avancé pour le CRM de retail de luxe. Il transforme les transcriptions vocales des Client Advisors (CA) en profils clients structurés et actionnables.

### Capacités Clés
- Transcription vocale en temps réel (Voxtral/Groq Whisper)
- Routage intelligent via Smart Router V3 (ML Random Forest)
- Extraction 4 piliers (Produit, Profil Client, Hospitalité, Action Business)
- Matching produits RAG
- Recommandations Next Best Action (NBA)
- Gamification avec scoring qualité et leaderboards
- Accès par rôles (Advisor/Manager/Admin)

### URLs de Production
- **Frontend**: https://lvmh-frontend.pages.dev
- **API**: https://lvmh-api-570069708764.europe-west9.run.app
- **Docs API**: https://lvmh-api-570069708764.europe-west9.run.app/docs

---

## Architecture Technique

### Stack Backend
| Composant | Technologie |
|-----------|-------------|
| Framework | FastAPI (async) |
| Langage | Python 3.10+ |
| Base de données | SQLite (SQLAlchemy ORM) |
| Auth | JWT + bcrypt |
| LLMs | Mistral AI (primary), OpenAI GPT-4o (fallback), Groq |
| ML | scikit-learn (Smart Router) |
| Vector Search | **ZVec** + sentence-transformers + FAISS |
| WebSocket | Visualisation pipeline temps réel |

### Stack Frontend
| Composant | Technologie |
|-----------|-------------|
| Framework | React 18 |
| Build Tool | Vite |
| Styling | TailwindCSS |
| Icônes | Lucide React |
| Graphiques | Recharts |
| Animations | Framer Motion, Canvas Confetti |

### Infrastructure
- Docker & Docker Compose
- Multi-stage builds (Node.js + Python)
- GCP Cloud Run (API)
- Cloudflare Pages (Frontend)

---

## Fonctionnalités Backend

### 1. Pipeline de Traitement Multi-Tiers

#### Tier 1 - Regex Rules (~50ms, Gratuit)
- Extraction par règles regex
- Cas simples et directs
- Aucune appels LLM

#### Tier 2 - Groq/Mistral (~3s, €0.0001)
- Notes de complexité moyenne
- Smart Router détermine le tier

#### Tier 3 - Mistral Large/GPT-4 (~5s, €0.005)
- Notes critiques ou complexes
- VIP/VIC, budgets élevés

### 2. Smart Router V3 (ML)
- **Score 0-100** basé sur:
  - Complexité текста (0-25)
  - Qualité linguistique (0-20)
  - Criticalité business (0-30)
  - Type d'intention (0-15)
  - Risque RGPD (0-10)
- Random Forest classifier

### 3. Transcription Audio
- **Primary**: Voxtral Mini (Mistral) - Données EU
- **Fallback**: Groq Whisper - Plus rapide
- **Fallback 2**: OpenAI Whisper-1
- Timestamps word-level inclus
- Support multilingue (fr, it, de, en...)

### 4. Extraction de Tags (Taxonomie 4 Piliers)

#### Pilier 1 - Univers Produit
- Catégories, styles, couleurs, matériaux
- Marques, collections

#### Pilier 2 - Profil Client
- Contexte d'achat
- Socio-pro
- Statut VIC

#### Pilier 3 - Hospitalité & Care
- Occasions
- Allergies
- Préférences

#### Pilier 4 - Action Business
- Next Best Action
- Urgence
- Potentiel budget

### 5. Product Matcher (RAG)
- **ZVec** pour vectorisation (bibliothèque Rust ultra-rapide)
- Semantic search avec sentence-transformers (all-MiniLM-L6-v2)
- **Fallback**: FAISS si ZVec non disponible
- Filtres: catégorie, prix, stock
- Cross-sell recommandations
- Variable: `LVMH_USE_ZVEC=true` pour activer

### 6. Recommender Engine (NBA)
- Génération automatique de NBA
- Signaux prédictifs client
- Gamification scoring
- Events basés sur le profil

### 7. Mistral Key Rotator
- 3 clés API configurables
- Rotation automatique en cas de limite
- Fallback transparent

### 8. Cache & Performance
- Cache sémantique pour prompts
- Cache de résultats
- Limitation de taux (rate limiting)

### 9. RGPD Compliance
- Anonymisation PII
- Détection données sensibles
- Filtrage automatique

---

## Fonctionnalités Frontend

### 1. Landing Page
- 4 espaces: Vendeur, Manager, Pipeline, Admin
- Design lux, glassmorphism
- Animations d'entrée

### 2. Login View
- Authentification JWT
- Redirection automatique post-login
- Gestion erreurs 401

### 3. Advisor View (Espace Vendeur)
- Upload audio/transcription manuelle
- Analyse en temps réel
- Historique des notes
- Recherche clients
- Dashboard personnel (score, stats)

### 4. Manager View (Espace Manager)
- Dashboard analytique complet
- Filtres avancés (advisor, tier, date)
- Leaderboard Advisors
- Vue recordings avec pagination
- Stats RGPD et coûts
- Métriques temps réel
- Segments clients
- Opportunity Board

### 5. Admin Panel (Admin Total)
- **Onglet Accueil**: Dashboard monitoring (health score, métriques, tendances)
- **Onglet Enregistrement**: Liste notes avec détails
- **Onglet Classement**: Rankings Advisors par points
- **Onglet User & Credentials**: Gestion utilisateurs (advisors, managers, admins)
- **Onglet Produits**: Catalogue produits CRUD + rebuild RAG

### 6. Pipeline View
- Visualisation temps réel du pipeline
- WebSocket pour updates live
- Statut de chaque étape

### 7. Products View
- Gestion CRUD produits
- Upload CSV
- Rebuild index RAG
- Statut stock

---

## API Endpoints

### Authentication
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/login` | Connexion utilisateur |
| POST | `/api/auth/seed` | Initialiser données démo |

### Transcription
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/transcribe` | Transcription audio (Voxtral primary) |
| POST | `/api/transcribe/with-timestamps` | Transcription avec timestamps |

### Analyse
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/analyze` | Analyser une note |
| POST | `/api/batch` | Traitement par lots |

### Résultats
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/results` | Liste résultats paginée |
| GET | `/api/results/{id}` | Détail résultat |
| GET | `/api/recordings` | Recordings (Manager) |

### Dashboard
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/dashboard/metrics` | Métriques dashboard |
| GET | `/api/dashboard/metrics/summary` | Résumé métriques |
| GET | `/api/dashboard/metrics/timeseries` | Séries temporelles |
| GET | `/api/dashboard/segments` | Segments clients |
| GET | `/api/dashboard/leaderboard` | Classement advisors |
| GET | `/api/dashboard/opportunities` | Opportunités |

### Produits
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/products` | Liste produits |
| POST | `/api/products` | Créer produit |
| PUT | `/api/products/{sku}/stock` | Mettre à jour stock |
| DELETE | `/api/products/{sku}` | Supprimer produit |
| POST | `/api/products/rebuild-rag` | Rebuild index RAG |

### Clients
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/clients/search` | Rechercher clients |

### Statistiques
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/stats/overview` | Vue d'ensemble |
| GET | `/api/stats/rgpd` | Stats RGPD |
| GET | `/api/stats/cost` | Stats coûts |

---

## Intelligence Artificielle & ML

### Modèles Utilisés

#### Transcription
- **Voxtral Mini** (Mistral) - Primary, données EU
- **Whisper Large V3** (Groq) - Fallback rapide
- **Whisper-1** (OpenAI) - Fallback ultime

#### Traitement Langage
- **Mistral Small** - Tier 2 rapide (~8B params)
- **Mistral Medium** - Tier 2 balancé (~70B params)
- **Mistral Large** - Tier 3 qualité (flagship)
- **GPT-4o** (OpenAI) - Fallback premium

#### Vectorisation
- **ZVec** (Rust) - Index vectoriel ultra-rapide
- **sentence-transformers** (all-MiniLM-L6-v2) - Embeddings produits
- **FAISS** - Fallback si ZVec indisponible

#### ML Classement
- **Smart Router V3** - Random Forest (100+ arbres)
- Features: complexité, qualité, business, intent, RGPD

### Métriques de Performance
| Métrique | Valeur |
|----------|--------|
| Temps moyen | ~2.8s / note |
| Précision taxonomie | 98.5% |
| Hallucinations | 0.0% |
| Débit | 45 notes/min |
| Coût moyen | €0.0004 / note |

---

## Infrastructure & Déploiement

### Frontend (Cloudflare Pages)
```bash
cd frontend-v2
npm run build:deploy
```

**Variables d'environnement:**
- `VITE_API_BASE_URL` - URL de l'API
- `VITE_WS_BASE_URL` - URL WebSocket (optionnel)

### Backend (GCP Cloud Run)
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/lvmh-api .
gcloud run deploy lvmh-api \
  --image gcr.io/PROJECT_ID/lvmh-api \
  --platform managed \
  --region europe-west9 \
  --allow-unauthenticated \
  --memory 1Gi \
  --port 8080 \
  --set-env-vars "LVMH_USE_ZVEC=true"
```
  --platform managed \
  --region europe-west9 \
  --allow-unauthenticated \
  --memory 1Gi \
  --port 8080
```

**Variables d'environnement Cloud Run:**
- `MISTRAL_API_KEY` - Clé Mistral principale
- `MISTRAL_API_KEY_2` - Clé Mistral backup
- `GROQ_API_KEY` - Clé Groq
- `OPENAI_API_KEY` - Clé OpenAI
- `JWT_SECRET_KEY` - Secret JWT (min 32 chars)
- `DATABASE_URL` - URL base de données
- `AUTO_CREATE_SCHEMA` - Création auto tables

### Docker
```bash
docker-compose up --build
```

---

## Sécurité & Conformité

### RGPD
- **Anonymisation**: PII (emails, phones, noms) masqués avant LLM
- **Souveraineté**: Mistral AI (EU-hosted) comme provider principal
- **Détection**: Données sensibles (santé, politique) automatiquement flaggées
- **Traitement local**: Tier 1 regex ne quitte jamais le serveur

### Authentication
- Tokens JWT avec expiration 24h
- Hachage passwords bcrypt
- RBAC (Role-Based Access Control)

### Gestion Secrets
- Jamais commit `.env` dans git
- Rotation API keys régulière
- Docker secrets pour production

---

## Base de Données

### Modèles SQLAlchemy

#### User
```python
- id: Integer (PK)
- email: String (unique)
- hashed_password: String
- full_name: String
- role: String (advisor/manager/admin)
- score: Integer
- store: String
```

#### Client
```python
- id: Integer (PK)
- name: String
- external_client_id: String (unique)
- category: String (Regular/Premium/VIC/Ultimate)
- vic_status: String
- total_spent: Float
- sentiment_score: Float
- sentiment_history: Text
- total_interactions: Integer
- last_interaction: DateTime
- last_contact_date: DateTime
- days_since_contact: Integer
```

#### Note
```python
- id: Integer (PK)
- advisor_id: Integer (FK User)
- client_id: Integer (FK Client)
- transcription: Text
- analysis_json: Text (JSON stocké)
- points_awarded: Integer
- timestamp: DateTime
- sentiment_score: Float
- event_invitation_sent: Boolean
```

#### Product
```python
- sku: String (PK)
- name: String
- category: String
- subcategory: String
- price: Float
- stock: Integer
- image_url: String
- description: Text
```

#### OpportunityAction
```python
- id: Integer (PK)
- note_id: Integer (FK Note)
- client_name: String
- advisor_name: String
- status: String (open/planned/done)
- action_type: String (call/schedule/done)
- next_action: Text
- urgency_level: Integer
- priority_score: Float
- timestamp: DateTime
```

---

## Configuration

### Fichiers de Config
- `config/production.py` - Settings Pydantic
- `config/taxonomy_v2.2.json` - Taxonomie 4 piliers
- `config/lexique_v2.csv` - Lexique mots-clés

### Profiles d'Exécution
| Profile | LLM Provider | Modèle | Timeout |
|---------|--------------|--------|---------|
| `default` | Mistral | mistral-small | 60s |
| `fast` | Groq | llama-3.1-8b-instant | 15s |
| `batch_csv` | Mistral | mistral-small | 30s |
| `quality` | Mistral | mistral-large | 120s |

### Rate Limiting
- `/api/transcribe`: 20 req/fenêtre
- `/api/analyze`: 100 req/fenêtre
- `/api/batch`: 10 req/fenêtre

---

## Comptes Demo

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Advisor | advisor@lvmh.com | lvmh |
| Manager | manager@lvmh.com | lvmh |
| Admin | admin@lvmh.com | lvmh |

---

## Commandes Utiles

```bash
# Installer dépendances
pip install -r requirements.txt

# Lancer API local
python -m uvicorn api.main:app --reload --port 8000

# Lancer frontend dev
cd frontend-v2 && npm run dev

# Lancer tests
pytest tests/ -v

# Nettoyer cache
make clean

# Rebuild RAG
python scripts/build_vector_store.py
```

---

## Résumé Technique

| Aspect | Détail |
|--------|--------|
| **Version** | 2.3 |
| **Langage** | Python 3.10+, JavaScript (React) |
| **API** | FastAPI REST + WebSocket |
| **Database** | SQLite |
| **Auth** | JWT |
| **LLM Primary** | Mistral AI (EU) |
| **LLM Fallback** | OpenAI GPT-4o, Groq |
| **Vector Store** | **ZVec** + sentence-transformers |
| **Frontend** | React 18 + Vite + TailwindCSS |
| **Deployment** | Cloudflare Pages + GCP Cloud Run |
| **RGPD** | Conforme (données EU) |

---

*Document généré le 17 février 2026*
*LVMH Data Office - Confidential & Proprietary*
