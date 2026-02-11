# Go-Live Checklist (API + Frontend)

Date baseline: 2026-02-11

## Scope
- Backend: FastAPI on Cloud Run
- Frontend: Cloudflare Pages
- Database: PostgreSQL (Cloud SQL recommended)
- Cache / rate limit: Redis (Memorystore recommended)

## 1) Before deployment
1. Set production env vars.
2. Ensure `DATABASE_URL` points to PostgreSQL.
3. Ensure `JWT_SECRET_KEY` is strong (>= 32 chars recommended).
4. Ensure `AUTO_CREATE_SCHEMA=false` in production.
5. Ensure `RATE_LIMIT_BACKEND=redis` with valid `REDIS_URL`.

## 2) Database migration
1. Run migration:
```bash
alembic upgrade head
```
2. For existing DB not managed by Alembic yet:
```bash
alembic stamp head
```
3. Verify tables `users`, `clients`, `notes`, `feedback` exist.

## 3) Backend deployment
1. Build/deploy Cloud Run workflow: `.github/workflows/deploy-api-cloud-run.yml`.
2. Verify endpoints:
```bash
curl https://<api>/health
curl https://<api>/ready
curl https://<api>/metrics/prometheus
```
3. Validate rate limiting returns HTTP 429 after limit exceeded.

## 4) Frontend deployment
1. Build/deploy workflow: `.github/workflows/deploy-frontend-cloudflare.yml`.
2. Validate login and advisor/manager routes.
3. Validate API base URL and websocket URL environment variables.

## 5) Quality gates
1. Re-run benchmark:
```bash
python scripts/benchmark_quality_pipeline.py --dataset LVMH_Realistic_Merged_CA001-100.csv --limit 100
```
2. Check SLO:
```bash
python scripts/check_slo.py --benchmark benchmark_quality_100_pipeline_prod_ready.json
```
3. Optional API/frontend parity:
```bash
python scripts/benchmark_api_frontend_parity.py --limit 20 --output-json benchmark_api_frontend_parity_20_latest.json
```

## 6) Automated go-live report
```bash
python scripts/go_live_checklist.py --benchmark benchmark_quality_100_pipeline_prod_ready.json --output-json go_live_checklist_report.json
```

Pass criteria:
- `overall_ok=true`
- No critical failures

## 7) Post-deploy operations
1. Enable daily DB backup workflow (`.github/workflows/db-backup.yml`).
2. Keep CI blocking on test/build failures.
3. Monitor:
- 5xx error rate
- p95 latency
- rate-limit saturation
- RAG hit-rate and quality drift
