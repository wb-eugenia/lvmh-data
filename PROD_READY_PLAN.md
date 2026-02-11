# LVMH Pipeline - Plan Prod Complet

Date: 11 February 2026

## Objectif
Rendre la pipeline Voice-to-Tag exploitable en production avec:
- backend robuste et observable
- déploiement automatisé
- sécurité API
- benchmark qualité reproductible
- gouvernance opérationnelle (SLO, backup, runbook)

## Architecture cible
- Backend: FastAPI sur GCP Cloud Run
- Frontend: Cloudflare Pages (`frontend-v2`)
- Database: PostgreSQL managé (Cloud SQL) en prod, SQLite local en dev
- LLM runtime: Mistral (Tier2/Tier3), OpenAI (Whisper + RGPD), RAG local FAISS
- Observabilité: JSON logs + dashboard métriques + Prometheus endpoint

## Ce qui a été implémenté

### 1) Hardening backend
- `api/main.py`
  - Ajout rate limiting global en mémoire (`InMemoryRateLimitMiddleware`)
  - Ajout logs structurés JSON (`JSON_LOGS=1`)
  - Ajout endpoint readiness `GET /ready` (test DB + secret JWT)
  - Ajout endpoint `GET /metrics/prometheus`
  - Ajout `X-Request-Id` et métriques HTTP (counter/histogram/gauge)
  - Ajout preload pipeline au startup (`PRELOAD_PIPELINE=1`)
- `src/pipeline_async.py`
  - Ajout timeout budget par note (`processing_timeout_seconds`)
  - Tier2/Tier3 bornés avec timeout global (incluant attente sémaphore)
  - Fallback progressif vers tiers inférieurs en cas timeout/erreur
  - RAG skip si budget temps résiduel insuffisant

### 2) Qualité benchmark & SLO
- `scripts/benchmark_quality_pipeline.py`
  - Benchmark qualité reproductible 100 notes
  - Export JSON global + CSV métriques par note
  - Validation de tags vs taxonomie v2.2
- `scripts/check_slo.py`
  - Vérification SLO automatique (quality, p95, rag hit-rate, failed notes)

### 3) CI/CD et ops
- `.github/workflows/ci.yml`
  - Tests backend non-intégration
  - Build frontend
- `.github/workflows/deploy-api-cloud-run.yml`
  - Build image API + déploiement Cloud Run
- `.github/workflows/deploy-frontend-cloudflare.yml`
  - Build et deploy Cloudflare Pages
- `.github/workflows/db-backup.yml`
  - Backup quotidien via workflow + artefact
- `cloudbuild.api.yaml`
  - Build API avec `Dockerfile.api`
- `scripts/backup_db.py`
  - Backup SQLite et PostgreSQL (pg_dump + gzip)
- `scripts/load_test_k6.js`
  - Test de charge API `POST /api/analyze`

### 4) PostgreSQL production explicite
- `api/database.py` et `src/database.py`
  - Pool config prod (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, etc.)
- `docker-compose.prod.yml`
  - Stack API + PostgreSQL pour environnement prod-like
- `.env.example`
  - Variables DB pool, logs, rate limiting, preload pipeline

### 5) UI pipeline visualisation
- `frontend-v2/src/components/PipelineVisualizer.jsx`
  - Correction normalisation quality score (0-1 / 0-100)
  - Correction index step final
- `frontend-v2/src/components/AdvisorView.jsx`
  - Intégration du visualiseur dans la vue Advisor

### 6) Multi-langue
- `src/language_utils.py`
  - Détection langue légère FR/EN/IT/ES/DE
- `api/schemas.py`
  - `language=AUTO` accepté
- `api/routers/analyze.py` / `api/routers/streaming.py`
  - Détection auto appliquée quand `AUTO`

## Matrice des gaps (avant -> après)
| Critère | État avant | État après |
|---|---|---|
| CI/CD pipeline | ❌ | ✅ Workflows GitHub |
| PostgreSQL production | ⚠️ | ✅ Support explicite + pool + compose prod |
| Monitoring/Alerting | ❌ | ✅ Dashboard + `/metrics/prometheus` + `check_slo.py` |
| UI Pipeline visualisation | ❌ | ✅ Branchée dans Advisor |
| Multi-langue complet | ⚠️ | ✅ `AUTO` + détection FR/EN/IT/ES/DE |
| Rate limiting API | ❌ | ✅ Middleware global |
| Backup automatique | ❌ | ✅ script + workflow schedule |
| Logs centralisés | ⚠️ | ✅ logs JSON stdout (Cloud Run ready) |
| Load testing | ❌ | ✅ script k6 |
| Documentation API | ⚠️ | ✅ guide prod + runbook (ce document) |

## Secrets CI/CD requis
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `CLOUD_RUN_SERVICE`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_PAGES_PROJECT`
- `VITE_API_BASE_URL`
- `VITE_WS_BASE_URL`
- `DATABASE_URL` (pour job backup)

## Commandes opérationnelles

### Benchmark qualité 100 notes
```bash
python scripts/benchmark_quality_pipeline.py --dataset LVMH_Realistic_Merged_CA001-100.csv --limit 100
```

### Check SLO
```bash
python scripts/check_slo.py --benchmark benchmark_quality_100_pipeline_prod_ready.json
```

## Dernière validation (11 Feb 2026)
- Benchmark 100 notes (`benchmark_quality_100_pipeline_prod_ready.json`)
  - `avg_quality_score`: **83.99**
  - `avg_tags_per_note`: **12.2**
  - `invalid_tags_rate_pct`: **0.0**
  - `rag_hit_rate_pct`: **90.0**
  - `p95_processing_time_ms`: **2956.15**
  - `failed_notes`: **0**
- SLO check: **PASS**
- Parité API/frontend (`benchmark_api_frontend_parity_20_latest.json`)
  - `tier_match_rate_pct`: **100.0**
  - `rgpd_match_rate_pct`: **100.0**
  - `avg_tag_jaccard`: **1.0**
  - `missing_required_fields`: **0**

### Backup DB
```bash
python scripts/backup_db.py --database-url "$DATABASE_URL" --output-dir backups
```

### Load test
```bash
k6 run scripts/load_test_k6.js -e BASE_URL=http://localhost:8080 -e BEARER_TOKEN=<jwt>
```

## Risques restants (à traiter avant go-live final)
- Migration schéma DB versionnée (Alembic) encore absente
- Rate limiter en mémoire: pour multi-instance Cloud Run, passer à Redis/Cloud Memorystore
- SLO alerting temps réel: brancher sur Cloud Monitoring policies (latency/error budget)
- Secrets rotation automatisée (Secret Manager + policy)

## Taxonomie active
- Runtime principal: `config/taxonomy_v2.2.json`
