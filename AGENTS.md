# LVMH Voice-to-Tag Pipeline - Agent Guide

## Project Overview

**LVMH Voice-to-Tag Pipeline V2.3** is an advanced AI system for hyper-personalized CRM in luxury retail. It transforms voice transcriptions from Client Advisors (CAs) into structured, actionable client profiles using a multi-tier processing architecture.

**Key Capabilities:**
- Real-time voice-to-text transcription (Groq Whisper)
- Intelligent note routing via Smart Router V3 (Random Forest ML)
- 4-pillar taxonomy extraction (Product, Client Profile, Hospitality, Business Action)
- RAG-based product matching
- Next Best Action (NBA) recommendations
- Gamification with quality scoring and leaderboards
- Role-based access (Advisor/Manager)

**Confidentiality:** LVMH Internal Use Only - RGPD Compliant

---

## Technology Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI (async) |
| Language | Python 3.10+ |
| Database | SQLite (SQLAlchemy ORM) |
| Auth | JWT + bcrypt |
| LLMs | Mistral AI (primary), OpenAI GPT-4o (fallback), Groq |
| ML | scikit-learn (Smart Router) |
| Vector Search | sentence-transformers + FAISS |
| WebSocket | Real-time pipeline visualization |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | React 18 |
| Build Tool | Vite |
| Styling | TailwindCSS |
| Icons | Lucide React |
| Charts | Recharts |
| Animations | Framer Motion, Canvas Confetti |

### Infrastructure
- Docker & Docker Compose
- Multi-stage builds (Node.js + Python)
- GCP Cloud Run deployment ready

---

## Project Structure

```
.
├── api/                    # FastAPI backend
│   ├── main.py            # App entry point, middleware, WebSocket
│   ├── database.py        # SQLAlchemy models & connection
│   ├── auth_utils.py      # JWT & password hashing
│   ├── schemas.py         # Pydantic request/response models
│   └── routers/           # API route modules
│       ├── auth.py        # Login, token generation
│       ├── analyze.py     # Single note analysis
│       ├── batch.py       # Batch processing
│       ├── results.py     # Results retrieval
│       ├── stats.py       # Dashboard statistics
│       └── transcribe.py  # Audio transcription
│
├── src/                    # Core pipeline modules
│   ├── event_pipeline.py  # Main FastAPI app (legacy entry)
│   ├── pipeline_async.py  # Async batch processing
│   ├── pipeline_batch_v2.py # Batch v2 with tier routing
│   ├── smart_router.py    # Smart Router V3 (ML routing)
│   ├── text_cleaner.py    # Pre-processing & normalization
│   ├── tier1_rules.py     # Regex-based extraction (Tier 1)
│   ├── tier2_groq.py      # Groq LLM processing (Tier 2)
│   ├── tier2_mistral.py   # Mistral AI processing (Tier 2/3)
│   ├── taxonomy.py        # Taxonomy management
│   ├── extractor.py       # Tag extraction engine
│   ├── product_matcher.py # RAG product matching
│   ├── recommender.py     # Next Best Action engine
│   ├── auth.py            # FastAPI auth dependencies
│   ├── database.py        # DB models (Store, User, Interaction)
│   ├── models.py          # Pydantic data models
│   ├── rgpd_filter.py     # RGPD compliance filtering
│   └── cache_manager.py   # Caching layer
│
├── frontend-v2/           # React frontend
│   ├── src/
│   │   ├── App.jsx        # Main app with routing
│   │   ├── main.jsx       # Entry point
│   │   ├── components/
│   │   │   ├── LandingPage.jsx
│   │   │   ├── LoginView.jsx
│   │   │   ├── AdvisorView.jsx    # CA interface
│   │   │   ├── ManagerView.jsx    # Manager dashboard
│   │   │   ├── AdminPanel.jsx     # Admin dashboard with sidebar tabs
│   │   │   ├── AdminProductsView.jsx # Products CRUD component
│   │   │   ├── PipelineVisualizer.jsx
│   │   │   └── ProductsView.jsx
│   │   └── context/
│   │       └── AuthContext.jsx    # JWT auth state
│   ├── package.json
│   └── vite.config.js
│
├── config/                # Configuration files
│   ├── production.py      # Pydantic settings
│   ├── taxonomy_v2.2.json # Taxonomy definition
│   └── lexique_v2.csv     # Keywords lexicon
│
├── scripts/               # Utility scripts
│   ├── run_wave2_pipeline.py
│   ├── build_vector_store.py
│   ├── validate_rgpd.py
│   └── deploy.ps1         # GCP deployment
│
├── tests/                 # Test suite
│   ├── test_production.py
│   ├── test_text_cleaner.py
│   └── test_precision.py
│
├── app.py                 # Streamlit legacy dashboard
├── requirements.txt       # Python dependencies
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Local orchestration
└── Makefile              # Common commands
```

---

## Build and Run Commands

### Local Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend-v2
npm install

# Run backend (FastAPI with auto-reload)
python -m uvicorn api.main:app --reload --port 8000

# Run frontend (dev server)
cd frontend-v2
npm run dev

# Run Streamlit legacy app
make run
```

### Using Make

```bash
make install          # Install Python dependencies
make run              # Start Streamlit app
make test             # Run pytest
make pipeline         # Run Wave 2 pipeline
make pipeline-nocache # Run without cache
make compare          # Compare Wave 1 vs Wave 2
make validate-rgpd    # RGPD validation
make clean            # Clean cache and logs
make clean-all        # Clean everything including outputs
```

### Docker Deployment

```bash
# Build and run full stack
docker-compose up --build

# Or using Make
make docker-build     # Build image
make docker-up        # Start services
make docker-down      # Stop services
make docker-logs      # View logs
```

The application will be available at:
- Frontend: https://lvmh-frontend.pages.dev (Cloudflare Pages)
- API: https://lvmh-api-570069708764.europe-west9.run.app (GCP Cloud Run)
- API Docs: https://lvmh-api-570069708764.europe-west9.run.app/docs

---

## Production Deployment URLs

### Current Deployments
- **Frontend**: https://lvmh-frontend.pages.dev (Cloudflare Pages)
- **API**: https://lvmh-api-570069708764.europe-west9.run.app (GCP Cloud Run)

### Deployment Commands

#### Frontend (Cloudflare Pages)

```bash
cd frontend-v2

# Build only
npm run build

# Build + Deploy en une commande
npm run build:deploy

# Deploy seul (si deja build)
npm run deploy

# Development
npm run dev
```

#### API (GCP Cloud Run)
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/lvmh-voice-tag .
gcloud run deploy lvmh-voice-tag \
  --image gcr.io/PROJECT_ID/lvmh-voice-tag \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --port 8080
```

---

## Key Configuration

### Environment Variables (.env)

```bash
OPENAI_API_KEY=sk-...          # OpenAI GPT-4o-mini
GROQ_API_KEY=gsk-...           # Groq API (Whisper + LLM)
MISTRAL_API_KEY=...            # Mistral AI (primary LLM)
```

### Config Settings (config/production.py)

```python
# Pipeline thresholds
tier1_confidence_threshold: 0.75
tier2_confidence_threshold: 0.85
max_concurrent_notes: 10
processing_timeout_seconds: 60

# Cache
cache_enabled: True
cache_ttl_seconds: 86400

# Ollama (local fallback)
ollama_host: "http://localhost:11434"
ollama_model: "qwen2.5:7b"
```

---

## Architecture Deep Dive

### Smart Router V3

The router scores notes 0-100 based on:
- **Text Complexity** (0-25): Length, vocabulary diversity
- **Linguistic Quality** (0-20): Fillers, errors, structure
- **Business Criticality** (0-30): VIC/VIP keywords, budget
- **Intent Type** (0-15): Purchase, gift, complaint
- **RGPD Risk** (0-10): Sensitive data detection

**Routing Logic:**
- Score < 20: Tier 1 (Regex rules, ~50ms, €0)
- Score 20-75: Tier 2 (Groq/Mistral, ~3s, €0.0001)
- Score > 75: Tier 3 (Mistral Large/GPT-4, ~5s, €0.005)

### 4-Pillar Taxonomy

1. **Pilier 1 - Univers Produit**: Categories, styles, colors, materials
2. **Pilier 2 - Profil Client**: Purchase context, socio-pro, VIC status
3. **Pilier 3 - Hospitalité & Care**: Occasions, allergies, preferences
4. **Pilier 4 - Action Business**: NBA, urgency, budget potential

### Authentication Flow

1. User logs in via `/api/auth/login` (OAuth2PasswordRequestForm)
2. Server validates credentials, returns JWT access token
3. Client includes token in `Authorization: Bearer <token>` header
4. `get_current_user()` dependency validates token and fetches user
5. Role check via `check_role()` for manager-only endpoints

**Demo Accounts:**
- Advisor: `advisor@lvmh.com` / `lvmh`
- Manager: `manager@lvmh.com` / `lvmh`

---

## Code Style Guidelines

### Python
- Follow PEP 8 (max line length: 120)
- Use type hints (typing module)
- Use Pydantic models for data validation
- Use async/await for I/O operations
- Log using `logging` module with structured JSON logs

```python
# Example pattern
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class MyModel(BaseModel):
    id: str
    score: float = Field(ge=0.0, le=100.0)
```

### JavaScript/React
- Use functional components with hooks
- Use Tailwind classes for styling
- Prefer Lucide icons
- Handle loading states explicitly

---

## Testing Strategy

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_production.py -v

# With coverage
pytest --cov=src tests/
```

### Test Types

1. **Unit Tests** (`test_text_cleaner.py`, `test_fuzzy.py`)
2. **Integration Tests** (`test_production.py`): Async pipeline, caching, DLQ
3. **Precision Tests** (`test_precision.py`): Accuracy benchmarks

### Key Test Patterns

```python
# Async test example
import asyncio
from src.pipeline_async import AsyncPipeline

async def test_pipeline():
    pipeline = AsyncPipeline(use_cache=True)
    results = await pipeline.process_batch(test_notes)
    assert len(results) == len(test_notes)

asyncio.run(test_pipeline())
```

---

## Security Considerations

### RGPD Compliance
- **Anonymization**: PII (emails, phones, names) masked before LLM processing
- **Souveraineté**: Mistral AI (EU-hosted) as primary LLM
- **Sensitive Data Detection**: Automatic flagging of health, political data
- **Local Processing**: Tier 1 regex never leaves the server

### Authentication
- JWT tokens with 24h expiration
- bcrypt password hashing
- Role-based access control (RBAC)

### Secrets Management
- Never commit `.env` file
- Rotate API keys regularly
- Use Docker secrets for production

---

## Common Development Tasks

### Adding a New API Endpoint

1. Create/modify router in `api/routers/`
2. Define Pydantic schemas in `api/schemas.py`
3. Add route with proper auth dependencies
4. Register router in `api/main.py`

### Adding a Frontend Component

1. Create component in `frontend-v2/src/components/`
2. Import and use in `App.jsx` or parent component
3. Use Tailwind for styling
4. Add to route handling if needed

### Modifying the Taxonomy

1. Edit `config/taxonomy_v2.2.json`
2. Update `src/taxonomy.py` if structure changes
3. Test extraction with `scripts/run_wave2_pipeline.py`
4. Rebuild vector store if products changed

### Rebuilding the RAG Index

```bash
python scripts/build_vector_store.py
```

---

## Admin Panel Architecture

### Components

- **AdminPanel.jsx** - Main admin dashboard with sidebar navigation (5 tabs)
- **AdminProductsView.jsx** - Full CRUD for products with stock management and RAG rebuild

### Sidebar Tabs

1. **Accueil** - Dashboard monitoring (health score, metrics, trends)
2. **Enregistrement** - List of notes with click-to-view details
3. **Classement** - Advisor rankings by points
4. **User & Credentials** - User management (advisors, managers, admins)
5. **Produits** - Product catalog with CRUD operations

### CORS Configuration

The API (`api/main.py`) is configured to allow Cloudflare Pages domains:
```python
ALLOWED_ORIGINS.extend([
    "https://lvmh-frontend.pages.dev",
])
```

For local development, add your localhost to `.env`:
```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `invalid_api_key` | Check `.env` file and API quotas |
| Slow Tier 2 processing | Reduce `MAX_CONCURRENT_CALLS` in config |
| RAG no match | Verify `data/vector_store/lv_index.pkl` exists |
| WebSocket disconnect | Check CORS settings in `api/main.py` |
| Database locked | SQLite limitation - restart server |

---

## Performance Benchmarks

Tested on 400 real notes (January 2026):

| Metric | Value |
|--------|-------|
| Avg Processing Time | ~2.8s / note |
| Taxonomy Precision | 98.5% |
| Hallucinations | 0.0% |
| Throughput | 45 notes/min |
| Avg Cost | €0.0004 / note |

---

## Deployment

### GCP Cloud Run (Production)

```powershell
# Run deployment script
.\scripts\deploy.ps1
```

Requirements:
- gcloud CLI authenticated
- Cloud Run & Cloud Build APIs enabled
- Project ID ready

### Docker Production

```bash
docker build -t lvmh-voice-tag .
docker run -p 8080:8080 --env-file .env lvmh-voice-tag
```

---

## Resources

- **Technical Documentation**: `LVMH_PIPELINE_TECH_DOC.md`
- **User Guide**: `README.md`
- **Next Steps**: `NEXT_STEPS.md`
- **API Docs**: `/docs` (when running locally)

---

**LVMH Data Office** - *Confidential & Proprietary* - 2026
