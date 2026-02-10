"""
Feedback Router - Syst?me de feedback et A/B Testing
Permet aux advisors de corriger les r?sultats et am?liore le mod?le
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import get_db
from api.models_sql import Feedback as FeedbackModel

logger = logging.getLogger("lvmh-api.feedback")
router = APIRouter()


class FeedbackRequest(BaseModel):
    """Feedback from advisor on extraction results"""
    note_id: str
    original_text: str
    predicted_tags: List[str]
    corrected_tags: List[str]
    corrections: Dict[str, Any] = Field(default_factory=dict)  # Field-level corrections
    rating: int = Field(ge=1, le=5)  # 1-5 satisfaction
    comment: Optional[str] = None
    advisor_id: Optional[str] = None
    processing_tier: int = 1
    actual_tier: Optional[int] = None
    routing_correct: Optional[bool] = None


class FeedbackStats(BaseModel):
    """Statistics for feedback system"""
    total_feedback: int
    accuracy_rate: float
    avg_rating: float
    top_corrections: List[dict]
    tier_distribution: dict


def _safe_json_load(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Submit feedback on extraction results
    Used to improve the ML models
    """
    try:
        was_correct = feedback.predicted_tags == feedback.corrected_tags
        routing_correct = feedback.routing_correct
        if routing_correct is None and feedback.actual_tier is not None:
            routing_correct = feedback.actual_tier == feedback.processing_tier

        entry = FeedbackModel(
            note_id=feedback.note_id,
            advisor_id=feedback.advisor_id,
            original_text=feedback.original_text,
            predicted_tags_json=json.dumps(feedback.predicted_tags, ensure_ascii=False),
            corrected_tags_json=json.dumps(feedback.corrected_tags, ensure_ascii=False),
            corrections_json=json.dumps(feedback.corrections or {}, ensure_ascii=False),
            rating=feedback.rating,
            comment=feedback.comment,
            processing_tier=feedback.processing_tier,
            actual_tier=feedback.actual_tier,
            routing_correct=routing_correct,
            created_at=datetime.utcnow()
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)

        # Add to ML Router for online learning only when actual tier is known
        if feedback.actual_tier is not None:
            try:
                from src.ml_router import get_ml_router
                ml_router = get_ml_router()
                ml_router.add_feedback(
                    text=feedback.original_text,
                    predicted_tier=feedback.processing_tier,
                    actual_tier=feedback.actual_tier,
                    was_correct=(feedback.actual_tier == feedback.processing_tier)
                )
            except Exception as e:
                logger.error(f"Failed to add ML feedback: {e}")

        logger.info(f"Feedback received for note {feedback.note_id}: rating={feedback.rating}")

        return {
            "status": "success",
            "feedback_id": entry.id,
            "message": "Feedback enregistr?, merci !",
            "was_correct": was_correct
        }

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/stats")
async def get_feedback_stats(db: Session = Depends(get_db)) -> FeedbackStats:
    """Get feedback statistics"""
    rows = db.query(FeedbackModel).all()

    if not rows:
        return FeedbackStats(
            total_feedback=0,
            accuracy_rate=0.0,
            avg_rating=0.0,
            top_corrections=[],
            tier_distribution={"1": 0, "2": 0, "3": 0}
        )

    total = len(rows)
    correct = 0
    total_rating = 0.0
    tier_dist = {"1": 0, "2": 0, "3": 0}
    corrections = {}

    for row in rows:
        predicted = _safe_json_load(row.predicted_tags_json, [])
        corrected = _safe_json_load(row.corrected_tags_json, [])
        if predicted == corrected:
            correct += 1
        total_rating += row.rating or 0

        tier_key = str(row.processing_tier or 1)
        tier_dist[tier_key] = tier_dist.get(tier_key, 0) + 1

        corr = _safe_json_load(row.corrections_json, {})
        if isinstance(corr, dict):
            for field, value in corr.items():
                key = f"{field} ? {value}"
                corrections[key] = corrections.get(key, 0) + 1

    top_corrections = [
        {"correction": k, "count": v}
        for k, v in sorted(corrections.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    avg_rating = total_rating / total if total > 0 else 0.0

    return FeedbackStats(
        total_feedback=total,
        accuracy_rate=round(correct / total * 100, 1) if total > 0 else 0.0,
        avg_rating=round(avg_rating, 2),
        top_corrections=top_corrections,
        tier_distribution=tier_dist
    )


@router.get("/feedback/recent")
async def get_recent_feedback(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent feedback entries"""
    rows = (
        db.query(FeedbackModel)
        .order_by(FeedbackModel.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(FeedbackModel).count()

    feedback = []
    for row in rows:
        feedback.append({
            "id": row.id,
            "note_id": row.note_id,
            "advisor_id": row.advisor_id,
            "original_text": row.original_text,
            "predicted_tags": _safe_json_load(row.predicted_tags_json, []),
            "corrected_tags": _safe_json_load(row.corrected_tags_json, []),
            "corrections": _safe_json_load(row.corrections_json, {}),
            "rating": row.rating,
            "comment": row.comment,
            "processing_tier": row.processing_tier,
            "actual_tier": row.actual_tier,
            "routing_correct": row.routing_correct,
            "created_at": row.created_at.isoformat() if row.created_at else None
        })

    return {
        "feedback": feedback,
        "total": total
    }


@router.post("/feedback/train")
async def trigger_training(db: Session = Depends(get_db)):
    """Trigger model retraining with collected feedback"""
    try:
        rows = db.query(FeedbackModel).all()
        texts = []
        labels = []

        for row in rows:
            if row.actual_tier is not None:
                texts.append(row.original_text)
                labels.append(int(row.actual_tier))
            elif row.routing_correct:
                texts.append(row.original_text)
                labels.append(int(row.processing_tier or 1))

        if len(texts) < 10:
            return {
                "status": "insufficient_data",
                "feedback_samples": len(rows),
                "usable_samples": len(texts),
                "message": "Pas assez de feedbacks labellis?s pour entra?ner le mod?le"
            }

        from src.ml_router import get_ml_router
        ml_router = get_ml_router()
        metrics = ml_router.train(texts, labels)

        return {
            "status": "trained",
            "feedback_samples": len(rows),
            "usable_samples": len(texts),
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Training trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
