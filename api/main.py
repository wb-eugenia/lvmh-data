"""
LVMH Voice-to-Tag API
FastAPI backend for React frontend.
"""

import os
import time
import logging
import asyncio
from contextlib import asynccontextmanager, suppress

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
    leaderboard_task = asyncio.create_task(broadcast_leaderboard_task())
    app.state.leaderboard_task = leaderboard_task
    yield
    leaderboard_task.cancel()
    with suppress(asyncio.CancelledError):
        await leaderboard_task
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
    "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002,http://127.0.0.1:5173"
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


# --- WebSocket Manager ---
from api.websocket_manager import manager
from fastapi import WebSocket, WebSocketDisconnect


async def broadcast_leaderboard_task():
    """Background task to push leaderboard updates."""
    from api.database import SessionLocal
    from api.routers.results import get_leaderboard_data # I'll check if this exists or implement it
    
    while True:
        try:
            db = SessionLocal()
            # Simplified leaderboard logic
            from api.models_sql import User
            users = db.query(User).filter(User.role == "advisor").order_by(User.score.desc()).limit(5).all()
            data = [
                {"id": u.name, "score": u.score, "isMe": False} # isMe handled by frontend
                for u in users
            ]
            await manager.broadcast({"type": "leaderboard", "data": data})
            db.close()
        except Exception as e:
            logger.error(f"Leaderboard broadcast error: {e}")
        await asyncio.sleep(10)

@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        manager.disconnect(websocket)


# Import and include routers
from api.routers import analyze, batch, results, stats, transcribe, auth, streaming, feedback, dashboard

app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(batch.router, prefix="/api", tags=["Batch"])
app.include_router(results.router, prefix="/api", tags=["Results"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
app.include_router(transcribe.router, prefix="/api", tags=["Transcribe"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(streaming.router, prefix="/api", tags=["Streaming"])
app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
