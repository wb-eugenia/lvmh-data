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

from api.schemas import NoteInput, ExtractionResult, ExtractionTags, RoutingInfo, RGPDInfo, MetaAnalysis
from src.pipeline_async import AsyncPipeline
from api.routers.auth import get_current_user
from api.models_sql import User, Note, Client
from api.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import json

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
async def analyze_note(
    note: NoteInput, 
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze a single client note and extract structured tags.
    """
    logger.info(f"Authenticated user: {current_user.email} (ID: {current_user.id})")

    start_time = time.time()
    
    try:
        pipeline = get_pipeline()
        
        # Progress callback for WebSocket
        from api.websocket_manager import manager
        async def on_progress(data):
            data["user_id"] = current_user.id
            await manager.broadcast(data)

        # Process note through pipeline
        result = await pipeline.process_note({
            'ID': f'API_{int(time.time())}',
            'Transcription': note.text,
            'Language': note.language
        }, on_progress=on_progress, save_to_cache=False)
        
        if result is None:
            raise HTTPException(status_code=500, detail="Analysis failed to produce a result.")
            
        processing_time = (time.time() - start_time) * 1000
        ext = result.extraction
        
        # Build response with mapping from 4-Pillar to API schema
        # === PERSISTENCE ===
        try:
            if current_user:
                # 1. Update Score
                points = 10
                quality = ext.meta_analysis.quality_score if ext else 0.0
                quality_pct = quality * 100 if quality <= 1 else quality
                if quality_pct >= 80:
                    points += 5
                current_user.score += points
                
                # 2. Get/Create Client (Simple logic: if VIC/Ultimate mentioned or just 'Standard')
                client_name = "Client Inconnu"
                if ext.pilier_2_profil_client.purchase_context.behavior in ["vic", "ultimate"]:
                    client_name = "Client VIP"
                
                # Find or create a generic client for this demo
                client = db.query(Client).filter(Client.name == client_name).first()
                if not client:
                    client = Client(name=client_name, vic_status="Standard")
                    db.add(client)
                    db.commit()
                    db.refresh(client)
                
                # 3. Save Note
                new_note = Note(
                    advisor_id=current_user.id,
                    client_id=client.id,
                    transcription=result.processed_text,
                    # Avoid persisting raw input text (may contain PII). Keep anonymized `processed_text`.
                    analysis_json=json.dumps(
                        result.model_dump(mode="json", exclude={"original_text"}),
                        ensure_ascii=False,
                        default=str
                    ),
                    points_awarded=points
                )
                db.add(new_note)
                db.commit()
                logger.info(f"💾 Note saved for user {current_user.email} (+{points} pts)")
        except Exception as e:
            logger.error(f"Persistence error: {e}")

        return ExtractionResult(
            id=result.id,
            tags=ext.tags if ext else [],
            extraction=ExtractionTags(
                brand=None, # Not explicitly in new 4-pillar categories yet
                product_category=", ".join(ext.pilier_1_univers_produit.categories) if ext else None,
                product_type=None,
                vip_status=ext.pilier_2_profil_client.purchase_context.behavior if ext else None,
                budget_range=ext.pilier_4_business.budget_potential if hasattr(ext, 'pilier_4_business') and ext.pilier_4_business else (ext.pilier_4_action_business.budget_potential if hasattr(ext, 'pilier_4_action_business') and ext.pilier_4_action_business else None),
                occasion=ext.pilier_3_hospitalite_care.occasion if ext else None,
                preferences=(ext.pilier_1_univers_produit.preferences.colors + ext.pilier_1_univers_produit.preferences.materials) if ext else []
            ),
            routing=RoutingInfo(
                tier=result.routing.tier,
                confidence=result.routing.confidence,
                reason=", ".join(result.routing.reasons)
            ),
            rgpd=RGPDInfo(
                contains_sensitive=result.rgpd.contains_sensitive,
                categories_detected=result.rgpd.categories_detected,
                anonymized_text=result.rgpd.anonymized_text
            ),
            meta_analysis=MetaAnalysis(
                quality_score=ext.meta_analysis.quality_score if ext else 0.0,
                advisor_feedback=ext.meta_analysis.advisor_feedback if ext else None,
                missing_info=ext.meta_analysis.missing_info if ext else [],
                risk_flags=ext.meta_analysis.risk_flags if ext else []
            ),
            pilier_1_univers_produit=ext.pilier_1_univers_produit.model_dump() if ext else {},
            pilier_2_profil_client=ext.pilier_2_profil_client.model_dump() if ext else {},
            pilier_3_hospitalite_care=ext.pilier_3_hospitalite_care.model_dump() if ext else {},
            pilier_4_action_business=ext.pilier_4_action_business.model_dump() if ext else {},
            processed_text=result.processed_text,
            original_text=result.original_text,
            processing_time_ms=processing_time,
            cache_hit=result.from_cache,
            model_used=getattr(result, 'model_used', "hybrid")
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch history of notes for current user."""
    try:
        notes = db.query(Note).filter(Note.advisor_id == current_user.id).order_by(Note.timestamp.desc()).all()
        
        # Simple serialization
        return [
            {
                "id": n.id,
                "date": n.timestamp.isoformat(),
                "transcription": n.transcription,
                "points": n.points_awarded,
                "client": n.client.name if n.client else "Inconnu"
            }
            for n in notes
        ]
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch history")
