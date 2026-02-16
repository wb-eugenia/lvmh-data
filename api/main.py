"""
LVMH Voice-to-Tag API
FastAPI backend for React frontend.
"""

import os
import time
import json
import logging
import asyncio
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

from api.database import engine
from api.websocket_manager import manager


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter suitable for stdout log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    json_logs = _env_flag("JSON_LOGS", "1")

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())

    formatter = JsonFormatter() if json_logs else logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    for handler in root.handlers:
        handler.setFormatter(formatter)


configure_logging()
logger = logging.getLogger("lvmh-api")


try:
    from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest, CONTENT_TYPE_LATEST

    PROMETHEUS_ENABLED = True
except Exception:
    PROMETHEUS_ENABLED = False
    Counter = Histogram = Gauge = None
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain"

if PROMETHEUS_ENABLED:
    try:
        HTTP_REQUESTS = Counter(
            "lvmh_api_http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"],
        )
    except ValueError:
        HTTP_REQUESTS = REGISTRY._names_to_collectors.get("lvmh_api_http_requests_total")

    try:
        HTTP_LATENCY = Histogram(
            "lvmh_api_http_request_duration_seconds",
            "HTTP request latency seconds",
            ["method", "path"],
        )
    except ValueError:
        HTTP_LATENCY = REGISTRY._names_to_collectors.get("lvmh_api_http_request_duration_seconds")

    try:
        HTTP_IN_PROGRESS = Gauge(
            "lvmh_api_http_in_progress_requests",
            "In-flight HTTP requests",
        )
    except ValueError:
        HTTP_IN_PROGRESS = REGISTRY._names_to_collectors.get("lvmh_api_http_in_progress_requests")
else:
    HTTP_REQUESTS = HTTP_LATENCY = HTTP_IN_PROGRESS = None


class DistributedRateLimitMiddleware(BaseHTTPMiddleware):
    """API protection against abuse with Redis backend fallback to in-memory."""

    def __init__(self, app):
        super().__init__(app)
        self.backend = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        self.default_limit = int(os.getenv("RATE_LIMIT_REQUESTS_PER_WINDOW", "120"))
        self.path_limits = {
            "/api/auth/login": int(os.getenv("RATE_LIMIT_LOGIN_PER_WINDOW", "20")),
            "/api/transcribe": int(os.getenv("RATE_LIMIT_TRANSCRIBE_PER_WINDOW", "20")),
            "/api/analyze": int(os.getenv("RATE_LIMIT_ANALYZE_PER_WINDOW", "60")),
            "/api/analyze/stream": int(os.getenv("RATE_LIMIT_STREAM_PER_WINDOW", "30")),
        }
        self.store: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()
        self._redis = None
        self._redis_last_attempt = 0.0
        self._redis_retry_seconds = int(os.getenv("RATE_LIMIT_REDIS_RETRY_SECONDS", "30"))
        self._redis_script = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_after = 1
  if oldest[2] ~= nil then
    retry_after = math.ceil(window - (now - tonumber(oldest[2])))
    if retry_after < 1 then
      retry_after = 1
    end
  end
  return {0, count, retry_after}
end

redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window + 1)
return {1, count + 1, 0}
"""

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _limit_for_path(self, path: str) -> int:
        for prefix, value in self.path_limits.items():
            if path.startswith(prefix):
                return value
        return self.default_limit

    async def _init_redis(self) -> None:
        if self.backend != "redis":
            return
        now = time.time()
        if self._redis is not None:
            return
        if now - self._redis_last_attempt < self._redis_retry_seconds:
            return
        self._redis_last_attempt = now
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            await self._redis.ping()
            logger.info("Rate limiter backend initialized: redis")
        except Exception as exc:
            self._redis = None
            logger.warning("Redis unavailable for rate limiter, fallback to memory: %s", exc)

    async def _check_limit_memory(self, key: str, limit: int, now: float) -> tuple[bool, int]:
        async with self.lock:
            bucket = self.store[key]
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0

    async def _check_limit_redis(self, key: str, limit: int, now: float) -> tuple[bool, int]:
        if self._redis is None:
            return await self._check_limit_memory(key, limit, now)
        try:
            redis_key = f"ratelimit:{key}"
            member = f"{now}:{uuid.uuid4().hex}"
            result = await self._redis.eval(
                self._redis_script,
                1,
                redis_key,
                str(now),
                str(self.window_seconds),
                str(limit),
                member,
            )
            allowed = int(result[0]) == 1
            retry_after = int(result[2]) if not allowed else 0
            return allowed, retry_after
        except Exception as exc:
            logger.warning("Redis rate limit check failed, fallback to memory: %s", exc)
            return await self._check_limit_memory(key, limit, now)

    async def dispatch(self, request: Request, call_next):
        if os.getenv("PYTEST_CURRENT_TEST"):
            return await call_next(request)

        path = request.url.path
        if (
            not path.startswith("/api")
            or path.startswith("/api/dashboard/metrics")
            or path in {"/metrics/prometheus"}
        ):
            return await call_next(request)

        await self._init_redis()
        now = time.time()
        limit = self._limit_for_path(path)
        key = f"{self._client_ip(request)}:{path}"

        if self._redis is not None and self.backend == "redis":
            allowed, retry_after = await self._check_limit_redis(key, limit, now)
        else:
            allowed, retry_after = await self._check_limit_memory(key, limit, now)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "path": path,
                    "limit": limit,
                    "window_seconds": self.window_seconds,
                    "backend": "redis" if self._redis is not None and self.backend == "redis" else "memory",
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"req-{int(time.time() * 1000)}"
        request.state.request_id = request_id  # Make available in route handlers
        start_time = time.time()

        if HTTP_IN_PROGRESS:
            HTTP_IN_PROGRESS.inc()

        response = await call_next(request)
        duration = time.time() - start_time

        method = request.method
        path = request.url.path
        status = response.status_code

        if HTTP_REQUESTS:
            HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
        if HTTP_LATENCY:
            HTTP_LATENCY.labels(method=method, path=path).observe(duration)
        if HTTP_IN_PROGRESS:
            HTTP_IN_PROGRESS.dec()

        logger.info(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round(duration * 1000, 2),
                "client_ip": request.headers.get(
                    "x-forwarded-for", request.client.host if request.client else None
                ),
            }
        )

        response.headers["X-Process-Time"] = str(round(duration, 4))
        response.headers["X-Request-Id"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LVMH Voice-to-Tag API starting")

    # Initialize Redis connection
    if _env_flag("USE_REDIS", "1"):
        try:
            from api.redis_client import get_redis
            await get_redis()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

    if _env_flag("PRELOAD_PIPELINE", "0"):  # Disabled by default - lazy load is better
        try:
            from api.routers.analyze import get_pipeline

            get_pipeline()
            logger.info("Pipeline preloaded")
        except Exception as exc:
            logger.warning("Pipeline preload failed: %s", exc)

    leaderboard_task = asyncio.create_task(broadcast_leaderboard_task())
    app.state.leaderboard_task = leaderboard_task
    yield
    
    # Cleanup
    leaderboard_task.cancel()
    with suppress(asyncio.CancelledError):
        await leaderboard_task
    
    # Close Redis connection
    try:
        from api.redis_client import close_redis
        await close_redis()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.warning(f"Redis cleanup error: {e}")
    
    logger.info("API shutting down")


app = FastAPI(
    title="LVMH Voice-to-Tag API",
    description="API backend for LVMH Voice-to-Tag Intelligence Dashboard",
    version="2.1.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV") != "production" else None,
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,https://lvmh-frontend.pages.dev"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(DistributedRateLimitMiddleware)
app.add_middleware(LoggingMiddleware)


@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "healthy",
        "version": "2.1.0",
        "service": "lvmh-voice-to-tag-api",
    }


@app.get("/ready", tags=["System"])
async def readiness():
    """Readiness probe checking DB access and required settings."""
    checks = {"database": False, "jwt_secret": False}
    details = {}
    status = "ready"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        details["database_error"] = str(exc)
        status = "not_ready"

    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    checks["jwt_secret"] = bool(jwt_secret and len(jwt_secret) >= 32)
    if not checks["jwt_secret"]:
        details["jwt_secret_warning"] = "JWT_SECRET_KEY missing or too short (min 32 chars)"
        if os.getenv("ENV", "development").lower() in {"production", "prod", "staging"}:
            status = "not_ready"

    return {
        "status": status,
        "checks": checks,
        "service": "lvmh-voice-to-tag-api",
        "details": details,
    }


@app.get("/metrics/prometheus", tags=["System"])
async def prometheus_metrics():
    """Prometheus scrape endpoint."""
    if not PROMETHEUS_ENABLED:
        return PlainTextResponse("prometheus-client not installed", status_code=503)
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def broadcast_leaderboard_task():
    """Background task to push leaderboard updates."""
    from api.database import SessionLocal

    while True:
        try:
            db = SessionLocal()
            from api.models_sql import User

            users = (
                db.query(User)
                .filter(User.role == "advisor")
                .order_by(User.score.desc())
                .limit(5)
                .all()
            )
            data = [{"id": (u.full_name or u.email.split("@")[0]), "score": u.score, "isMe": False} for u in users]
            await manager.broadcast({"type": "leaderboard", "data": data})
            db.close()
        except Exception as exc:
            logger.error("Leaderboard broadcast error: %s", exc)
        await asyncio.sleep(10)


@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WS Error: %s", exc)
        manager.disconnect(websocket)


from api.routers import analyze, batch, results, stats, transcribe, auth, streaming, feedback, dashboard, products

app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(batch.router, prefix="/api", tags=["Batch"])
app.include_router(results.router, prefix="/api", tags=["Results"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(transcribe.router, prefix="/api", tags=["Transcribe"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(streaming.router, prefix="/api", tags=["Streaming"])
app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
app.include_router(products.router, prefix="/api", tags=["Products"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

# GraphQL endpoint
try:
    from strawberry.fastapi import GraphQLRouter
    from api.graphql import schema as graphql_schema
    
    app.include_router(
        GraphQLRouter(graphql_schema),
        prefix="/graphql",
        tags=["GraphQL"]
    )
    logger.info("GraphQL endpoint enabled at /graphql")
except Exception as e:
    logger.warning(f"GraphQL disabled: {e}")
