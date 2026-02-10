"""
Streaming Router - Resultats progressifs en temps reel
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    pipeline,
    request: Request
) -> AsyncGenerator[str, None]:
    from datetime import datetime
    
    start_time = datetime.now()
    
    # Etape 1: Initialisation
    yield f"data: {json.dumps({'type': 'start', 'timestamp': datetime.now().isoformat()})}\n\n"
    await asyncio.sleep(0.1)
    
    # Etape 2: Data Cleaning
    yield f"data: {json.dumps({'type': 'progress', 'step': 'cleaning', 'status': 'started'})}\n\n"
    
    try:
        from src.text_cleaner import MultilingualTextCleaner
        cleaner = MultilingualTextCleaner(use_embeddings=False)
        clean_res = cleaner.clean_text(text, language)
        cleaned_text = clean_res['cleaned']
        
        cleaning_result = {
            'type': 'progress',
            'step': 'cleaning',
            'status': 'complete',
            'tokens_saved': clean_res.get('fillers_removed', 0),
            'cleaned_preview': cleaned_text[:100] + '...' if len(cleaned_text) > 100 else cleaned_text
        }
        yield f"data: {json.dumps(cleaning_result)}\n\n"
        
        # Etape 3: PII Detection
        pii_detected = any(t in cleaned_text for t in ['[EMAIL]', '[PHONE]', '[CARTE]', '[NAME]'])
        if pii_detected:
            pii_result = {
                'type': 'progress',
                'step': 'rgpd',
                'status': 'complete',
                'pii_detected': True,
                'categories': [t for t in ['[EMAIL]', '[PHONE]', '[CARTE]', '[NAME]'] if t in cleaned_text]
            }
            yield f"data: {json.dumps(pii_result)}\n\n"
        
        # Etape 4: Routing
        yield f"data: {json.dumps({'type': 'progress', 'step': 'routing', 'status': 'started'})}\n\n"
        
        from src.ml_router import get_ml_router
        ml_router = get_ml_router()
        ml_decision = ml_router.predict(cleaned_text, language)
        
        if ml_decision:
            tier = ml_decision.tier
            confidence = ml_decision.confidence
            routing_source = "ml"
        else:
            from src.smart_router import SmartRouterV2
            router_v2 = SmartRouterV2()
            decision = router_v2.route_ml(cleaned_text, language, {})
            tier = decision.tier
            confidence = decision.confidence
            routing_source = "heuristic"
        
        routing_result = {
            'type': 'progress',
            'step': 'routing',
            'status': 'complete',
            'tier': tier,
            'confidence': round(confidence, 3),
            'source': routing_source
        }
        yield f"data: {json.dumps(routing_result)}\n\n"
        
        # Etape 5: Extraction
        extraction_start = {'type': 'progress', 'step': 'extraction', 'tier': tier, 'status': 'started'}
        yield f"data: {json.dumps(extraction_start)}\n\n"
        
        # Simulation du temps de traitement
        processing_time = 0.5 if tier == 1 else (2.0 if tier == 2 else 4.0)
        
        if tier >= 2:
            steps = 4 if tier == 3 else 2
            for i in range(steps):
                await asyncio.sleep(processing_time / steps)
                progress = int((i + 1) / steps * 100)
                progress_update = {
                    'type': 'progress',
                    'step': 'extraction',
                    'tier': tier,
                    'status': 'processing',
                    'progress_percent': progress
                }
                yield f"data: {json.dumps(progress_update)}\n\n"
        
        # Resultat final
        from src.tier1_rules import Tier1RulesEngine
        tier1 = Tier1RulesEngine()
        extraction = tier1.extract(cleaned_text, language)
        
        result = {
            'type': 'complete',
            'timestamp': datetime.now().isoformat(),
            'processing_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
            'routing': {
                'tier': tier,
                'confidence': round(confidence, 3),
                'source': routing_source
            },
            'extraction': {
                'tags': extraction.tags if extraction else [],
                'pilier_1': extraction.pilier_1_univers_produit.model_dump() if extraction and hasattr(extraction, 'pilier_1_univers_produit') else {},
                'pilier_2': extraction.pilier_2_profil_client.model_dump() if extraction and hasattr(extraction, 'pilier_2_profil_client') else {},
            },
            'rgpd': {
                'pii_detected': pii_detected,
                'anonymized_text': cleaned_text[:200] + '...' if len(cleaned_text) > 200 else cleaned_text
            }
        }
        
        yield f"data: {json.dumps(result)}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_result = {'type': 'error', 'message': str(e)}
        yield f"data: {json.dumps(error_result)}\n\n"
    
    finally:
        yield f"data: {json.dumps({'type': 'end'})}\n\n"


@router.post("/analyze/stream")
async def analyze_streaming(
    request: StreamingRequest,
    http_request: Request
):
    """
    Endpoint pour l'analyse en streaming (SSE)
    """
    return StreamingResponse(
        generate_streaming_results(
            text=request.text,
            language=request.language,
            pipeline=None,
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
    """
    Demo endpoint pour tester le streaming
    """
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
