"""
Dashboard Router - Monitoring et m?triques en temps r?el
"""

import os
import json
import logging
import csv
import io
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from api.database import get_db
from api.models_sql import Client, Feedback, Note, OpportunityAction, User
from api.routers.auth import require_roles
from config.production import settings

logger = logging.getLogger("lvmh-api.dashboard")
router = APIRouter(
    dependencies=[Depends(require_roles("manager", "admin"))]
)
MIN_FEEDBACK_FOR_ACCURACY_ALERT = 10


class SystemMetrics(BaseModel):
    """System-wide metrics"""
    timestamp: str
    window: Dict[str, Optional[str]]
    pipeline_stats: Dict
    cache_stats: Dict
    cost_stats: Dict
    quality_metrics: Dict
    alerts: List[str]


class OpportunityActionUpsertPayload(BaseModel):
    note_id: int
    action_type: str
    status: str
    details: Optional[str] = None


_metrics_history: List[Dict] = []
ALLOWED_ACTION_TYPES = {"open", "call", "schedule", "assign", "other"}
ALLOWED_ACTION_STATUS = {"open", "planned", "done"}
ALLOWED_OPPORTUNITY_PRIORITY_FILTER = {"all", "urgent", "vip", "tier3"}
ALLOWED_OPPORTUNITY_SORT = {"priority", "recent", "budget", "urgency"}
ALLOWED_OPPORTUNITY_WINDOW = {"all", "today", "7d", "30d"}
DEMO_ACCOUNT_EMAILS = {"advisor@lvmh.com", "manager@lvmh.com", "admin@lvmh.com"}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolve_time_window(
    *,
    days: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    end_ts = date_to
    start_ts = date_from

    if end_ts is None and (start_ts is not None or days is not None):
        end_ts = _utcnow_naive()

    if start_ts is None and days is not None:
        if end_ts is None:
            end_ts = _utcnow_naive()
        start_ts = end_ts - timedelta(days=days)

    if start_ts and end_ts and start_ts > end_ts:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    return start_ts, end_ts


def _window_payload(start_ts: Optional[datetime], end_ts: Optional[datetime], days: Optional[int]) -> Dict[str, Optional[str]]:
    return {
        "days": str(days) if days is not None else None,
        "date_from": start_ts.isoformat() if start_ts else None,
        "date_to": end_ts.isoformat() if end_ts else None,
    }


def _apply_time_filter(query, column, start_ts: Optional[datetime], end_ts: Optional[datetime]):
    if start_ts is not None:
        query = query.filter(column >= start_ts)
    if end_ts is not None:
        query = query.filter(column <= end_ts)
    return query


def _parse_note_ids_csv(note_ids: Optional[str]) -> Optional[List[int]]:
    if not note_ids:
        return None

    parsed: List[int] = []
    for raw in note_ids.split(","):
        token = raw.strip()
        if not token:
            continue
        if not token.isdigit():
            raise HTTPException(status_code=400, detail=f"Invalid note_id value '{token}'")
        parsed.append(int(token))
    return parsed or None


def _normalize_action_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ALLOWED_ACTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type '{value}'. Allowed: {sorted(ALLOWED_ACTION_TYPES)}",
        )
    return normalized


def _normalize_action_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ALLOWED_ACTION_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{value}'. Allowed: {sorted(ALLOWED_ACTION_STATUS)}",
        )
    return normalized


def _normalize_opportunity_priority(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ALLOWED_OPPORTUNITY_PRIORITY_FILTER:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{value}'. Allowed: {sorted(ALLOWED_OPPORTUNITY_PRIORITY_FILTER)}",
        )
    return normalized


def _normalize_opportunity_sort(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ALLOWED_OPPORTUNITY_SORT:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort '{value}'. Allowed: {sorted(ALLOWED_OPPORTUNITY_SORT)}",
        )
    return normalized


def _normalize_opportunity_window(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ALLOWED_OPPORTUNITY_WINDOW:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid window '{value}'. Allowed: {sorted(ALLOWED_OPPORTUNITY_WINDOW)}",
        )
    return normalized


def _extract_budget_value(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 0:
            return numeric
        return None

    if value in (None, ""):
        return None

    text = str(value).lower()
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(k|m)?", text)
    if not matches:
        return None

    parsed: List[float] = []
    for amount_raw, suffix in matches:
        amount = float(amount_raw.replace(",", "."))
        if suffix == "m":
            amount *= 1_000_000
        elif suffix == "k":
            amount *= 1_000
        if amount > 0:
            parsed.append(amount)

    if not parsed:
        return None
    return max(parsed)


def _normalize_urgency(value: Any) -> tuple[int, str]:
    text = str(value or "").strip().lower()
    if not text:
        return 1, "Low"

    if (
        "urgent" in text
        or "high" in text
        or "immediat" in text
        or "crit" in text
        or "hot" in text
    ):
        return 3, "High"

    if (
        "medium" in text
        or "modere" in text
        or "normal" in text
        or "moyen" in text
    ):
        return 2, "Medium"

    return 1, "Low"


def _format_confidence_label(raw_confidence: Any) -> str:
    if not isinstance(raw_confidence, (int, float)):
        return "-"
    confidence = float(raw_confidence)
    if confidence <= 1:
        confidence *= 100
    return f"{round(confidence)}%"


def _get_action_label(action_status: str, action_type: str) -> str:
    if action_status == "done":
        return "Action finalisee"
    if action_type == "call":
        return "Appel planifie"
    if action_type == "schedule":
        return "Rappel planifie"
    if action_status == "planned":
        return "Action planifiee"
    return "Action en cours"


def _build_opportunity_row(note: Note) -> Dict[str, Any]:
    data = _safe_json_load(note.analysis_json) or {}
    extraction = data.get("extraction", {}) if isinstance(data, dict) else {}
    if not isinstance(extraction, dict):
        extraction = {}
    routing = data.get("routing", {}) if isinstance(data, dict) else {}
    if not isinstance(routing, dict):
        routing = {}

    p4 = extraction.get("pilier_4_action_business", {})
    if not isinstance(p4, dict):
        p4 = {}

    urgency_level, urgency_label = _normalize_urgency(
        p4.get("urgency") or p4.get("priority") or p4.get("lead_temperature")
    )
    budget_value = _extract_budget_value(p4.get("budget_specific") or p4.get("budget_potential"))
    budget_label = (
        p4.get("budget_specific")
        or p4.get("budget_potential")
        or (f"{int(budget_value)}" if budget_value is not None else "-")
    )

    next_action_value = p4.get("next_best_action")
    next_action = None
    if isinstance(next_action_value, dict):
        next_action = (
            next_action_value.get("description")
            or next_action_value.get("title")
            or next_action_value.get("label")
        )
    elif isinstance(next_action_value, str):
        next_action = next_action_value

    if not next_action and isinstance(data, dict):
        root_nba = data.get("next_best_action")
        if isinstance(root_nba, dict):
            next_action = root_nba.get("description") or root_nba.get("title")
        elif isinstance(root_nba, str):
            next_action = root_nba

    if not next_action:
        next_action = "Relance conseiller recommandee."

    tier_raw = routing.get("tier", 1)
    try:
        tier = int(tier_raw)
    except Exception:
        tier = 1
    if tier not in (1, 2, 3):
        tier = 1

    raw_confidence = routing.get("confidence")
    confidence_numeric = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.0
    confidence_ratio = confidence_numeric if confidence_numeric <= 1 else confidence_numeric / 100.0

    vip_label = (note.client.vic_status if note.client else None) or "Standard"
    is_vip = vip_label != "Standard"

    tier_score = 30 if tier == 3 else 18 if tier == 2 else 8
    urgency_score = urgency_level * 15
    vip_score = 25 if is_vip else 0
    budget_score = min(35.0, budget_value / 2000.0) if budget_value else 0.0
    confidence_score = round(confidence_ratio * 12)
    priority_score = round(tier_score + urgency_score + vip_score + budget_score + confidence_score)

    action = note.opportunity_action
    action_status = (str(action.status).strip().lower() if action and action.status else "open")
    action_type = (str(action.action_type).strip().lower() if action and action.action_type else "")
    action_label = _get_action_label(action_status, action_type)

    advisor_name = "Inconnu"
    advisor_store = "N/A"
    if note.advisor:
        advisor_name = note.advisor.full_name or note.advisor.email or "Inconnu"
        advisor_store = note.advisor.store or "N/A"

    row = {
        "note_id": note.id,
        "timestamp": note.timestamp.isoformat() if note.timestamp else None,
        "client_name": (note.client.name if note.client else None) or "Client inconnu",
        "advisor_name": advisor_name,
        "advisor_store": advisor_store,
        "vip_label": vip_label,
        "is_vip": is_vip,
        "tier": tier,
        "urgency_level": urgency_level,
        "urgency": urgency_label,
        "next_action": str(next_action),
        "budget_value": budget_value,
        "budget_label": str(budget_label) if budget_label is not None else "-",
        "confidence": _format_confidence_label(raw_confidence),
        "priority_score": priority_score,
        "churn_risk": p4.get("churn_risk"),
        "churn_level": p4.get("churn_level"),
        "clv_estimate": p4.get("clv_estimate"),
        "clv_tier": p4.get("clv_tier"),
        "prediction_source": p4.get("prediction_source"),
        "action_status": action_status,
        "action_type": action_type,
        "action_label": action_label,
        "action_updated_at": action.updated_at.isoformat() if action and action.updated_at else None,
        "manager_name": (action.manager.full_name or action.manager.email) if action and action.manager else None,
    }
    row["_timestamp_dt"] = note.timestamp
    row["_search_blob"] = (
        f"{row['client_name']} {row['advisor_name']} {row['next_action']} "
        f"{row['vip_label']} {row['budget_label']}"
    ).lower()
    return row


def _flatten_for_csv(prefix: str, value: Any, rows: List[tuple[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_for_csv(next_prefix, nested, rows)
        return
    if isinstance(value, list):
        rows.append((prefix, "; ".join(str(item) for item in value)))
        return
    rows.append((prefix, value))


def _get_cost_per_tier() -> Dict[int, float]:
    try:
        from src.smart_router import SmartRouterV2

        raw_costs = getattr(SmartRouterV2, "TIER_COSTS", {1: 0.0001, 2: 0.002, 3: 0.015})
        return {
            1: float(raw_costs.get(1, 0.0001)),
            2: float(raw_costs.get(2, 0.002)),
            3: float(raw_costs.get(3, 0.015)),
        }
    except Exception:
        return {1: 0.0001, 2: 0.002, 3: 0.015}


def _normalize_str_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    for value in values:
        if isinstance(value, (str, int, float)):
            item = str(value).strip()
            if item:
                normalized.append(item)
    return normalized


def _extract_audio_sources(payload: Any, path: str = "") -> List[Dict[str, str]]:
    """Best effort extraction of audio/recording URLs or file paths from nested payload."""
    hits: List[Dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}" if path else str(key)
            key_l = str(key).lower()

            if isinstance(value, str):
                value_l = value.lower()
                key_has_audio_hint = any(token in key_l for token in ("audio", "record", "media", "source"))
                value_has_audio_hint = value_l.endswith((".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac", ".flac"))
                if key_has_audio_hint or value_has_audio_hint:
                    hits.append(
                        {
                            "path": next_path,
                            "value": value,
                        }
                    )
            else:
                hits.extend(_extract_audio_sources(value, next_path))
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            next_path = f"{path}[{idx}]"
            hits.extend(_extract_audio_sources(value, next_path))
    return hits


def _derive_tags(extraction: Dict[str, Any]) -> List[str]:
    explicit = _normalize_str_list(extraction.get("tags"))
    if explicit:
        return explicit

    p1 = extraction.get("pilier_1_univers_produit", {}) if isinstance(extraction, dict) else {}
    p2 = extraction.get("pilier_2_profil_client", {}) if isinstance(extraction, dict) else {}
    p3 = extraction.get("pilier_3_hospitalite_care", {}) if isinstance(extraction, dict) else {}
    p4 = extraction.get("pilier_4_action_business", {}) if isinstance(extraction, dict) else {}

    combined: List[str] = []
    combined.extend(_normalize_str_list(p1.get("categories")))
    combined.extend(_normalize_str_list(p1.get("styles")))
    preferences = p1.get("preferences", {}) if isinstance(p1, dict) else {}
    combined.extend(_normalize_str_list(preferences.get("colors")))
    combined.extend(_normalize_str_list(preferences.get("materials")))
    purchase_context = p2.get("purchase_context", {}) if isinstance(p2, dict) else {}
    combined.extend(_normalize_str_list(purchase_context.get("events")))
    combined.extend(_normalize_str_list(p3.get("allergies")))
    combined.extend(_normalize_str_list(p3.get("preferred_contact")))
    combined.extend(_normalize_str_list(p4.get("follow_up_actions")))

    # De-duplicate while preserving order.
    seen = set()
    deduped: List[str] = []
    for item in combined:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _safe_json_load(value: Optional[str]) -> Optional[Dict]:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
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


def _get_pipeline_stats(
    db: Session,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
) -> Dict:
    """Get current pipeline statistics from DB"""
    notes_query = _apply_time_filter(db.query(Note), Note.timestamp, start_ts, end_ts)
    notes = notes_query.all()
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


def _get_cost_stats(
    db: Session,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
) -> Dict:
    """Get cost tracking statistics"""
    cost_per_tier = _get_cost_per_tier()

    notes_query = _apply_time_filter(db.query(Note), Note.timestamp, start_ts, end_ts)
    notes = notes_query.all()
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


def _build_daily_series(
    db: Session,
    start_ts: datetime,
    end_ts: datetime,
) -> List[Dict[str, Any]]:
    cost_per_tier = _get_cost_per_tier()
    notes = _apply_time_filter(db.query(Note), Note.timestamp, start_ts, end_ts).all()
    feedback_rows = _apply_time_filter(db.query(Feedback), Feedback.created_at, start_ts, end_ts).all()

    daily: Dict[str, Dict[str, Any]] = {}
    day_cursor = start_ts.date()
    end_date = end_ts.date()
    while day_cursor <= end_date:
        key = day_cursor.isoformat()
        daily[key] = {
            "date": key,
            "notes_processed": 0,
            "parsed_notes": 0,
            "processing_time_sum_ms": 0.0,
            "processing_time_count": 0,
            "cost_eur": 0.0,
            "tier_distribution": {"tier1": 0, "tier2": 0, "tier3": 0},
            "feedback_count": 0,
            "accuracy_overlap_sum": 0.0,
            "alerts": [],
        }
        day_cursor += timedelta(days=1)

    for note in notes:
        if not note.timestamp:
            continue
        key = note.timestamp.date().isoformat()
        if key not in daily:
            continue
        bucket = daily[key]
        bucket["notes_processed"] += 1

        data = _safe_json_load(note.analysis_json) or {}
        if data:
            bucket["parsed_notes"] += 1

        routing = data.get("routing", {})
        tier = int(routing.get("tier", 1))
        if tier == 1:
            bucket["tier_distribution"]["tier1"] += 1
        elif tier == 2:
            bucket["tier_distribution"]["tier2"] += 1
        elif tier == 3:
            bucket["tier_distribution"]["tier3"] += 1
        else:
            bucket["tier_distribution"]["tier1"] += 1
            tier = 1

        pt = data.get("processing_time_ms")
        if isinstance(pt, (int, float)):
            bucket["processing_time_sum_ms"] += float(pt)
            bucket["processing_time_count"] += 1

        bucket["cost_eur"] += float(cost_per_tier.get(tier, cost_per_tier[1]))

    for row in feedback_rows:
        if not row.created_at:
            continue
        key = row.created_at.date().isoformat()
        if key not in daily:
            continue
        bucket = daily[key]
        predicted = _safe_json_load(row.predicted_tags_json) or []
        corrected = _safe_json_load(row.corrected_tags_json) or []
        bucket["feedback_count"] += 1
        bucket["accuracy_overlap_sum"] += _tag_overlap_score(predicted, corrected)

    series: List[Dict[str, Any]] = []
    for key in sorted(daily.keys()):
        bucket = daily[key]
        notes_processed = int(bucket["notes_processed"])
        parsed_notes = int(bucket["parsed_notes"])
        feedback_count = int(bucket["feedback_count"])
        avg_processing = (
            bucket["processing_time_sum_ms"] / bucket["processing_time_count"]
            if bucket["processing_time_count"] > 0
            else 0.0
        )
        success_rate = (parsed_notes / notes_processed * 100) if notes_processed > 0 else 0.0
        accuracy_rate = (
            round(bucket["accuracy_overlap_sum"] / feedback_count * 100, 1)
            if feedback_count > 0
            else None
        )

        pipeline_snapshot = {
            "avg_processing_time_ms": round(avg_processing, 1),
            "success_rate": round(success_rate, 1),
        }
        cost_snapshot = {"total_cost_eur": round(float(bucket["cost_eur"]), 4)}
        quality_snapshot = {
            "accuracy_rate": accuracy_rate,
            "total_feedback": feedback_count,
            "accuracy_available": feedback_count > 0,
        }
        alerts = _check_alerts(pipeline_snapshot, cost_snapshot, quality_snapshot)

        series.append(
            {
                "date": key,
                "notes_processed": notes_processed,
                "success_rate": pipeline_snapshot["success_rate"],
                "avg_processing_time_ms": pipeline_snapshot["avg_processing_time_ms"],
                "cost_eur": cost_snapshot["total_cost_eur"],
                "feedback_count": feedback_count,
                "accuracy_rate": accuracy_rate,
                "alerts_count": len(alerts),
                "has_alerts": len(alerts) > 0,
                "tier_distribution": bucket["tier_distribution"],
            }
        )

    return series


def _get_quality_metrics(
    db: Session,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
) -> Dict:
    """Get quality metrics from feedback"""
    rows_query = _apply_time_filter(db.query(Feedback), Feedback.created_at, start_ts, end_ts)
    rows = rows_query.all()
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
async def get_metrics(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
) -> SystemMetrics:
    """Get complete system metrics"""
    start_ts, end_ts = _resolve_time_window(days=days, date_from=date_from, date_to=date_to)

    if start_ts is None and end_ts is None:
        pipeline_stats = _get_pipeline_stats(db)
        cost_stats = _get_cost_stats(db)
        quality_metrics = _get_quality_metrics(db)
    else:
        pipeline_stats = _get_pipeline_stats(db, start_ts=start_ts, end_ts=end_ts)
        cost_stats = _get_cost_stats(db, start_ts=start_ts, end_ts=end_ts)
        quality_metrics = _get_quality_metrics(db, start_ts=start_ts, end_ts=end_ts)

    cache_stats = _get_cache_stats()
    alerts = _check_alerts(pipeline_stats, cost_stats, quality_metrics)

    metrics = SystemMetrics(
        timestamp=datetime.now().isoformat(),
        window=_window_payload(start_ts, end_ts, days),
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
async def get_summary(
    days: Optional[int] = Query(default=None, ge=1, le=365),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get executive summary of system health"""
    start_ts, end_ts = _resolve_time_window(days=days, date_from=date_from, date_to=date_to)

    if start_ts is None and end_ts is None:
        pipeline = _get_pipeline_stats(db)
        quality = _get_quality_metrics(db)
        cost = _get_cost_stats(db)
    else:
        pipeline = _get_pipeline_stats(db, start_ts=start_ts, end_ts=end_ts)
        quality = _get_quality_metrics(db, start_ts=start_ts, end_ts=end_ts)
        cost = _get_cost_stats(db, start_ts=start_ts, end_ts=end_ts)

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
    processed_in_window = _apply_time_filter(db.query(Note), Note.timestamp, start_ts, end_ts).count()

    return {
        "health_score": health_score,
        "health_status": "healthy" if health_score > 80 else "warning" if health_score > 60 else "critical",
        "window": _window_payload(start_ts, end_ts, days),
        "summary": {
            "processed_today": processed_today,
            "processed_in_window": processed_in_window,
            "success_rate": success_rate,
            "accuracy": quality.get("accuracy_rate"),
            "accuracy_available": bool(quality.get("accuracy_available", False)),
            "avg_rating": quality.get("avg_rating"),
            "daily_cost_eur": cost.get("total_cost_eur", 0)
        },
        "alerts_count": len(alerts),
        "alerts": alerts[:3]
    }


@router.get("/metrics/timeseries")
async def get_metrics_timeseries(
    days: Optional[int] = Query(default=30, ge=1, le=365),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get daily trend series for admin monitoring charts."""
    effective_days = days or 30
    start_ts, end_ts = _resolve_time_window(days=effective_days, date_from=date_from, date_to=date_to)
    if start_ts is None or end_ts is None:
        end_ts = _utcnow_naive()
        start_ts = end_ts - timedelta(days=effective_days)

    series = _build_daily_series(db, start_ts=start_ts, end_ts=end_ts)
    totals = {
        "notes_processed": sum(item.get("notes_processed", 0) for item in series),
        "cost_eur": round(sum(item.get("cost_eur", 0.0) for item in series), 4),
        "alerts_count": sum(item.get("alerts_count", 0) for item in series),
        "avg_processing_time_ms": round(
            sum(item.get("avg_processing_time_ms", 0.0) for item in series) / len(series),
            1,
        ) if series else 0.0,
    }

    return {
        "window": _window_payload(start_ts, end_ts, effective_days),
        "series": series,
        "totals": totals,
    }


@router.get("/opportunities/actions")
async def get_opportunity_actions(
    status: Optional[str] = Query(default=None, pattern="^(open|planned|done)$"),
    note_ids: Optional[str] = Query(default=None),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """List persisted opportunity actions for manager command center."""
    normalized_status = _normalize_action_status(status) if status else None
    parsed_note_ids = _parse_note_ids_csv(note_ids)

    query = db.query(OpportunityAction)
    if parsed_note_ids:
        query = query.filter(OpportunityAction.note_id.in_(parsed_note_ids))
    if normalized_status:
        query = query.filter(OpportunityAction.status == normalized_status)
    if days is not None:
        cutoff = _utcnow_naive() - timedelta(days=days)
        query = query.join(Note, OpportunityAction.note_id == Note.id).filter(Note.timestamp >= cutoff)

    rows = query.order_by(OpportunityAction.updated_at.desc()).limit(limit).all()
    actions = []
    for row in rows:
        actions.append(
            {
                "id": row.id,
                "note_id": row.note_id,
                "manager_id": row.manager_id,
                "manager_name": (row.manager.full_name or row.manager.email) if row.manager else None,
                "action_type": row.action_type,
                "status": row.status,
                "details": row.details,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )

    return {"actions": actions, "count": len(actions)}


@router.post("/opportunities/actions")
async def upsert_opportunity_action(
    payload: OpportunityActionUpsertPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("manager", "admin")),
):
    """Create or update a manager action for one note."""
    normalized_action_type = _normalize_action_type(payload.action_type)
    normalized_status = _normalize_action_status(payload.status)
    details = str(payload.details).strip() if payload.details else None

    note = db.query(Note).filter(Note.id == payload.note_id).first()
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note {payload.note_id} not found")

    now = _utcnow_naive()
    action = db.query(OpportunityAction).filter(OpportunityAction.note_id == payload.note_id).first()
    if action is None:
        action = OpportunityAction(
            note_id=payload.note_id,
            manager_id=current_user.id,
            action_type=normalized_action_type,
            status=normalized_status,
            details=details,
            created_at=now,
            updated_at=now,
        )
        db.add(action)
    else:
        action.manager_id = current_user.id
        action.action_type = normalized_action_type
        action.status = normalized_status
        action.details = details
        action.updated_at = now

    db.commit()
    db.refresh(action)

    return {
        "status": "ok",
        "action": {
            "id": action.id,
            "note_id": action.note_id,
            "manager_id": action.manager_id,
            "manager_name": (action.manager.full_name or action.manager.email) if action.manager else None,
            "action_type": action.action_type,
            "status": action.status,
            "details": action.details,
            "created_at": action.created_at.isoformat() if action.created_at else None,
            "updated_at": action.updated_at.isoformat() if action.updated_at else None,
        },
    }


@router.get("/opportunities/export")
async def export_opportunities(
    format: str = Query(default="csv", pattern="^(json|csv)$"),
    window: str = Query(default="all", pattern="^(all|today|7d|30d)$"),
    priority: str = Query(default="all", pattern="^(all|urgent|vip|tier3)$"),
    advisor: Optional[str] = Query(default=None),
    action_status: str = Query(default="all", pattern="^(all|open|planned|done)$"),
    search: Optional[str] = Query(default=None),
    sort: str = Query(default="priority", pattern="^(priority|recent|budget|urgency)$"),
    limit: int = Query(default=200, ge=1, le=5000),
    note_ids: Optional[str] = Query(default=None),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("manager", "admin")),
):
    """Export manager opportunity board rows using active frontend filters."""
    normalized_window = _normalize_opportunity_window(window)
    normalized_priority = _normalize_opportunity_priority(priority)
    normalized_sort = _normalize_opportunity_sort(sort)
    normalized_action_status = action_status.strip().lower()
    parsed_note_ids = _parse_note_ids_csv(note_ids)
    advisor_filter = (advisor or "").strip().lower()
    search_filter = (search or "").strip().lower()

    # Resolve time scope from explicit days or named window.
    effective_days = days
    if effective_days is None:
        if normalized_window == "today":
            effective_days = 1
        elif normalized_window == "7d":
            effective_days = 7
        elif normalized_window == "30d":
            effective_days = 30
    start_ts, end_ts = _resolve_time_window(days=effective_days, date_from=None, date_to=None)

    notes_query = (
        db.query(Note)
        .options(
            joinedload(Note.advisor),
            joinedload(Note.client),
            joinedload(Note.opportunity_action).joinedload(OpportunityAction.manager),
        )
    )
    notes_query = _apply_time_filter(notes_query, Note.timestamp, start_ts, end_ts)
    if parsed_note_ids:
        notes_query = notes_query.filter(Note.id.in_(parsed_note_ids))

    # Pull enough candidates before in-memory filtering/sorting.
    source_limit = min(max(limit * 10, 500), 5000)
    notes = notes_query.order_by(Note.timestamp.desc()).limit(source_limit).all()

    rows: List[Dict[str, Any]] = []
    for note in notes:
        row = _build_opportunity_row(note)

        if advisor_filter and advisor_filter != "all":
            if row["advisor_name"].strip().lower() != advisor_filter:
                continue

        if normalized_priority == "urgent" and int(row["urgency_level"]) != 3:
            continue
        if normalized_priority == "vip" and not bool(row["is_vip"]):
            continue
        if normalized_priority == "tier3" and int(row["tier"]) != 3:
            continue

        status = row["action_status"]
        if normalized_action_status == "open" and status != "open":
            continue
        if normalized_action_status == "planned" and status != "planned":
            continue
        if normalized_action_status == "done" and status != "done":
            continue

        if search_filter and search_filter not in row["_search_blob"]:
            continue

        rows.append(row)

    if normalized_sort == "recent":
        rows.sort(key=lambda item: item.get("_timestamp_dt") or datetime.min, reverse=True)
    elif normalized_sort == "budget":
        rows.sort(key=lambda item: float(item.get("budget_value") or 0.0), reverse=True)
    elif normalized_sort == "urgency":
        rows.sort(
            key=lambda item: (int(item.get("urgency_level") or 1), int(item.get("priority_score") or 0)),
            reverse=True,
        )
    else:
        rows.sort(key=lambda item: int(item.get("priority_score") or 0), reverse=True)

    total_filtered = len(rows)
    rows = rows[:limit]
    for idx, row in enumerate(rows, start=1):
        row["row_index"] = idx
        row.pop("_search_blob", None)
        row.pop("_timestamp_dt", None)

    payload = {
        "generated_at": _utcnow_naive().isoformat(),
        "filters": {
            "window": normalized_window,
            "days": effective_days,
            "priority": normalized_priority,
            "advisor": advisor if advisor else "all",
            "action_status": normalized_action_status,
            "search": search or "",
            "sort": normalized_sort,
            "limit": limit,
            "note_ids": parsed_note_ids or [],
        },
        "totals": {
            "source_candidates": len(notes),
            "filtered": total_filtered,
            "returned": len(rows),
        },
        "rows": rows,
        "exported_by": current_user.email,
    }

    timestamp_slug = _utcnow_naive().strftime("%Y%m%d_%H%M%S")
    if format == "json":
        headers = {"Content-Disposition": f'attachment; filename="manager_opportunities_{timestamp_slug}.json"'}
        return JSONResponse(content=payload, headers=headers)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    columns = [
        "row_index",
        "note_id",
        "timestamp",
        "client_name",
        "advisor_name",
        "advisor_store",
        "vip_label",
        "tier",
        "urgency",
        "priority_score",
        "budget_value",
        "budget_label",
        "confidence",
        "churn_risk",
        "churn_level",
        "clv_estimate",
        "clv_tier",
        "prediction_source",
        "next_action",
        "action_status",
        "action_type",
        "action_label",
        "action_updated_at",
        "manager_name",
    ]
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(column) for column in columns])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="manager_opportunities_{timestamp_slug}.csv"'},
    )


@router.get("/segments")
async def get_note_segments(
    window: str = Query(default="7d", pattern="^(all|today|7d|30d)$"),
    advisor: Optional[str] = Query(default=None),
    n_clusters: int = Query(default=5, ge=2, le=10),
    limit: int = Query(default=1500, ge=20, le=10000),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Cluster note-level behavior into manager-ready segments."""
    from src.analytics.note_segmentation import NoteSegmentation

    normalized_window = _normalize_opportunity_window(window)
    advisor_filter = (advisor or "").strip().lower()

    effective_days = days
    if effective_days is None:
        if normalized_window == "today":
            effective_days = 1
        elif normalized_window == "7d":
            effective_days = 7
        elif normalized_window == "30d":
            effective_days = 30

    start_ts, end_ts = _resolve_time_window(days=effective_days, date_from=None, date_to=None)

    notes_query = (
        db.query(Note)
        .options(
            joinedload(Note.advisor),
            joinedload(Note.client),
        )
    )
    notes_query = _apply_time_filter(notes_query, Note.timestamp, start_ts, end_ts)
    notes = notes_query.order_by(Note.timestamp.desc()).limit(limit).all()

    raw_notes: List[Dict[str, Any]] = []
    for note in notes:
        advisor_name = (note.advisor.full_name or note.advisor.email) if note.advisor else None
        if advisor_filter and advisor_filter != "all":
            if str(advisor_name or "").strip().lower() != advisor_filter:
                continue

        raw_notes.append(
            {
                "id": note.id,
                "timestamp": note.timestamp.isoformat() if note.timestamp else None,
                "analysis_json": note.analysis_json,
                "advisor": {
                    "name": advisor_name,
                    "store": note.advisor.store if note.advisor else None,
                },
                "client": {
                    "name": note.client.name if note.client else None,
                    "vic_status": note.client.vic_status if note.client else None,
                },
            }
        )

    segmenter = NoteSegmentation(n_clusters=n_clusters)
    payload = segmenter.segment_notes(raw_notes, n_clusters=n_clusters)
    payload["window"] = _window_payload(start_ts, end_ts, effective_days)
    payload["filters"] = {
        "window": normalized_window,
        "advisor": advisor_filter or "all",
        "limit": limit,
    }
    return payload


@router.get("/metrics/day-details")
async def get_metrics_day_details(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=30, ge=1, le=300),
    db: Session = Depends(get_db),
):
    """Get detailed notes list and KPIs for one specific day."""
    try:
        day_start = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    day_end = day_start + timedelta(days=1)
    notes = (
        db.query(Note)
        .filter(Note.timestamp >= day_start, Note.timestamp < day_end)
        .order_by(Note.timestamp.desc())
        .all()
    )
    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.created_at >= day_start, Feedback.created_at < day_end)
        .all()
    )
    cost_per_tier = _get_cost_per_tier()

    parsed_notes = 0
    total_processing_time = 0.0
    processing_count = 0
    tier_distribution = {"tier1": 0, "tier2": 0, "tier3": 0}
    total_cost = 0.0

    for note in notes:
        data = _safe_json_load(note.analysis_json) or {}
        if data:
            parsed_notes += 1
        routing = data.get("routing", {})
        tier = int(routing.get("tier", 1))
        if tier == 1:
            tier_distribution["tier1"] += 1
        elif tier == 2:
            tier_distribution["tier2"] += 1
        elif tier == 3:
            tier_distribution["tier3"] += 1
        else:
            tier = 1
            tier_distribution["tier1"] += 1

        total_cost += float(cost_per_tier.get(tier, cost_per_tier[1]))

        pt = data.get("processing_time_ms")
        if isinstance(pt, (int, float)):
            total_processing_time += float(pt)
            processing_count += 1

    feedback_count = len(feedback_rows)
    accuracy_rate = None
    if feedback_count > 0:
        overlap_sum = 0.0
        for row in feedback_rows:
            predicted = _safe_json_load(row.predicted_tags_json) or []
            corrected = _safe_json_load(row.corrected_tags_json) or []
            overlap_sum += _tag_overlap_score(predicted, corrected)
        accuracy_rate = round(overlap_sum / feedback_count * 100, 1)

    avg_processing = (total_processing_time / processing_count) if processing_count > 0 else 0.0
    total_notes = len(notes)
    success_rate = (parsed_notes / total_notes * 100) if total_notes > 0 else 0.0

    alerts = _check_alerts(
        pipeline_stats={
            "avg_processing_time_ms": round(avg_processing, 1),
            "success_rate": round(success_rate, 1),
        },
        cost_stats={"total_cost_eur": round(total_cost, 4)},
        quality={
            "accuracy_rate": accuracy_rate,
            "total_feedback": feedback_count,
            "accuracy_available": feedback_count > 0,
        },
    )

    limited_notes = notes[:limit]
    notes_rows: List[Dict[str, Any]] = []
    for note in limited_notes:
        data = _safe_json_load(note.analysis_json) or {}
        routing = data.get("routing", {})
        tier = int(routing.get("tier", 1))
        confidence = routing.get("confidence")
        processing_time_ms = data.get("processing_time_ms")
        advisor_name = None
        if note.advisor:
            advisor_name = note.advisor.full_name or note.advisor.email

        raw_preview = note.transcription or data.get("processed_text") or ""
        preview = " ".join(str(raw_preview).split())
        if len(preview) > 220:
            preview = f"{preview[:220]}..."

        notes_rows.append(
            {
                "note_id": note.id,
                "timestamp": note.timestamp.isoformat() if note.timestamp else None,
                "advisor_name": advisor_name,
                "tier": tier,
                "confidence": round(float(confidence), 3) if isinstance(confidence, (int, float)) else None,
                "processing_time_ms": round(float(processing_time_ms), 1) if isinstance(processing_time_ms, (int, float)) else None,
                "from_cache": bool(data.get("from_cache") or data.get("cache_hit")),
                "quality_score": data.get("quality_score"),
                "transcription_preview": preview,
            }
        )

    return {
        "date": date,
        "summary": {
            "total_notes": total_notes,
            "returned_notes": len(notes_rows),
            "success_rate": round(success_rate, 1),
            "avg_processing_time_ms": round(avg_processing, 1),
            "cost_eur": round(total_cost, 4),
            "feedback_count": feedback_count,
            "accuracy_rate": accuracy_rate,
            "tier_distribution": tier_distribution,
            "alerts_count": len(alerts),
            "alerts": alerts,
        },
        "notes": notes_rows,
    }


@router.get("/metrics/note-details/{note_id}")
async def get_metrics_note_details(
    note_id: int,
    db: Session = Depends(get_db),
):
    """Get full detail payload for one note (for admin drilldown modal)."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    data = _safe_json_load(note.analysis_json) or {}
    extraction = data.get("extraction", {}) if isinstance(data, dict) else {}
    if not isinstance(extraction, dict):
        extraction = {}

    routing = data.get("routing", {}) if isinstance(data, dict) else {}
    if not isinstance(routing, dict):
        routing = {}

    rgpd = data.get("rgpd", {}) if isinstance(data, dict) else {}
    if not isinstance(rgpd, dict):
        rgpd = {}

    p1 = extraction.get("pilier_1_univers_produit", {}) if isinstance(extraction, dict) else {}
    p2 = extraction.get("pilier_2_profil_client", {}) if isinstance(extraction, dict) else {}
    p3 = extraction.get("pilier_3_hospitalite_care", {}) if isinstance(extraction, dict) else {}
    p4 = extraction.get("pilier_4_action_business", {}) if isinstance(extraction, dict) else {}
    meta = extraction.get("meta_analysis", {}) if isinstance(extraction, dict) else {}

    if not isinstance(p1, dict):
        p1 = {}
    if not isinstance(p2, dict):
        p2 = {}
    if not isinstance(p3, dict):
        p3 = {}
    if not isinstance(p4, dict):
        p4 = {}
    if not isinstance(meta, dict):
        meta = {}

    matched_products = p1.get("matched_products")
    if not isinstance(matched_products, list):
        matched_products = []

    nba = p4.get("next_best_action")
    if not isinstance(nba, dict):
        nba = {}

    tags = _derive_tags(extraction)
    audio_sources = _extract_audio_sources(data)[:5]

    raw_preview = note.transcription or data.get("processed_text") or ""
    preview = " ".join(str(raw_preview).split())
    if len(preview) > 300:
        preview = f"{preview[:300]}..."

    return {
        "note": {
            "id": note.id,
            "timestamp": note.timestamp.isoformat() if note.timestamp else None,
            "advisor": {
                "id": note.advisor.id if note.advisor else None,
                "name": (note.advisor.full_name if note.advisor else None) or (note.advisor.email if note.advisor else None),
                "store": note.advisor.store if note.advisor else None,
            },
            "client": {
                "id": note.client.id if note.client else None,
                "name": note.client.name if note.client else None,
                "vic_status": note.client.vic_status if note.client else None,
            },
            "points_awarded": note.points_awarded,
            "transcription_preview": preview,
            "transcription": note.transcription or data.get("processed_text") or "",
        },
        "routing": {
            "tier": int(routing.get("tier", 1)),
            "confidence": routing.get("confidence"),
            "reasons": routing.get("reasons", []),
        },
        "quality": {
            "quality_score": meta.get("quality_score"),
            "advisor_feedback": meta.get("advisor_feedback"),
            "missing_info": meta.get("missing_info", []),
            "risk_flags": meta.get("risk_flags", []),
        },
        "rgpd": rgpd,
        "tags": tags,
        "next_best_action": nba,
        "matched_products": matched_products,
        "pillars": {
            "pilier_1_univers_produit": p1,
            "pilier_2_profil_client": p2,
            "pilier_3_hospitalite_care": p3,
            "pilier_4_action_business": p4,
        },
        "audio": {
            "available": len(audio_sources) > 0,
            "sources": audio_sources,
        },
    }


@router.get("/metrics/export")
async def export_metrics(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Export filtered metrics payload as JSON or CSV."""
    start_ts, end_ts = _resolve_time_window(days=days, date_from=date_from, date_to=date_to)

    if start_ts is None and end_ts is None:
        pipeline_stats = _get_pipeline_stats(db)
        cost_stats = _get_cost_stats(db)
        quality_metrics = _get_quality_metrics(db)
    else:
        pipeline_stats = _get_pipeline_stats(db, start_ts=start_ts, end_ts=end_ts)
        cost_stats = _get_cost_stats(db, start_ts=start_ts, end_ts=end_ts)
        quality_metrics = _get_quality_metrics(db, start_ts=start_ts, end_ts=end_ts)

    cache_stats = _get_cache_stats()
    alerts = _check_alerts(pipeline_stats, cost_stats, quality_metrics)
    window = _window_payload(start_ts, end_ts, days)
    generated_at = _utcnow_naive().isoformat()

    payload = {
        "generated_at": generated_at,
        "window": window,
        "pipeline_stats": pipeline_stats,
        "cache_stats": cache_stats,
        "cost_stats": cost_stats,
        "quality_metrics": quality_metrics,
        "alerts": alerts,
        "exported_by": current_user.email,
    }

    timestamp_slug = _utcnow_naive().strftime("%Y%m%d_%H%M%S")
    if format == "json":
        headers = {"Content-Disposition": f'attachment; filename="admin_metrics_{timestamp_slug}.json"'}
        return JSONResponse(content=payload, headers=headers)

    rows: List[tuple[str, Any]] = []
    _flatten_for_csv("", payload, rows)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerows(rows)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="admin_metrics_{timestamp_slug}.csv"'},
    )


@router.get("/components/status")
async def get_component_status(current_user: User = Depends(require_roles("admin"))):
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
async def warm_semantic_cache(
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
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


@router.get("/admin/users")
async def admin_list_users(
    include_hashed_password: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Admin user inventory with role/points and login credential hints."""
    users = db.query(User).order_by(User.role.asc(), User.email.asc()).all()
    note_counts = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(Note.advisor_id, func.count(Note.id))
            .group_by(Note.advisor_id)
            .all()
        )
        if user_id is not None
    }
    last_note_at = {
        int(user_id): timestamp
        for user_id, timestamp in (
            db.query(Note.advisor_id, func.max(Note.timestamp))
            .group_by(Note.advisor_id)
            .all()
        )
        if user_id is not None
    }

    demo_password = os.getenv("DEMO_PASSWORD", "lvmh")
    rows: List[Dict[str, Any]] = []
    for user in users:
        email = str(user.email or "").strip()
        email_lower = email.lower()
        is_demo_account = email_lower in DEMO_ACCOUNT_EMAILS

        credentials: Dict[str, Any] = {
            "username": email,
            "password": demo_password if is_demo_account else None,
            "password_hint": (
                "Compte demo seede via DEMO_PASSWORD"
                if is_demo_account
                else "Mot de passe non recuperable (hash uniquement)"
            ),
            "is_demo_account": is_demo_account,
        }
        if include_hashed_password:
            credentials["hashed_password"] = user.hashed_password

        user_id = int(user.id)
        last_note = last_note_at.get(user_id)
        rows.append(
            {
                "id": user_id,
                "email": email,
                "full_name": user.full_name,
                "role": str(user.role or "advisor").strip().lower(),
                "store": user.store,
                "score": int(user.score or 0),
                "notes_count": int(note_counts.get(user_id, 0)),
                "last_note_at": last_note.isoformat() if isinstance(last_note, datetime) else None,
                "credentials": credentials,
            }
        )

    return {
        "total": len(rows),
        "requested_by": current_user.email,
        "users": rows,
    }


@router.post("/admin/points/reset")
async def admin_reset_points(
    advisor_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Reset scoreboard points for all users (or advisors only)."""
    try:
        query = db.query(User)
        if advisor_only:
            query = query.filter(User.role == "advisor")

        users = query.all()
        reset_users = 0
        for user in users:
            if int(user.score or 0) != 0:
                user.score = 0
                reset_users += 1

        db.commit()
        return {
            "status": "ok",
            "target": "advisors" if advisor_only else "all_users",
            "total_users": len(users),
            "reset_users": reset_users,
            "requested_by": current_user.email,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Admin points reset failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to reset points")


@router.delete("/admin/recordings/{note_id}")
async def admin_delete_recording(
    note_id: int,
    adjust_advisor_points: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Delete one recording and optionally adjust advisor score."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    removed_points = int(note.points_awarded or 0)
    advisor_id = int(note.advisor_id) if note.advisor_id is not None else None
    try:
        deleted_actions = (
            db.query(OpportunityAction)
            .filter(OpportunityAction.note_id == note_id)
            .delete(synchronize_session=False)
        )
        db.delete(note)

        advisor_updated = False
        if adjust_advisor_points and advisor_id is not None and removed_points > 0:
            advisor = db.query(User).filter(User.id == advisor_id).first()
            if advisor:
                advisor.score = max(0, int(advisor.score or 0) - removed_points)
                advisor_updated = True

        db.commit()
        return {
            "status": "ok",
            "deleted_note_id": note_id,
            "deleted_actions": int(deleted_actions or 0),
            "removed_points": removed_points,
            "advisor_points_adjusted": advisor_updated,
            "requested_by": current_user.email,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Admin single recording delete failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete recording")


@router.delete("/admin/recordings")
async def admin_purge_recordings(
    reset_points: bool = Query(default=True),
    delete_feedback: bool = Query(default=True),
    delete_clients: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Purge all recordings and optionally reset points and related data."""
    try:
        deleted_actions = db.query(OpportunityAction).delete(synchronize_session=False)
        deleted_notes = db.query(Note).delete(synchronize_session=False)
        deleted_feedback = db.query(Feedback).delete(synchronize_session=False) if delete_feedback else 0
        deleted_clients = db.query(Client).delete(synchronize_session=False) if delete_clients else 0
        reset_users = db.query(User).update({User.score: 0}, synchronize_session=False) if reset_points else 0

        db.commit()
        return {
            "status": "ok",
            "deleted_notes": int(deleted_notes or 0),
            "deleted_actions": int(deleted_actions or 0),
            "deleted_feedback": int(deleted_feedback or 0),
            "deleted_clients": int(deleted_clients or 0),
            "reset_users": int(reset_users or 0),
            "requested_by": current_user.email,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Admin purge recordings failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to purge recordings")
