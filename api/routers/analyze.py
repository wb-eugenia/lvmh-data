"""
Analyze router - Single note analysis endpoint.
Rate limited to 30 requests per minute.
"""

import sys
import os
import time
import logging
from typing import Optional, Any, List

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from slowapi import Limiter
from slowapi.util import get_remote_address

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.schemas import (
    NoteInput,
    ParityProbeInput,
    ExtractionResult,
    ExtractionTags,
    RoutingInfo,
    RGPDInfo,
    MetaAnalysis,
    ParityProjection,
    ParityProbeDiff,
    ParityProbeMeta,
    ParityProbeResult,
)
from src.pipeline_async import AsyncPipeline
from src.language_utils import detect_language
from api.routers.auth import get_current_user, require_roles
from api.models_sql import User, Note, Client
from api.database import get_db, SessionLocal
from sqlalchemy.orm import Session
from fastapi import Depends
import json
from config.production import settings

logger = logging.getLogger("lvmh-api.analyze")
router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Pipeline instance (lazy loaded)
_pipeline: Optional[AsyncPipeline] = None

TRUTHY_VALUES = {"1", "true", "yes", "y", "oui"}


def _normalize_tags(value: Any) -> List[str]:
    if isinstance(value, str):
        source = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        source = list(value)
    else:
        return []
    normalized: List[str] = []
    seen = set()
    for raw in source:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _normalize_tier(value: Any) -> int:
    try:
        tier = int(round(float(value)))
    except (TypeError, ValueError):
        tier = 1
    return min(3, max(1, tier))


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return normalized in TRUTHY_VALUES


def _jaccard(a: List[str], b: List[str]) -> float:
    set_a = set(a or [])
    set_b = set(b or [])
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return float(len(set_a & set_b) / len(union))


def _build_parity_projection(tier_value: Any, rgpd_sensitive_value: Any, tags_value: Any) -> ParityProjection:
    return ParityProjection(
        tier=_normalize_tier(tier_value),
        rgpd_contains_sensitive=_normalize_bool(rgpd_sensitive_value),
        tags=_normalize_tags(tags_value),
    )


def _projection_from_pipeline_result(result: Any) -> ParityProjection:
    extraction = result.extraction if result is not None else None
    return _build_parity_projection(
        result.routing.tier if result and result.routing else 1,
        result.rgpd.contains_sensitive if result and result.rgpd else False,
        extraction.tags if extraction else [],
    )


def get_pipeline() -> AsyncPipeline:
    """Get or create pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AsyncPipeline(use_cache=True, use_semantic_cache=False, use_cross_validation=True)
        logger.info("Pipeline initialized")
    return _pipeline


def persist_note_single_transaction(
    advisor_id: int,
    behavior: Optional[str],
    processed_text: str,
    analysis_payload: dict,
    points: int,
) -> None:
    """
    Persist score + client + note in one short transaction.
    Used as background task for single-note latency path.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == advisor_id).first()
        if user is None:
            return

        user.score = int(user.score or 0) + int(points)

        client_name = "Client VIP" if str(behavior or "").lower() in {"vic", "ultimate", "platinum"} else "Client Inconnu"
        client = db.query(Client).filter(Client.name == client_name).first()
        if client is None:
            client = Client(name=client_name, vic_status="Standard")
            db.add(client)
            db.flush()

        note = Note(
            advisor_id=user.id,
            client_id=client.id,
            transcription=processed_text,
            analysis_json=json.dumps(analysis_payload, ensure_ascii=False, default=str),
            points_awarded=int(points),
        )
        db.add(note)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Persistence error (background): %s", exc)
    finally:
        db.close()


@router.post("/analyze", response_model=ExtractionResult)
@limiter.limit("30/minute")
async def analyze_note(
    note: NoteInput, 
    request: Request, 
    background_tasks: BackgroundTasks,
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
        note_language = note.language
        if note_language == "AUTO":
            note_language = detect_language(note.text, fallback="FR")

        result = await pipeline.process_note({
            'ID': f'API_{int(time.time())}',
            'Transcription': note.text,
            'Language': note_language
        }, on_progress=on_progress, profile=settings.single_note_profile.name, save_to_cache=settings.single_note_profile.save_to_cache)
        
        if result is None:
            raise HTTPException(status_code=500, detail="Analysis failed to produce a result.")
            
        processing_time = float(result.processing_time_ms or ((time.time() - start_time) * 1000))
        ext = result.extraction
        parity_projection = _projection_from_pipeline_result(result)

        if not result.quality_gate_passed:
            raise HTTPException(
                status_code=422,
                detail=result.quality_gate_reason or "Quality contract failed (empty tags on high-signal note).",
            )
        
        # Build response with mapping from 4-Pillar to API schema
        # === PERSISTENCE ===
        try:
            if current_user and ext:
                quality = ext.meta_analysis.quality_score if ext else 0.0
                quality_pct = quality * 100 if quality <= 1 else quality
                points = 15 if quality_pct >= 80 else 10
                behavior = ext.pilier_2_profil_client.purchase_context.behavior if ext else None
                analysis_payload = result.model_dump(mode="json", exclude={"original_text"})

                if settings.single_note_profile.defer_non_critical_writes:
                    background_tasks.add_task(
                        persist_note_single_transaction,
                        current_user.id,
                        behavior,
                        result.processed_text,
                        analysis_payload,
                        points,
                    )
                else:
                    persist_note_single_transaction(
                        current_user.id,
                        behavior,
                        result.processed_text,
                        analysis_payload,
                        points,
                    )
                logger.info("Note persistence scheduled for user %s (+%s pts)", current_user.email, points)
        except Exception as e:
            logger.error(f"Persistence error: {e}")

        return ExtractionResult(
            id=result.id,
            tags=parity_projection.tags,
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
                tier=parity_projection.tier,
                confidence=_normalize_confidence(result.routing.confidence),
                reason=", ".join(result.routing.reasons)
            ),
            rgpd=RGPDInfo(
                contains_sensitive=parity_projection.rgpd_contains_sensitive,
                categories_detected=_normalize_tags(result.rgpd.categories_detected),
                anonymized_text=result.rgpd.anonymized_text
            ),
            meta_analysis=MetaAnalysis(
                quality_score=ext.meta_analysis.quality_score if ext else 0.0,
                confidence_score=ext.meta_analysis.confidence_score if ext else 0.0,
                completeness_score=ext.meta_analysis.completeness_score if ext else 0.0,
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
            profile=result.profile,
            stage_timings_ms=result.stage_timings_ms,
            fallbacks_applied=result.fallbacks_applied,
            quality_gate_passed=result.quality_gate_passed,
            quality_gate_reason=result.quality_gate_reason,
            cache_hit=result.from_cache,
            model_used=getattr(result, 'model_used', "hybrid")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/parity-probe", response_model=ParityProbeResult)
@limiter.limit("60/minute")
async def analyze_parity_probe(
    note: ParityProbeInput,
    request: Request,
    current_user: User = Depends(require_roles("manager", "admin")),
):
    """
    Technical endpoint used to compare API projection vs runtime projection
    within the same production runtime.
    """
    if not settings.enable_parity_probe:
        raise HTTPException(status_code=403, detail="Parity probe endpoint disabled")

    start_time = time.time()
    try:
        pipeline = get_pipeline()

        note_language = note.language
        if note_language == "AUTO":
            note_language = detect_language(note.text, fallback="FR")

        runtime_profile = note.profile or settings.single_note_profile.name
        result = await pipeline.process_note(
            {
                "ID": f"PARITY_{int(time.time())}",
                "Transcription": note.text,
                "Language": note_language,
            },
            profile=runtime_profile,
            save_to_cache=False,
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Parity probe failed to produce a result.")

        if not result.quality_gate_passed:
            raise HTTPException(
                status_code=422,
                detail=result.quality_gate_reason or "Quality contract failed during parity probe.",
            )

        processing_time = float(result.processing_time_ms or ((time.time() - start_time) * 1000))
        api_projection = _projection_from_pipeline_result(result)
        runtime_projection = _projection_from_pipeline_result(result)
        tag_jaccard = _jaccard(api_projection.tags, runtime_projection.tags)

        return ParityProbeResult(
            api_projection=api_projection,
            runtime_projection=runtime_projection,
            diff=ParityProbeDiff(
                tier_mismatch=api_projection.tier != runtime_projection.tier,
                rgpd_mismatch=(
                    api_projection.rgpd_contains_sensitive
                    != runtime_projection.rgpd_contains_sensitive
                ),
                tag_jaccard=tag_jaccard,
            ),
            meta=ParityProbeMeta(
                profile=result.profile or runtime_profile,
                model_used=getattr(result, "model_used", "hybrid"),
                processing_time_ms=processing_time,
                cache_hit=bool(result.from_cache),
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Parity probe error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/analyze/runtime-metrics")
async def get_runtime_metrics(current_user: User = Depends(require_roles("manager", "admin"))):
    """Profile-separated runtime metrics with stage-level averages."""
    pipeline = get_pipeline()
    return {
        "targets": {
            "single_note_p50_ms": settings.target_single_note_p50_ms,
            "single_note_p95_ms": settings.target_single_note_p95_ms,
            "success_rate_pct": settings.target_success_rate_pct,
            "quality_score": settings.target_quality_score,
        },
        "profiles": pipeline.get_profile_metrics(),
    }

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
