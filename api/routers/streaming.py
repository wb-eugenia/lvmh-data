"""
Streaming Router - Resultats progressifs en temps reel
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.pipeline_async import AsyncPipeline
from src.language_utils import detect_language

logger = logging.getLogger("lvmh-api.streaming")
router = APIRouter()


class StreamingRequest(BaseModel):
    text: str
    language: str = "FR"
    client_id: Optional[str] = None
    advisor_id: Optional[str] = None


async def generate_streaming_results(
    text: str,
    language: str,
    request: Request
) -> AsyncGenerator[str, None]:
    from datetime import datetime

    start_time = time.time()

    # Stream start event
    yield f"data: {json.dumps({'type': 'start', 'timestamp': datetime.now().isoformat()})}\n\n"

    # Progress queue
    progress_queue: asyncio.Queue = asyncio.Queue()

    async def on_progress(step_data):
        payload = {"type": "progress", **(step_data or {})}
        await progress_queue.put(payload)

    note = {
        "ID": f"STREAM_{int(start_time)}",
        "Transcription": text,
        "Language": detect_language(text, fallback="FR") if str(language).upper() == "AUTO" else language
    }

    pipeline = AsyncPipeline(use_semantic_cache=False)
    task = asyncio.create_task(pipeline.process_note(note, on_progress=on_progress))

    try:
        # Stream progress updates
        while True:
            if task.done() and progress_queue.empty():
                break
            try:
                update = await asyncio.wait_for(progress_queue.get(), timeout=0.2)
                yield f"data: {json.dumps(update, default=str)}\n\n"
            except asyncio.TimeoutError:
                continue

        result = await task
        if result:
            result_payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else json.loads(result.json())
            extraction = result_payload.get("extraction") or {}
            pilier_1 = extraction.get("pilier_1_univers_produit", {}) if isinstance(extraction, dict) else {}
            tags = extraction.get("tags") if isinstance(extraction, dict) else None
            if not tags:
                tags = pilier_1.get("categories", []) if isinstance(pilier_1, dict) else []

            final_payload = {
                "type": "complete",
                "timestamp": datetime.now().isoformat(),
                "processing_time_ms": round((time.time() - start_time) * 1000, 1),
                "routing": result_payload.get("routing", {}),
                "extraction": extraction,
                "tags": tags,
                "rgpd": result_payload.get("rgpd", {}),
                "processed_text": result_payload.get("processed_text"),
                "pipeline_output": result_payload
            }
            yield f"data: {json.dumps(final_payload, default=str)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No result returned'})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    finally:
        yield f"data: {json.dumps({'type': 'end'})}\n\n"


@router.post("/analyze/stream")
async def analyze_streaming(request: StreamingRequest, http_request: Request):
    """Endpoint pour l'analyse en streaming (SSE)"""
    return StreamingResponse(
        generate_streaming_results(
            text=request.text,
            language=request.language,
            request=http_request
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/analyze/stream/demo")
async def demo_streaming():
    """Demo endpoint pour tester le streaming"""
    async def demo_generator():
        steps = [
            {"type": "start", "message": "Demarrage"},
            {"type": "progress", "step": "cleaning", "status": "complete", "tokens_saved": 3},
            {"type": "progress", "step": "routing", "tier": 2, "confidence": 0.85},
            {"type": "progress", "step": "extraction", "tier": 2, "progress_percent": 25},
            {"type": "progress", "step": "extraction", "tier": 2, "progress_percent": 50},
            {"type": "progress", "step": "extraction", "tier": 2, "progress_percent": 75},
            {"type": "progress", "step": "extraction", "tier": 2, "progress_percent": 100},
            {"type": "complete", "tags": ["sac", "noir", "femme"]},
            {"type": "end"}
        ]

        for step in steps:
            yield f"data: {json.dumps(step)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        demo_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )
