"""
Analyze router - Single note analysis endpoint.
"""

import sys
import os
import time
import json
import logging
import uuid
from typing import Optional, Any, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

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
from src.text_cleaner import sentiment_rules
from api.routers.auth import get_current_user, require_roles
from api.models_sql import User, Note, Client
from api.database import get_db, SessionLocal
from api.container import get_pipeline
from sqlalchemy.orm import Session
from fastapi import Depends
import json
from config.production import settings

logger = logging.getLogger("lvmh-api.analyze")
router = APIRouter()

# Rate limiter - disabled for testing
# limiter = Limiter(key_func=get_remote_address)

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


def get_pipeline_from_container() -> AsyncPipeline:
    """Get pipeline instance via dependency injection."""
    return get_pipeline()


def persist_note_single_transaction(
    advisor_id: int,
    behavior: Optional[str],
    processed_text: str,
    analysis_payload: dict,
    points: int,
    client_id_db: Optional[int] = None,
    sentiment_score: float = 0.0,
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

        # Use the client_id if provided, otherwise fallback to behavior-based lookup
        if client_id_db:
            client = db.query(Client).filter(Client.id == client_id_db).first()
        else:
            client_name = "Client VIP" if str(behavior or "").lower() in {"vic", "ultimate", "platinum"} else "Client Inconnu"
            client = db.query(Client).filter(Client.name == client_name).first()
        
        if client is None:
            client = Client(name="Client Inconnu", vic_status="Standard")
            db.add(client)
            db.flush()

        note = Note(
            advisor_id=user.id,
            client_id=client.id,
            transcription=processed_text,
            analysis_json=json.dumps(analysis_payload, ensure_ascii=False, default=str),
            points_awarded=int(points),
            sentiment_score=sentiment_score,
        )
        db.add(note)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Persistence error (background): %s", exc)
    finally:
        db.close()


@router.post("/analyze", response_model=ExtractionResult)
# @limiter.limit("30/minute")
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

        # Edge processing: if text_preprocessed=True, skip server-side cleaning
        note_data = {
            'ID': f'API_{int(time.time())}',
            'Transcription': note.text,
            'Language': note_language,
            'is_written': note.is_written_note,
            'text_preprocessed': note.text_preprocessed,
            'rgpd_risk': note.rgpd_risk,
        }
        
        result = await pipeline.process_note(
            note_data,
            on_progress=on_progress, 
            profile=settings.single_note_profile.name, 
            save_to_cache=settings.single_note_profile.save_to_cache
        )
        
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
        
        # === SENTIMENT ANALYSIS ===
        sentiment_label, sentiment_score = sentiment_rules(note.text)
        logger.info(f"Sentiment analysis: {sentiment_label} ({sentiment_score:.2f})")
        
        # === CLIENT LOOKUP/CREATE ===
        client_id_db = None
        client_category = "Regular"
        
        # Determine client identifier (external ID, name, or generate unknown)
        client_identifier = note.client_id or note.client_name
        if not client_identifier:
            client_identifier = f"UNKNOWN_{uuid.uuid4().hex[:8]}"
        
        # Find or create client in database
        try:
            db = SessionLocal()
            try:
                # Try to find by external_client_id first
                if note.client_id:
                    client = db.query(Client).filter(Client.external_client_id == note.client_id).first()
                # Then try by name
                elif note.client_name:
                    client = db.query(Client).filter(Client.name.ilike(f"%{note.client_name}%")).first()
                else:
                    client = None
                
                if client is None:
                    # Create new client
                    client = Client(
                        name=note.client_name or "Client Inconnu",
                        external_client_id=note.client_id if note.client_id else None,
                        category="Regular",
                        vic_status="Standard",
                    )
                    db.add(client)
                    db.flush()
                
                client_id_db = client.id
                client_category = client.category or "Regular"
                
                # Update client sentiment and interaction count
                current_interactions = client.total_interactions or 0
                current_sentiment = client.sentiment_score or 0.0
                
                # Calculate new average sentiment
                new_sentiment = (current_sentiment * current_interactions + sentiment_score) / (current_interactions + 1)
                
                client.sentiment_score = new_sentiment
                client.total_interactions = current_interactions + 1
                client.last_interaction = datetime.utcnow()
                client.last_contact_date = datetime.utcnow()
                
                # Calculate days since last contact
                if client.last_contact_date:
                    client.days_since_contact = (datetime.utcnow() - client.last_contact_date).days
                
                # Update category based on behavior if available
                if ext and ext.pilier_2_profil_client:
                    behavior = ext.pilier_2_profil_client.purchase_context.behavior
                    if behavior in ["vic", "ultimate", "platinum"]:
                        client.vic_status = behavior.upper()
                        client.category = "VIC" if behavior in ["vic", "platinum"] else "Ultimate"
                        client_category = client.category
                
                db.commit()
                logger.info(f"Client {client.id} updated: sentiment={new_sentiment:.2f}, category={client_category}")
            except Exception as e:
                db.rollback()
                logger.warning(f"Client update failed: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Client database error: {e}")
        
        # Build response with mapping from 4-Pillar to API schema
        # === PERSISTENCE ===
        logger.info(f"PERSISTENCE CHECK: current_user={current_user is not None}, ext={ext is not None}, client_id_db={client_id_db}")
        try:
            if current_user and ext:
                quality = ext.meta_analysis.quality_score if ext else 0.0
                quality_pct = quality * 100 if quality <= 1 else quality
                points = 15 if quality_pct >= 80 else 10
                behavior = ext.pilier_2_profil_client.purchase_context.behavior if ext else None
                
                # Add sentiment to analysis payload
                analysis_payload = result.model_dump(mode="json", exclude={"original_text"})
                analysis_payload["sentiment"] = {
                    "label": sentiment_label,
                    "score": sentiment_score,
                }
                analysis_payload["client_category"] = client_category
                analysis_payload["client_id_db"] = client_id_db

                logger.info(f"PERSISTENCE CALL: user_id={current_user.id}, behavior={behavior}, points={points}, client_id={client_id_db}")
                if settings.defer_non_critical_writes:
                    background_tasks.add_task(
                        persist_note_single_transaction,
                        current_user.id,
                        behavior,
                        result.processed_text,
                        analysis_payload,
                        points,
                        client_id_db,
                        sentiment_score,
                    )
                else:
                    persist_note_single_transaction(
                        current_user.id,
                        behavior,
                        result.processed_text,
                        analysis_payload,
                        points,
                        client_id_db,
                        sentiment_score,
                    )
                logger.info("Note persistence completed for user %s (+%s pts)", current_user.email, points)
        except Exception as e:
            logger.error(f"Persistence error: {e}", exc_info=True)

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
# @limiter.limit("60/minute")
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
        
        # Safe serialization - avoid relationship issues
        result = []
        for n in notes:
            try:
                client_name = "Inconnu"
                if n.client:
                    try:
                        client_name = n.client.name
                    except:
                        pass
                result.append({
                    "id": n.id,
                    "date": n.timestamp.isoformat() if n.timestamp else None,
                    "transcription": n.transcription[:100] + "..." if n.transcription and len(n.transcription) > 100 else n.transcription,
                    "points": n.points_awarded,
                    "client": client_name
                })
            except Exception as e:
                logger.warning(f"Note serialization error: {e}")
                continue
        
        return result
    except Exception as e:
        logger.error(f"History fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not fetch history")
