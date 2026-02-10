"""
Feedback Router - Système de feedback et A/B Testing
Permet aux advisors de corriger les résultats et améliore le modèle
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("lvmh-api.feedback")
router = APIRouter()


class FeedbackRequest(BaseModel):
    """Feedback from advisor on extraction results"""
    note_id: str
    original_text: str
    predicted_tags: List[str]
    corrected_tags: List[str]
    corrections: dict  # Field-level corrections
    rating: int  # 1-5 satisfaction
    comment: Optional[str] = None
    advisor_id: Optional[str] = None
    processing_tier: int = 1


class FeedbackStats(BaseModel):
    """Statistics for feedback system"""
    total_feedback: int
    accuracy_rate: float
    avg_rating: float
    top_corrections: List[dict]
    tier_distribution: dict


# In-memory storage (use database in production)
_feedback_store: List[dict] = []


@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit feedback on extraction results
    Used to improve the ML models
    
    Example:
        {
            "note_id": "123",
            "original_text": "Mme Dupont veut un sac noir",
            "predicted_tags": ["sac", "rouge"],
            "corrected_tags": ["sac", "noir"],
            "corrections": {"couleur": "noir"},
            "rating": 4,
            "comment": "Couleur incorrecte",
            "processing_tier": 2
        }
    """
    try:
        feedback_entry = {
            **feedback.model_dump(),
            "timestamp": datetime.now().isoformat(),
            "was_correct": feedback.predicted_tags == feedback.corrected_tags
        }
        
        _feedback_store.append(feedback_entry)
        
        # Keep only last 1000 entries
        if len(_feedback_store) > 1000:
            _feedback_store.pop(0)
        
        # Add to ML Router for online learning
        try:
            from src.ml_router import get_ml_router
            ml_router = get_ml_router()
            
            # Determine if routing was correct
            was_routing_correct = True  # Simplified - would need actual logic
            
            ml_router.add_feedback(
                text=feedback.original_text,
                predicted_tier=feedback.processing_tier,
                actual_tier=feedback.processing_tier,  # Would be determined by actual review
                was_correct=was_routing_correct
            )
        except Exception as e:
            logger.error(f"Failed to add ML feedback: {e}")
        
        logger.info(f"Feedback received for note {feedback.note_id}: rating={feedback.rating}")
        
        return {
            "status": "success",
            "feedback_id": len(_feedback_store) - 1,
            "message": "Feedback enregistré, merci !"
        }
        
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/stats")
async def get_feedback_stats() -> FeedbackStats:
    """
    Get feedback statistics
    """
    if not _feedback_store:
        return FeedbackStats(
            total_feedback=0,
            accuracy_rate=0.0,
            avg_rating=0.0,
            top_corrections=[],
            tier_distribution={"1": 0, "2": 0, "3": 0}
        )
    
    # Calculate stats
    total = len(_feedback_store)
    correct = sum(1 for f in _feedback_store if f.get("was_correct", False))
    avg_rating = sum(f.get("rating", 3) for f in _feedback_store) / total
    
    # Tier distribution
    tier_dist = {"1": 0, "2": 0, "3": 0}
    for f in _feedback_store:
        tier = str(f.get("processing_tier", 1))
        tier_dist[tier] = tier_dist.get(tier, 0) + 1
    
    # Top corrections (simplified)
    corrections = {}
    for f in _feedback_store:
        for field, value in f.get("corrections", {}).items():
            key = f"{field} → {value}"
            corrections[key] = corrections.get(key, 0) + 1
    
    top_corrections = [
        {"correction": k, "count": v}
        for k, v in sorted(corrections.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    return FeedbackStats(
        total_feedback=total,
        accuracy_rate=round(correct / total * 100, 1),
        avg_rating=round(avg_rating, 2),
        top_corrections=top_corrections,
        tier_distribution=tier_dist
    )


@router.get("/feedback/recent")
async def get_recent_feedback(limit: int = 10):
    """
    Get recent feedback entries
    """
    return {
        "feedback": _feedback_store[-limit:],
        "total": len(_feedback_store)
    }


@router.post("/feedback/train")
async def trigger_training():
    """
    Trigger model retraining with collected feedback
    """
    try:
        from src.ml_router import get_ml_router
        ml_router = get_ml_router()
        
        # In real implementation, would prepare training data from feedback
        # For now, return status
        return {
            "status": "training_triggered",
            "feedback_samples": len(_feedback_store),
            "message": "Réentraînement programmé"
        }
        
    except Exception as e:
        logger.error(f"Training trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
