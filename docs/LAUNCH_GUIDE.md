# LVMH Data Pipeline - Guide de Lancement

## 📋 Prérequis

- **Docker Desktop** (recommandé) OU
- **Python 3.10+** & **Node.js 18+**

---

## 🎯 Méthodes de Lancement

### Option 1: Docker (Recommandée) ⭐

```bash
# Lancer tout le projet en une commande
docker-compose up --build

# Accès:
# - Frontend: http://localhost:3000
# - API:      http://localhost:8000
```

### Option 2: Manuel (Développement)

**Terminal 1 - Backend:**
```bash
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend-v2
npm install
npm run dev
```

### Option 3: Streamlit (Legacy)
```bash
make run
# ou
streamlit run app.py
```

---

## 🔐 Comptes de Démo

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Vendeur | `advisor@lvmh.com` | `lvmh` |
| Manager | `manager@lvmh.com` | `lvmh` |

---

## 🔄 Architecture des Commandes (Flow ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LVMH VOICE-TO-TAG PIPELINE                              │
│                            Architecture des Commandes                           │
└─────────────────────────────────────────────────────────────────────────────────┘

                                🎯 MAKE COMMANDS
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
       ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
       │ make install│        │  make run   │        │  make test  │
       └──────┬──────┘        └──────┬──────┘        └──────┬──────┘
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │ pip install -r  │    │ streamlit run   │    │ pytest tests/   │
    │ requirements.txt│    │     app.py      │    │      -v         │
    └─────────────────┘    └────────┬────────┘    └─────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │      STREAMLIT LEGACY APP     │
                    │         (Port 8501)           │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │   TagExtractor      │         │   Taxonomy Manager  │
        │   (Mistral AI)      │         │   (LVMH Standards)  │
        └──────────┬──────────┘         └─────────────────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │    lvmh.db (SQLite) │
        │   Persistance data  │
        └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                              DOCKER COMMANDS FLOW
═══════════════════════════════════════════════════════════════════════════════════

                                🐳 DOCKER COMPOSE
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         docker-compose up --build                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Build Context     │    │   Build Context     │    │   Networks/Volumes  │
│   (Dockerfile)      │    │   (Dockerfile.api)  │    │                     │
└──────────┬──────────┘    └──────────┬──────────┘    └─────────────────────┘
           │                          │
           ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐
│   lvmh-app Service  │◄──►│   API Service       │
│   Port: 8080        │    │   Port: 8000        │
└──────────┬──────────┘    └─────────────────────┘
           │
           │    ┌─────────────────────────────────────────────────────────────┐
           │    │                    CONTAINER RUNTIME                         │
           │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
           └────►│  FastAPI      │  │  Frontend   │  │  SQLite Database    │  │
                │  Backend      │──►│  Static     │  │  /app/lvmh.db       │  │
                └─────────────┘  │  └─────────────┘  └─────────────────────┘  │
                                 └─────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
             ┌────────────┐    ┌────────────┐    ┌────────────┐
             │  Port 3000 │    │  Port 8000 │    │  API Docs  │
             │  Frontend  │    │  API       │    │  /docs     │
             └────────────┘    └────────────┘    └────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                            PIPELINE COMMANDS FLOW
═══════════════════════════════════════════════════════════════════════════════════

                              ⚙️ PIPELINE EXECUTION
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ make pipeline   │        │make pipeline-   │        │  make compare   │
│                 │        │   nocache      │        │                 │
└────────┬────────┘        └────────┬────────┘        └────────┬────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ scripts/run_    │        │ scripts/run_    │        │ scripts/compare │
│ wave2_pipeline  │        │ wave2_pipeline  │        │ _waves.py       │
│     .py         │        │   .py --no-cache│        │                 │
└────────┬────────┘        └────────┬────────┘        └─────────────────┘
         │                          │
         │            ┌─────────────┘
         │            │
         ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE PROCESSING CHAIN                               │
│                                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │  Input   │───►│  Text    │───►│  Smart   │───►│  Tag     │───►│  Output  │  │
│   │  CSV/DB  │    │  Cleaner │    │  Router  │    │  Extract │    │  JSON    │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                        │                                        │
│                              ┌─────────┴─────────┐                              │
│                              ▼                   ▼                              │
│                        ┌──────────┐       ┌──────────┐                          │
│                        │  Regex   │       │ Mistral  │                          │
│                        │  Engine  │       │   AI     │                          │
│                        │  (T1)    │       │(T2 & T3) │                          │
│                        └──────────┘       └──────────┘                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                           UTILITIES & CLEANUP FLOW
═══════════════════════════════════════════════════════════════════════════════════

                              🧹 CLEANUP COMMANDS
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
           ▼                         ▼                         ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│   make clean    │        │  make clean-all │        │make validate-   │
│                 │        │                 │        │    rgpd        │
└────────┬────────┘        └────────┬────────┘        └─────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────┐        ┌─────────────────┐
│ rm -rf cache/   │        │ make clean +    │
│ rm -rf logs/    │        │ rm outputs/*    │
│ rm __pycache__  │        │                 │
└─────────────────┘        └─────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                            REQUEST FLOW (Runtime)
═══════════════════════════════════════════════════════════════════════════════════

   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────────┐
   │   User      │────►│  Frontend   │────►│         FastAPI Gateway             │
   │  (Browser)  │     │  (React)    │     │         (Port 8000)                 │
   └─────────────┘     └─────────────┘     └───────────────┬─────────────────────┘
                                                           │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            │                            │
                              ▼                            ▼                            ▼
                    ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
                    │  /auth/login    │          │  /analyze       │          │  /history       │
                    │  JWT Token      │          │  Data Pipeline  │          │  User History   │
                    └────────┬────────┘          └────────┬────────┘          └─────────────────┘
                             │                            │
                             ▼                            ▼
                    ┌─────────────────┐          ┌─────────────────────────────────────────┐
                    │  SQLite Users   │          │         Smart Router V3                 │
                    │  Table          │          │    (Random Forest Classifier)           │
                    └─────────────────┘          └───────────────┬─────────────────────────┘
                                                                 │
                                    ┌────────────────────────────┼────────────────────────────┐
                                    │                            │                            │
                                    ▼                            ▼                            ▼
                          ┌───────────────┐            ┌───────────────┐            ┌───────────────┐
                          │   Tier 1      │            │   Tier 2      │            │   Tier 3      │
                          │   Regex       │            │   Mistral     │            │   Mistral     │
                          │   Engine      │            │   Balanced    │            │   Premium     │
                          └───────┬───────┘            └───────┬───────┘            └───────┬───────┘
                                  │                            │                            │
                                  └────────────────────────────┼────────────────────────────┘
                                                               │
                                                               ▼
                                                  ┌─────────────────────┐
                                                  │  Result Consolidator │
                                                  │  + NBA Engine       │
                                                  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │     lvmh.db         │
                                                  │  (SQLite/PostgreSQL)│
                                                  └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
                              FILE STRUCTURE MAP
═══════════════════════════════════════════════════════════════════════════════════

📁 lvmh-data/
│
├── 📁 api/                          ← FastAPI Backend
│   ├── main.py                      ← Entry point API
│   ├── routes/
│   └── models/
│
├── 📁 frontend-v2/                  ← React Frontend
│   ├── src/
│   │   ├── components/              ← UI Components
│   │   ├── pages/                   ← Login, Dashboard
│   │   └── services/                ← API calls
│   └── package.json
│
├── 📁 src/                          ← Core Pipeline Logic
│   ├── pipeline_async.py            ← Main pipeline
│   ├── smart_router.py              ← ML Router
│   ├── extractor.py                 ← Tag extraction
│   └── recommender.py               ← NBA & Gamification
│
├── 📁 scripts/                      ← Utility Scripts
│   ├── run_wave2_pipeline.py
│   └── compare_waves.py
│
├── 📄 app.py                        ← Streamlit Legacy App
├── 📄 Makefile                      ← Command definitions
├── 📄 docker-compose.yml            ← Docker orchestration
├── 📄 requirements.txt              ← Python dependencies
└── 📄 lvmh.db                       ← SQLite Database

```

---

## 📝 Récapitulatif des Commandes

| Commande | Description |
|----------|-------------|
| `make install` | Installe les dépendances Python |
| `make run` | Lance l'app Streamlit (legacy) |
| `make test` | Lance les tests pytest |
| `make pipeline` | Execute le pipeline Wave 2 |
| `make pipeline-nocache` | Pipeline sans cache |
| `make compare` | Compare Wave 1 vs Wave 2 |
| `make clean` | Nettoie cache et logs |
| `make docker-up` | Lance avec Docker Compose |
| `make docker-down` | Arrête les containers |

---

**LVMH Data Office** - *Confidential & Proprietary* - 2026
