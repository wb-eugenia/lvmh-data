"""
LVMH Voice-to-Tag API
FastAPI backend for React frontend.
"""

import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lvmh-api")


# Logging Middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        logger.info({
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2)
        })
        
        response.headers["X-Process-Time"] = str(round(duration, 4))
        return response


# Lifespan (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 LVMH Voice-to-Tag API starting...")
    yield
    logger.info("👋 API shutting down...")


# Create app
app = FastAPI(
    title="LVMH Voice-to-Tag API",
    description="API backend for LVMH Voice-to-Tag Intelligence Dashboard",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENV") != "production" else None,
    lifespan=lifespan
)

# Dynamic CORS
ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "lvmh-voice-to-tag-api"
    }


# Import and include routers
from api.routers import analyze, batch, results, stats

app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(batch.router, prefix="/api", tags=["Batch"])
app.include_router(results.router, prefix="/api", tags=["Results"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
