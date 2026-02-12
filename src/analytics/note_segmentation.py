from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


class NoteSegmentation:
    """
    Segment notes (not clients) from persisted analysis payloads.
    """

    SEGMENT_LABELS = [
        "VIC_Platinum",
        "VIP_Occasionnel",
        "Prospect_Chaud",
        "Fidele_Regulier",
        "Nouveau_Potentiel",
    ]

    def __init__(self, n_clusters: int = 5, random_state: int = 42):
        self.n_clusters = max(2, int(n_clusters))
        self.random_state = random_state

    @staticmethod
    def _safe_json_load(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            import json

            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _to_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            raw = value.strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        if not isinstance(value, (int, float)):
            return 0.0
        conf = float(value)
        if conf < 0:
            return 0.0
        if conf <= 1:
            return conf
        if conf <= 100:
            return conf / 100.0
        return 1.0

    @staticmethod
    def _normalize_urgency(value: Any) -> int:
        text = str(value or "").strip().lower()
        if not text:
            return 1
        if any(token in text for token in ("urgent", "high", "immediat", "crit", "hot")):
            return 3
        if any(token in text for token in ("medium", "normal", "modere", "moyen")):
            return 2
        return 1

    @staticmethod
    def _extract_budget_value(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value) if float(value) > 0 else 0.0
        if value in (None, ""):
            return 0.0

        text = str(value).lower()
        matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(k|m)?", text)
        if not matches:
            return 0.0

        parsed: List[float] = []
        for amount_raw, suffix in matches:
            amount = float(amount_raw.replace(",", "."))
            if suffix == "m":
                amount *= 1_000_000
            elif suffix == "k":
                amount *= 1_000
            if amount > 0:
                parsed.append(amount)
        return max(parsed) if parsed else 0.0

    @staticmethod
    def _is_vip(payload: Dict[str, Any], extraction: Dict[str, Any]) -> bool:
        client = payload.get("client", {})
        if isinstance(client, dict):
            status = str(client.get("vic_status", "")).strip().lower()
            if status and status != "standard":
                return True

        p2 = extraction.get("pilier_2_profil_client", {}) if isinstance(extraction, dict) else {}
        if isinstance(p2, dict):
            purchase_context = p2.get("purchase_context", {})
            if isinstance(purchase_context, dict):
                behavior = str(purchase_context.get("behavior", "")).strip().lower()
                if behavior in {"vic", "vip", "ultimate", "platinum"}:
                    return True
            status = str(p2.get("status", "")).strip().lower()
            if status in {"vic", "vip", "ultimate", "platinum"}:
                return True
        return False

    def _build_note_row(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None

        analysis = self._safe_json_load(payload.get("analysis_json"))
        if not analysis:
            analysis = payload

        extraction = analysis.get("extraction", {})
        if not isinstance(extraction, dict):
            extraction = {}
        routing = analysis.get("routing", {})
        if not isinstance(routing, dict):
            routing = {}

        p1 = extraction.get("pilier_1_univers_produit", {})
        if not isinstance(p1, dict):
            p1 = {}
        p4 = extraction.get("pilier_4_action_business", {})
        if not isinstance(p4, dict):
            p4 = {}

        tags = extraction.get("tags")
        if not isinstance(tags, list):
            tags = p1.get("categories", [])
        tags = [str(t).strip() for t in tags if isinstance(t, (str, int, float)) and str(t).strip()]

        tier = int(routing.get("tier", 1)) if str(routing.get("tier", "1")).isdigit() else 1
        tier = min(3, max(1, tier))
        confidence = self._normalize_confidence(routing.get("confidence", 0.0))
        urgency_level = self._normalize_urgency(
            p4.get("urgency") or p4.get("priority") or p4.get("lead_temperature")
        )
        budget_value = self._extract_budget_value(p4.get("budget_specific") or p4.get("budget_potential"))
        vip_flag = 1.0 if self._is_vip(payload, extraction) else 0.0

        churn_risk = p4.get("churn_risk")
        if not isinstance(churn_risk, (int, float)):
            churn_risk = 0.0
        churn_risk = min(1.0, max(0.0, float(churn_risk)))

        clv_estimate = p4.get("clv_estimate")
        if not isinstance(clv_estimate, (int, float)):
            clv_estimate = 0.0
        clv_estimate = max(0.0, float(clv_estimate))

        budget_scaled = math.log1p(budget_value) / math.log1p(200_000.0) if budget_value > 0 else 0.0
        clv_scaled = math.log1p(clv_estimate) / math.log1p(500_000.0) if clv_estimate > 0 else 0.0
        tags_count = min(20.0, float(len(tags)))

        priority_score = (
            (30.0 if tier == 3 else 18.0 if tier == 2 else 8.0)
            + urgency_level * 15.0
            + vip_flag * 25.0
            + (min(35.0, budget_value / 2000.0) if budget_value else 0.0)
            + round(confidence * 12.0)
        )

        return {
            "note_id": payload.get("id") or payload.get("note_id"),
            "advisor_name": (
                (payload.get("advisor", {}) or {}).get("name")
                if isinstance(payload.get("advisor"), dict)
                else payload.get("advisor_name")
            ),
            "client_name": (
                (payload.get("client", {}) or {}).get("name")
                if isinstance(payload.get("client"), dict)
                else payload.get("client_name")
            ),
            "timestamp": payload.get("timestamp"),
            "tier": tier,
            "confidence": confidence,
            "urgency_level": urgency_level,
            "budget_value": budget_value,
            "vip_flag": vip_flag,
            "tags_count": len(tags),
            "tags": tags,
            "priority_score": round(float(priority_score), 2),
            "churn_risk": churn_risk,
            "clv_estimate": clv_estimate,
            "features": [
                float(tier),
                float(confidence),
                float(tags_count),
                float(budget_scaled),
                float(urgency_level) / 3.0,
                float(vip_flag),
                float(churn_risk),
                float(clv_scaled),
            ],
        }

    def _build_cluster_labels(self, cluster_agg: Dict[int, Dict[str, float]]) -> Dict[int, str]:
        ordered = sorted(
            cluster_agg.items(),
            key=lambda item: (
                item[1].get("vip_share", 0.0),
                item[1].get("avg_budget", 0.0),
                item[1].get("avg_priority_score", 0.0),
            ),
            reverse=True,
        )
        labels: Dict[int, str] = {}
        for rank, (cluster_id, _) in enumerate(ordered):
            if rank < len(self.SEGMENT_LABELS):
                labels[cluster_id] = self.SEGMENT_LABELS[rank]
            else:
                labels[cluster_id] = f"Segment_{cluster_id + 1}"
        return labels

    def segment_notes(
        self,
        raw_notes: List[Dict[str, Any]],
        *,
        n_clusters: Optional[int] = None,
    ) -> Dict[str, Any]:
        rows = [self._build_note_row(note) for note in raw_notes or []]
        rows = [row for row in rows if row is not None]

        if not rows:
            return {
                "total_notes": 0,
                "n_clusters_requested": int(n_clusters or self.n_clusters),
                "n_clusters_used": 0,
                "segments": [],
                "assignments": [],
            }

        requested_clusters = max(2, int(n_clusters or self.n_clusters))
        n_samples = len(rows)
        if n_samples < 2:
            used_clusters = 1
            cluster_ids = np.zeros(n_samples, dtype=int)
        else:
            used_clusters = min(requested_clusters, n_samples)
            if used_clusters < 2:
                used_clusters = 2
            features = np.array([row["features"] for row in rows], dtype=float)
            scaled = StandardScaler().fit_transform(features)
            model = KMeans(n_clusters=used_clusters, random_state=self.random_state, n_init=10)
            cluster_ids = model.fit_predict(scaled)

        tag_counter_by_cluster: Dict[int, Counter] = defaultdict(Counter)
        cluster_agg: Dict[int, Dict[str, float]] = defaultdict(
            lambda: {
                "count": 0.0,
                "budget_sum": 0.0,
                "confidence_sum": 0.0,
                "priority_sum": 0.0,
                "tier3_count": 0.0,
                "vip_count": 0.0,
                "churn_high_count": 0.0,
            }
        )

        assignments: List[Dict[str, Any]] = []
        for row, cluster_id in zip(rows, cluster_ids):
            cluster = int(cluster_id)
            agg = cluster_agg[cluster]
            agg["count"] += 1.0
            agg["budget_sum"] += float(row["budget_value"])
            agg["confidence_sum"] += float(row["confidence"])
            agg["priority_sum"] += float(row["priority_score"])
            agg["tier3_count"] += 1.0 if int(row["tier"]) == 3 else 0.0
            agg["vip_count"] += float(row["vip_flag"])
            agg["churn_high_count"] += 1.0 if float(row["churn_risk"]) >= 0.7 else 0.0

            for tag in row["tags"]:
                tag_counter_by_cluster[cluster][tag] += 1

            assignment = {
                "note_id": row["note_id"],
                "segment_id": cluster,
                "tier": row["tier"],
                "confidence": round(float(row["confidence"]), 4),
                "budget_value": round(float(row["budget_value"]), 2),
                "priority_score": round(float(row["priority_score"]), 2),
                "vip_flag": bool(row["vip_flag"]),
                "advisor_name": row["advisor_name"],
                "client_name": row["client_name"],
                "timestamp": row["timestamp"],
                "churn_risk": round(float(row["churn_risk"]), 4),
                "clv_estimate": round(float(row["clv_estimate"]), 2),
            }
            assignments.append(assignment)

        normalized_cluster_agg: Dict[int, Dict[str, float]] = {}
        for cluster, agg in cluster_agg.items():
            count = max(1.0, agg["count"])
            normalized_cluster_agg[cluster] = {
                "count": agg["count"],
                "avg_budget": agg["budget_sum"] / count,
                "avg_confidence": agg["confidence_sum"] / count,
                "avg_priority_score": agg["priority_sum"] / count,
                "tier3_share": agg["tier3_count"] / count,
                "vip_share": agg["vip_count"] / count,
                "high_churn_share": agg["churn_high_count"] / count,
            }

        label_map = self._build_cluster_labels(normalized_cluster_agg)
        for assignment in assignments:
            assignment["segment_label"] = label_map.get(assignment["segment_id"], f"Segment_{assignment['segment_id'] + 1}")

        segments: List[Dict[str, Any]] = []
        for cluster in sorted(normalized_cluster_agg.keys()):
            agg = normalized_cluster_agg[cluster]
            segments.append(
                {
                    "segment_id": cluster,
                    "segment_label": label_map.get(cluster, f"Segment_{cluster + 1}"),
                    "count": int(agg["count"]),
                    "share_pct": round((agg["count"] / n_samples) * 100.0, 2),
                    "avg_budget": round(agg["avg_budget"], 2),
                    "avg_confidence": round(agg["avg_confidence"], 4),
                    "avg_priority_score": round(agg["avg_priority_score"], 2),
                    "tier3_share_pct": round(agg["tier3_share"] * 100.0, 2),
                    "vip_share_pct": round(agg["vip_share"] * 100.0, 2),
                    "high_churn_share_pct": round(agg["high_churn_share"] * 100.0, 2),
                    "top_tags": [tag for tag, _ in tag_counter_by_cluster[cluster].most_common(5)],
                }
            )

        return {
            "total_notes": n_samples,
            "n_clusters_requested": requested_clusters,
            "n_clusters_used": used_clusters,
            "segments": segments,
            "assignments": assignments,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

