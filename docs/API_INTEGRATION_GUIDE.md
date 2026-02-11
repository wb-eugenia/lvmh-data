# API Integration Guide

## Base URL
- Local: `http://localhost:8080`
- Prod (example): `https://<cloud-run-url>`

## Authentication
### Login
`POST /api/auth/login` (`application/x-www-form-urlencoded`)

Fields:
- `username`
- `password`

Response:
```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "role": "advisor",
  "name": "Sophie Martin",
  "points": 120
}
```

Use header:
`Authorization: Bearer <access_token>`

## Core Endpoints

### Health
- `GET /health`
- `GET /ready`
- `GET /metrics/prometheus`

### Analyze note
`POST /api/analyze`
```json
{
  "text": "Cliente VIC cherche un cadeau anniversaire...",
  "language": "AUTO"
}
```

### Streaming analyze (SSE)
`POST /api/analyze/stream`
```json
{
  "text": "Cliente VIP cherche un sac en cuir noir.",
  "language": "AUTO"
}
```

### Transcribe audio
`POST /api/transcribe` with multipart form-data:
- `file`: audio blob (`.webm`, `.wav`, etc.)

### Dashboard metrics
- `GET /api/dashboard/metrics`
- `GET /api/dashboard/metrics/summary`
- `GET /api/dashboard/components/status`

## Rate Limiting
Global API protection enabled (config via env):
- `RATE_LIMIT_WINDOW_SECONDS`
- `RATE_LIMIT_REQUESTS_PER_WINDOW`
- `RATE_LIMIT_LOGIN_PER_WINDOW`
- `RATE_LIMIT_ANALYZE_PER_WINDOW`
- `RATE_LIMIT_TRANSCRIBE_PER_WINDOW`
- `RATE_LIMIT_STREAM_PER_WINDOW`

Exceeded limits return:
- HTTP `429`
- `Retry-After` header

## Error Contract
Standard errors:
```json
{
  "detail": "Error message"
}
```

Rate limit error:
```json
{
  "detail": "Rate limit exceeded",
  "path": "/api/analyze",
  "limit": 60,
  "window_seconds": 60
}
```

## Observability
- Request tracing:
  - `X-Request-Id`
  - `X-Process-Time`
- Structured logs:
  - set `JSON_LOGS=1`
- Prometheus:
  - scrape `/metrics/prometheus`

