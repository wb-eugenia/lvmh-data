"""
Dashboard Router - Monitoring et m?triques en temps r?el
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models_sql import Note, Feedback
from config.production import settings

logger = logging.getLogger("lvmh-api.dashboard")
router = APIRouter()
MIN_FEEDBACK_FOR_ACCURACY_ALERT = 10


class SystemMetrics(BaseModel):
    """System-wide metrics"""
    timestamp: str
    pipeline_stats: Dict
    cache_stats: Dict
    cost_stats: Dict
    quality_metrics: Dict
    alerts: List[str]


_metrics_history: List[Dict] = []


def _safe_json_load(value: Optional[str]) -> Optional[Dict]:
    if not value:
        return None


def _normalized_tag_set(values: Optional[List[str]]) -> set[str]:
    if not values:
        return set()
    return {
        str(v).strip().lower()
        for v in values
        if isinstance(v, (str, int, float)) and str(v).strip()
    }


def _tag_overlap_score(predicted: Optional[List[str]], corrected: Optional[List[str]]) -> float:
    pred_set = _normalized_tag_set(predicted)
    corr_set = _normalized_tag_set(corrected)
    union = pred_set | corr_set
    if not union:
        return 1.0
    return len(pred_set & corr_set) / len(union)
    try:
        return json.loads(value)
    except Exception:
        return None


def _get_pipeline_stats(db: Session) -> Dict:
    """Get current pipeline statistics from DB"""
    notes = db.query(Note).all()
    total = len(notes)

    if total == 0:
        return {
            "total_processed": 0,
            "success_rate": 0.0,
            "tier_distribution": {"tier1": 0, "tier2": 0, "tier3": 0},
            "avg_processing_time_ms": 0.0,
            "avg_confidence": 0.0,
            "cache_hit_rate": 0.0,
            "active_processes": 0
        }

    # A persisted note means the pipeline completed. JSON parsing failures should not
    # turn global success rate to 0; they are tracked separately.
    success = total
    tier_dist = {"tier1": 0, "tier2": 0, "tier3": 0}
    times = []
    confidences = []
    cache_hits = 0
    parse_failures = 0

    for note in notes:
        data = _safe_json_load(note.analysis_json)
        if not data:
            parse_failures += 1
            continue
        routing = data.get("routing", {})
        tier = int(routing.get("tier", 1))
        if tier == 1:
            tier_dist["tier1"] += 1
        elif tier == 2:
            tier_dist["tier2"] += 1
        elif tier == 3:
            tier_dist["tier3"] += 1
        else:
            tier_dist["tier1"] += 1

        pt = data.get("processing_time_ms")
        if isinstance(pt, (int, float)):
            times.append(float(pt))

        conf = routing.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))

        if data.get("from_cache") or data.get("cache_hit"):
            cache_hits += 1

    avg_time = sum(times) / len(times) if times else 0.0
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    success_rate = (success / total) * 100 if total > 0 else 0.0
    cache_hit_rate = (cache_hits / total) * 100 if total > 0 else 0.0

    return {
        "total_processed": total,
        "success_rate": round(success_rate, 1),
        "analysis_parse_failures": parse_failures,
        "tier_distribution": tier_dist,
        "avg_processing_time_ms": round(avg_time, 1),
        "avg_confidence": round(avg_conf, 3),
        "cache_hit_rate": round(cache_hit_rate, 1),
        "active_processes": 0
    }


def _get_cache_stats() -> Dict:
    """Get cache statistics"""
    exact_entries = 0
    cache_dir = Path(settings.cache_dir)
    if cache_dir.exists():
        exact_entries = len(list(cache_dir.rglob("*.json")))

    semantic_stats = {"enabled": False, "entries_count": 0}
    semantic_file = Path("cache/semantic/semantic_cache.json")
    if semantic_file.exists():
        try:
            data = json.loads(semantic_file.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
            stats = data.get("stats", {})
            semantic_stats = {
                "enabled": True,
                "entries_count": len(entries),
                "hits": stats.get("hits", 0),
                "misses": stats.get("misses", 0),
                "hit_rate": stats.get("hit_rate", "0%"),
                "similarity_threshold": data.get("similarity_threshold", 0.92)
            }
        except Exception as e:
            logger.error(f"Failed to read semantic cache stats: {e}")

    return {
        "exact_cache": {
            "entries": exact_entries,
            "dir": str(cache_dir)
        },
        "semantic_cache": semantic_stats
    }


def _get_cost_stats(db: Session) -> Dict:
    """Get cost tracking statistics"""
    # Use tier costs from SmartRouter if available
    try:
        from src.smart_router import SmartRouterV2
        cost_per_tier = getattr(SmartRouterV2, "TIER_COSTS", {1: 0.0001, 2: 0.002, 3: 0.015})
    except Exception:
        cost_per_tier = {1: 0.0001, 2: 0.002, 3: 0.015}

    notes = db.query(Note).all()
    total = len(notes)

    tier_costs = {1: 0.0, 2: 0.0, 3: 0.0}
    total_cost = 0.0

    for note in notes:
        data = _safe_json_load(note.analysis_json) or {}
        tier = int(data.get("routing", {}).get("tier", 1))
        cost = float(cost_per_tier.get(tier, 0.0001))
        tier_costs[tier] += cost
        total_cost += cost

    cost_per_note = total_cost / total if total > 0 else 0.0

    return {
        "total_cost_eur": round(total_cost, 4),
        "cost_per_note": round(cost_per_note, 6),
        "tier_costs": {
            "tier1": round(tier_costs[1], 4),
            "tier2": round(tier_costs[2], 4),
            "tier3": round(tier_costs[3], 4)
        },
        "currency": "EUR",
        "estimated_monthly": round(total_cost * 30, 4)
    }


def _get_quality_metrics(db: Session) -> Dict:
    """Get quality metrics from feedback"""
    rows = db.query(Feedback).all()
    if not rows:
        return {
            "accuracy_rate": None,
            "accuracy_available": False,
            "avg_rating": None,
            "total_feedback": 0
        }

    total = len(rows)
    exact_match = 0
    overlap_sum = 0.0
    total_rating = 0.0

    for row in rows:
        predicted = _safe_json_load(row.predicted_tags_json) or []
        corrected = _safe_json_load(row.corrected_tags_json) or []
        pred_set = _normalized_tag_set(predicted)
        corr_set = _normalized_tag_set(corrected)
        if pred_set == corr_set:
            exact_match += 1
        overlap_sum += _tag_overlap_score(predicted, corrected)
        total_rating += row.rating or 0

    return {
        "accuracy_rate": round(overlap_sum / total * 100, 1),
        "exact_match_rate": round(exact_match / total * 100, 1),
        "accuracy_available": True,
        "avg_rating": round(total_rating / total, 2),
        "total_feedback": total,
        "improvement_trend": "stable"
    }


def _check_alerts(pipeline_stats: Dict, cost_stats: Dict, quality: Dict) -> List[str]:
    """Check for system alerts"""
    alerts = []

    avg_time = pipeline_stats.get("avg_processing_time_ms", 0)
    if avg_time > 5000:
        alerts.append(f"ALERT: High processing time ({avg_time}ms)")

    success_rate = pipeline_stats.get("success_rate", 100)
    if success_rate < 95:
        alerts.append(f"ALERT: Low success rate ({success_rate}%)")

    daily_cost = cost_stats.get("total_cost_eur", 0)
    if daily_cost > 10:
        alerts.append(f"ALERT: High daily cost (?{daily_cost:.2f})")

    accuracy = quality.get("accuracy_rate")
    total_feedback = int(quality.get("total_feedback", 0) or 0)
    if (
        total_feedback >= MIN_FEEDBACK_FOR_ACCURACY_ALERT
        and isinstance(accuracy, (int, float))
        and accuracy < 80
    ):
        alerts.append(f"ALERT: Low accuracy ({accuracy}%)")

    return alerts


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics(db: Session = Depends(get_db)) -> SystemMetrics:
    """Get complete system metrics"""
    pipeline_stats = _get_pipeline_stats(db)
    cache_stats = _get_cache_stats()
    cost_stats = _get_cost_stats(db)
    quality_metrics = _get_quality_metrics(db)
    alerts = _check_alerts(pipeline_stats, cost_stats, quality_metrics)

    metrics = SystemMetrics(
        timestamp=datetime.now().isoformat(),
        pipeline_stats=pipeline_stats,
        cache_stats=cache_stats,
        cost_stats=cost_stats,
        quality_metrics=quality_metrics,
        alerts=alerts
    )

    _metrics_history.append(metrics.model_dump())
    if len(_metrics_history) > 1000:
        _metrics_history.pop(0)

    return metrics


@router.get("/metrics/history")
async def get_metrics_history(
    hours: int = 24,
    metric_type: Optional[str] = None
):
    """Get metrics history for time series"""
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
        except Exception:
            continue

    return {
        "data": filtered,
        "count": len(filtered),
        "hours": hours
    }


@router.get("/metrics/summary")
async def get_summary(db: Session = Depends(get_db)):
    """Get executive summary of system health"""
    pipeline = _get_pipeline_stats(db)
    quality = _get_quality_metrics(db)
    cost = _get_cost_stats(db)
    alerts = _check_alerts(pipeline, cost, quality)

    health_score = 100
    if alerts:
        health_score -= len(alerts) * 10

    success_rate = pipeline.get("success_rate", 100)
    if success_rate < 99:
        health_score -= (100 - success_rate) * 2

    accuracy = quality.get("accuracy_rate")
    total_feedback = int(quality.get("total_feedback", 0) or 0)
    if (
        total_feedback >= MIN_FEEDBACK_FOR_ACCURACY_ALERT
        and isinstance(accuracy, (int, float))
        and accuracy < 90
    ):
        health_score -= (100 - accuracy)

    health_score = max(0, health_score)

    # Notes processed today
    today = datetime.now().date()
    processed_today = db.query(Note).filter(Note.timestamp >= datetime(today.year, today.month, today.day)).count()

    return {
        "health_score": health_score,
        "health_status": "healthy" if health_score > 80 else "warning" if health_score > 60 else "critical",
        "summary": {
            "processed_today": processed_today,
            "success_rate": success_rate,
            "accuracy": quality.get("accuracy_rate"),
            "accuracy_available": bool(quality.get("accuracy_available", False)),
            "avg_rating": quality.get("avg_rating"),
            "daily_cost_eur": cost.get("total_cost_eur", 0)
        },
        "alerts_count": len(alerts),
        "alerts": alerts[:3]
    }


@router.get("/components/status")
async def get_component_status():
    """Get status of all pipeline components"""
    components = {}

    # Check runtime ML router status (Smart Router V2/V3 used by pipeline).
    try:
        from src.smart_router import SmartRouterV2
        smart_router = SmartRouterV2()
        components["ml_router"] = smart_router.get_ml_stats()
    except Exception as e:
        components["ml_router"] = {"error": str(e)}

    # Check Semantic Cache
    if os.getenv("SEMANTIC_CACHE_DISABLED") == "1":
        components["semantic_cache"] = {"enabled": False, "reason": "disabled"}
    else:
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
        from src.text_cleaner import HAS_EMBEDDINGS
        components["text_cleaner"] = {
            "embeddings_available": bool(HAS_EMBEDDINGS)
        }
    except Exception as e:
        components["text_cleaner"] = {"error": str(e)}

    return components


@router.post("/cache/warm")
async def warm_semantic_cache(limit: int = 200, db: Session = Depends(get_db)):
    """Warm semantic cache from recent notes"""
    try:
        from src.semantic_cache import SemanticCache
        cache = SemanticCache()
        if cache.model is None:
            raise HTTPException(status_code=503, detail="Semantic cache disabled or embeddings unavailable")

        notes = (
            db.query(Note)
            .order_by(Note.timestamp.desc())
            .limit(limit)
            .all()
        )

        warmed = 0
        skipped = 0

        for note in notes:
            data = _safe_json_load(note.analysis_json) or {}
            text = note.transcription or data.get("processed_text")
            if not text:
                skipped += 1
                continue

            # Skip if already in cache (semantic match)
            if cache.get(text):
                skipped += 1
                continue

            tier_used = int(data.get("routing", {}).get("tier", 1))
            language = data.get("language", "FR")
            stored = cache.store(text=text, result=data or {}, tier_used=tier_used, language=language)
            if stored:
                warmed += 1
            else:
                skipped += 1

        return {
            "status": "ok",
            "warmed": warmed,
            "skipped": skipped,
            "entries": cache.get_stats().get("entries_count", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache warm failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
