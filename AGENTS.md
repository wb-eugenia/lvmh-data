# LVMH Voice-to-Tag Pipeline - Agent Guide

## Project Overview

**LVMH Voice-to-Tag Pipeline V2.3** is an advanced AI system for hyper-personalized CRM in luxury retail. It transforms voice transcriptions from Client Advisors (CAs) into structured, actionable client profiles using a multi-tier processing architecture.

**Key Capabilities:**
- Real-time voice-to-text transcription (OpenAI Whisper)
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
| LLMs | Mistral AI (primary), OpenAI (transcription + RGPD) |
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
│   │   │   └── PipelineVisualizer.jsx
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
- Frontend: http://localhost:3000 (or 5173 in dev)
- API: http://localhost:8000 or http://localhost:8080
- API Docs: http://localhost:8000/docs

---

## Key Configuration

### Environment Variables (.env)

```bash
OPENAI_API_KEY=sk-...          # OpenAI (Whisper + RGPD)
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
- Score 20-75: Tier 2 (Mistral, ~3s, €0.0001)
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

**Method 1: Using gcloud CLI (Recommended)**

```bash
# 1. Authenticate
gcloud auth login
gcloud config set project elite-hold-485510-t5

# 2. Build and push to Container Registry
gcloud builds submit --project=elite-hold-485510-t5 --tag gcr.io/elite-hold-485510-t5/lvmh-voice-tag:latest

# 3. Deploy to Cloud Run
gcloud run deploy lvmh-api \
  --image gcr.io/elite-hold-485510-t5/lvmh-voice-tag \
  --platform managed \
  --region europe-west9 \
  --allow-unauthenticated \
  --memory 1Gi \
  --port 8080 \
  --project=elite-hold-485510-t5
```

**Method 2: Using deployment script**

```powershell
# Run deployment script
.\scripts\deploy.ps1
```

**Method 3: Manual Docker build**

```bash
docker build -t lvmh-voice-tag .
docker run -p 8080:8080 --env-file .env lvmh-voice-tag
```

**Current Production Service:**
- URL: https://lvmh-api-570069708764.europe-west9.run.app
- Service: lvmh-api
- Region: europe-west9

**Environment Variables for Cloud Run:**
```
OPENAI_API_KEY=sk-...
MISTRAL_API_KEY=...
JWT_SECRET_KEY=your-secret-key-min-32-chars
ENV=production
CORS_ORIGINS=https://your-domain.com
```

**Troubleshooting:**
- Check logs: `gcloud logs read --project=elite-hold-485510-t5 --resource=cloud_run_revision --service=lvmh-api`
- Rollback: `gcloud run revisions list lvmh-api --region=europe-west9`

---

## Code Audit & Performance Improvements

### Current Issues Found

#### 1. Database (High Priority)

| Issue | Location | Impact |
|-------|----------|--------|
| No composite indexes on Note | `models_sql.py` | Slow filtered queries |
| Missing indexes on Feedback | `models_sql.py` | Slow feedback queries |
| N+1 queries in results.py | `routers/results.py:260-270` | Multiple DB hits per request |
| No query result caching | Most routers | Repeated expensive queries |

#### 2. API Performance (Medium Priority)

| Issue | Location | Impact |
|-------|----------|--------|
| No response compression | `main.py` | Large JSON payloads |
| In-memory batch task storage | `batch.py:30` | Lost on restart, no scaling |
| Global mutable state | Multiple files | Thread-safety issues |
| Sync DB calls in async | `stats.py` | Blocking event loop |

#### 3. Code Quality (Medium Priority)

| Issue | Location | Impact |
|-------|----------|--------|
| Duplicate normalization logic | `analyze.py`, `schemas.py` | Code duplication |
| No connection pooling config | `database.py` | Default pool too large |
| Missing type hints | Several files | Poor IDE support |
| No request ID tracking | `main.py` | Hard to debug |

### Recommended Improvements

#### Phase 1: Quick Wins (1-2 days)

```python
# 1. Add composite indexes to models_sql.py
class Note(Base):
    __table_args__ = (
        Index("ix_notes_advisor_timestamp", "advisor_id", "timestamp"),
        Index("ix_notes_client_timestamp", "client_id", "timestamp"),
    )

# 2. Enable GZip compression in main.py
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Add ETag caching to stats endpoints
etag = generate_etag(data)
if request.headers.get("if-none-match") == etag:
    return JSONResponse(status_code=304)
```

#### Phase 2: Performance (1 week)

1. **Redis for caching & sessions**
   - Replace in-memory batch tasks with Redis
   - Use Redis for stats caching
   - Store session data in Redis

2. **Database optimizations**
   - Add connection pooling for PostgreSQL
   - Use SQLAlchemy 2.0 async (asyncpg)
   - Add query result pagination

3. **API optimizations**
   - Add response caching headers
   - Implement request deduplication
   - Add GraphQL for complex queries

#### Phase 3: Architecture (2-4 weeks)

1. **Microservices split**
   - Separate transcription service
   - Separate analysis pipeline
   - Separate API/frontend

2. **Message queue**
   - Replace in-memory queue with RabbitMQ/Cloud Tasks
   - Add dead letter queue
   - Implement retry logic

3. **Advanced caching**
   - Semantic cache for LLM responses
   - Redis for vector store metadata
   - CDN for static assets

### Feature Suggestions

| Feature | Priority | Effort |
|---------|----------|--------|
| Real-time notifications (WebSocket) | High | 1 week |
| Export to CSV/Excel | High | 2 days |
| Client timeline view | Medium | 1 week |
| Advanced search with filters | Medium | 1 week |
| Dashboard customization | Medium | 2 weeks |
| Multi-language support | Low | 2 weeks |
| AI-powered insights | Low | 4 weeks |

### Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| API p95 latency | ~500ms | <200ms |
| Note processing | ~2.8s | <1.5s |
| DB query time | ~100ms | <20ms |
| Memory usage | ~500MB | <300MB |
| Cold start | ~10s | <3s |

---

## Resources

- **Technical Documentation**: `LVMH_PIPELINE_TECH_DOC.md`
- **User Guide**: `README.md`
- **Next Steps**: `NEXT_STEPS.md`
- **API Docs**: `/docs` (when running locally)
- **Production API**: https://lvmh-api-570069708764.europe-west9.run.app

---

**LVMH Data Office** - *Confidential & Proprietary* - 2026
