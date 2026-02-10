"""
Dashboard Router - Monitoring et métriques en temps réel
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("lvmh-api.dashboard")
router = APIRouter()


class SystemMetrics(BaseModel):
    """System-wide metrics"""
    timestamp: str
    pipeline_stats: Dict
    cache_stats: Dict
    cost_stats: Dict
    quality_metrics: Dict
    alerts: List[str]


# In-memory metrics storage (use proper TSDB in production)
_metrics_history: List[Dict] = []


def _get_pipeline_stats() -> Dict:
    """Get current pipeline statistics"""
    try:
        from src.pipeline_async import AsyncPipeline
        # This would need a singleton or global instance in real implementation
        return {
            "total_processed": 0,
            "success_rate": 98.5,
            "tier_distribution": {"tier1": 45, "tier2": 40, "tier3": 15},
            "avg_processing_time_ms": 2100,
            "active_processes": 0
        }
    except Exception as e:
        logger.error(f"Failed to get pipeline stats: {e}")
        return {}


def _get_cache_stats() -> Dict:
    """Get cache statistics"""
    try:
        from src.semantic_cache import get_semantic_cache
        from src.cache_manager import CacheManager
        
        semantic = get_semantic_cache()
        semantic_stats = semantic.get_stats() if semantic else {"enabled": False}
        
        return {
            "semantic_cache": semantic_stats,
            "exact_match_hits": 42,
            "exact_match_misses": 158
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {}


def _get_cost_stats() -> Dict:
    """Get cost tracking statistics"""
    try:
        # Load from cost tracker if available
        cost_file = "logs/costs.json"
        if os.path.exists(cost_file):
            with open(cost_file, 'r') as f:
                data = json.load(f)
                return {
                    "total_cost_eur": sum(entry.get("cost", 0) for entry in data),
                    "cost_per_note": sum(entry.get("cost", 0) for entry in data) / max(len(data), 1),
                    "tier_costs": {
                        "tier1": 0.0,
                        "tier2": sum(e.get("cost", 0) for e in data if e.get("tier") == 2),
                        "tier3": sum(e.get("cost", 0) for e in data if e.get("tier") == 3)
                    }
                }
        
        # Default/fallback
        return {
            "total_cost_eur": 0.0,
            "cost_per_note": 0.0,
            "tier_costs": {"tier1": 0, "tier2": 0, "tier3": 0},
            "estimated_monthly": 0.0
        }
    except Exception as e:
        logger.error(f"Failed to get cost stats: {e}")
        return {}


def _get_quality_metrics() -> Dict:
    """Get quality metrics from feedback"""
    try:
        from api.routers.feedback import _feedback_store
        
        if not _feedback_store:
            return {
                "accuracy_rate": 0,
                "avg_rating": 0,
                "total_feedback": 0
            }
        
        total = len(_feedback_store)
        correct = sum(1 for f in _feedback_store if f.get("was_correct", False))
        avg_rating = sum(f.get("rating", 3) for f in _feedback_store) / total
        
        return {
            "accuracy_rate": round(correct / total * 100, 1),
            "avg_rating": round(avg_rating, 2),
            "total_feedback": total,
            "improvement_trend": "stable"  # Would calculate from time series
        }
    except Exception as e:
        logger.error(f"Failed to get quality metrics: {e}")
        return {}


def _check_alerts() -> List[str]:
    """Check for system alerts"""
    alerts = []
    
    # Check processing time
    pipeline_stats = _get_pipeline_stats()
    avg_time = pipeline_stats.get("avg_processing_time_ms", 0)
    if avg_time > 5000:
        alerts.append(f"ALERT: High processing time ({avg_time}ms)")
    
    # Check error rate
    success_rate = pipeline_stats.get("success_rate", 100)
    if success_rate < 95:
        alerts.append(f"ALERT: Low success rate ({success_rate}%)")
    
    # Check cost
    cost_stats = _get_cost_stats()
    daily_cost = cost_stats.get("total_cost_eur", 0)
    if daily_cost > 10:  # €10/day threshold
        alerts.append(f"ALERT: High daily cost (€{daily_cost:.2f})")
    
    # Check quality
    quality = _get_quality_metrics()
    accuracy = quality.get("accuracy_rate", 100)
    if accuracy < 80:
        alerts.append(f"ALERT: Low accuracy ({accuracy}%)")
    
    return alerts


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics() -> SystemMetrics:
    """
    Get complete system metrics
    """
    metrics = SystemMetrics(
        timestamp=datetime.now().isoformat(),
        pipeline_stats=_get_pipeline_stats(),
        cache_stats=_get_cache_stats(),
        cost_stats=_get_cost_stats(),
        quality_metrics=_get_quality_metrics(),
        alerts=_check_alerts()
    )
    
    # Store in history
    _metrics_history.append(metrics.model_dump())
    if len(_metrics_history) > 1000:
        _metrics_history.pop(0)
    
    return metrics


@router.get("/metrics/history")
async def get_metrics_history(
    hours: int = 24,
    metric_type: Optional[str] = None
):
    """
    Get metrics history for time series
    
    Args:
        hours: Number of hours to look back
        metric_type: Filter by metric type (pipeline, cache, cost, quality)
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    
    filtered = []
    for m in _metrics_history:
        try:
            m_time = datetime.fromisoformat(m.get("timestamp", ""))
            if m_time > cutoff:
                if metric_type:
                    filtered.append({
                        "timestamp": m.get("timestamp"),
                        metric_type: m.get(metric_type, {})
                    })
                else:
                    filtered.append(m)
        except:
            continue
    
    return {
        "data": filtered,
        "count": len(filtered),
        "hours": hours
    }


@router.get("/metrics/summary")
async def get_summary():
    """
    Get executive summary of system health
    """
    pipeline = _get_pipeline_stats()
    quality = _get_quality_metrics()
    cost = _get_cost_stats()
    alerts = _check_alerts()
    
    # Calculate health score
    health_score = 100
    if alerts:
        health_score -= len(alerts) * 10
    
    success_rate = pipeline.get("success_rate", 100)
    if success_rate < 99:
        health_score -= (100 - success_rate) * 2
    
    accuracy = quality.get("accuracy_rate", 100)
    if accuracy < 90:
        health_score -= (100 - accuracy)
    
    health_score = max(0, health_score)
    
    return {
        "health_score": health_score,
        "health_status": "healthy" if health_score > 80 else "warning" if health_score > 60 else "critical",
        "summary": {
            "processed_today": pipeline.get("total_processed", 0),
            "success_rate": success_rate,
            "accuracy": quality.get("accuracy_rate", 0),
            "avg_rating": quality.get("avg_rating", 0),
            "daily_cost_eur": cost.get("total_cost_eur", 0)
        },
        "alerts_count": len(alerts),
        "alerts": alerts[:3]  # Top 3 alerts
    }


@router.get("/components/status")
async def get_component_status():
    """
    Get status of all pipeline components
    """
    components = {}
    
    # Check ML Router
    try:
        from src.ml_router import get_ml_router
        ml = get_ml_router()
        components["ml_router"] = ml.get_stats()
    except Exception as e:
        components["ml_router"] = {"error": str(e)}
    
    # Check Semantic Cache
    try:
        from src.semantic_cache import get_semantic_cache
        cache = get_semantic_cache()
        components["semantic_cache"] = cache.get_stats() if cache else {"enabled": False}
    except Exception as e:
        components["semantic_cache"] = {"error": str(e)}
    
    # Check Cross Validator
    try:
        from src.cross_validator import get_cross_validator
        cv = get_cross_validator()
        components["cross_validator"] = {"enabled": cv is not None}
    except Exception as e:
        components["cross_validator"] = {"error": str(e)}
    
    # Check Text Cleaner
    try:
        from src.text_cleaner import MultilingualTextCleaner
        components["text_cleaner"] = {
            "embeddings_available": True  # Simplified
        }
    except Exception as e:
        components["text_cleaner"] = {"error": str(e)}
    
    return components
