"""
Analyze router - Single note analysis endpoint.
Rate limited to 30 requests per minute.
"""

import sys
import os
import time
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import NoteInput, ExtractionResult, ExtractionTags, RoutingInfo, RGPDInfo
from src.pipeline_async import AsyncPipeline

logger = logging.getLogger("lvmh-api.analyze")
router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Pipeline instance (lazy loaded)
_pipeline: Optional[AsyncPipeline] = None


def get_pipeline() -> AsyncPipeline:
    """Get or create pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AsyncPipeline(use_cache=True)
        logger.info("Pipeline initialized")
    return _pipeline


@router.post("/analyze", response_model=ExtractionResult)
@limiter.limit("30/minute")
async def analyze_note(note: NoteInput, request: Request):
    """
    Analyze a single client note and extract structured tags.
    
    Rate limited to 30 requests per minute per IP.
    """
    start_time = time.time()
    
    try:
        pipeline = get_pipeline()
        
        # Process note through pipeline
        result = await pipeline.process_note({
            'ID': f'API_{int(time.time())}',
            'Transcription': note.text,
            'Language': note.language
        })
        
        processing_time = (time.time() - start_time) * 1000
        
        # Build response
        return ExtractionResult(
            id=result.id,
            tags=result.extraction.tags if hasattr(result.extraction, 'tags') else [],
            extraction=ExtractionTags(
                brand=getattr(result.extraction, 'brand', None),
                product_category=getattr(result.extraction, 'product_category', None),
                product_type=getattr(result.extraction, 'product_type', None),
                vip_status=getattr(result.extraction, 'vip_status', None),
                budget_range=getattr(result.extraction, 'budget_range', None),
                occasion=getattr(result.extraction, 'occasion', None),
                preferences=getattr(result.extraction, 'preferences', [])
            ),
            routing=RoutingInfo(
                tier=result.routing.tier,
                confidence=result.routing.confidence,
                reason=getattr(result.routing, 'reason', None)
            ),
            rgpd=RGPDInfo(
                contains_sensitive=result.rgpd.contains_sensitive if hasattr(result, 'rgpd') else False,
                categories_detected=getattr(result.rgpd, 'categories_detected', []) if hasattr(result, 'rgpd') else [],
                anonymized_text=getattr(result.rgpd, 'anonymized_text', None) if hasattr(result, 'rgpd') else None
            ),
            processing_time_ms=processing_time,
            cache_hit=getattr(result, 'cache_hit', False),
            model_used=getattr(result, 'model_used', None)
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
