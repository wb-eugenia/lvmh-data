from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import train_test_split

from src.models import ExtractionResult

logger = logging.getLogger(__name__)


class SyntheticClientPredictions:
    """
    Supervised models trained on synthetic labels derived from historical notes.
    Prediction source is explicitly tagged as synthetic.
    """

    FEATURE_COLUMNS = [
        "days_since_last_visit",
        "avg_spend_trend",
        "engagement_score",
        "tier_hint",
        "confidence_hint",
        "vip_flag",
        "urgency_hint",
    ]

    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_path = self.model_dir / "synthetic_predictions.joblib"
        self.metadata_path = self.model_dir / "synthetic_predictions_metadata.json"

        self.churn_model: Optional[RandomForestClassifier] = None
        self.clv_model: Optional[LinearRegression] = None
        self.metadata: Dict[str, Any] = {}
        self._training_attempted = False
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        try:
            import joblib

            if self.artifact_path.exists():
                payload = joblib.load(self.artifact_path)
                self.churn_model = payload.get("churn_model")
                self.clv_model = payload.get("clv_model")
            if self.metadata_path.exists():
                self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load synthetic prediction artifacts: %s", exc)
            self.churn_model = None
            self.clv_model = None
            self.metadata = {}

    def _save_artifacts(self) -> None:
        try:
            import joblib

            payload = {"churn_model": self.churn_model, "clv_model": self.clv_model}
            joblib.dump(payload, self.artifact_path)
            self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist synthetic prediction artifacts: %s", exc)

    @staticmethod
    def _safe_json_load(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
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
    def _extract_budget_value(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value) if float(value) > 0 else 0.0
        if value in (None, ""):
            return 0.0
        text = str(value).lower()
        import re

        matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(k|m)?", text)
        if not matches:
            return 0.0
        parsed: List[float] = []
        for raw_amount, suffix in matches:
            amount = float(raw_amount.replace(",", "."))
            if suffix == "k":
                amount *= 1000
            elif suffix == "m":
                amount *= 1_000_000
            if amount > 0:
                parsed.append(amount)
        return max(parsed) if parsed else 0.0

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
    def _normalize_urgency(value: Any) -> float:
        text = str(value or "").strip().lower()
        if not text:
            return 1.0
        if any(token in text for token in ("urgent", "high", "immediat", "crit", "hot")):
            return 3.0
        if any(token in text for token in ("medium", "normal", "modere", "moyen")):
            return 2.0
        return 1.0

    @staticmethod
    def _derive_vip_flag(extraction: Dict[str, Any], client_status: Optional[str] = None) -> float:
        if client_status and str(client_status).lower() not in {"", "standard", "unknown"}:
            return 1.0
        p2 = extraction.get("pilier_2_profil_client", {}) if isinstance(extraction, dict) else {}
        if isinstance(p2, dict):
            status = str(p2.get("status", "")).lower()
            if status in {"vic", "vip", "ultimate", "platinum"}:
                return 1.0
            context = p2.get("purchase_context", {})
            if isinstance(context, dict):
                behavior = str(context.get("behavior", "")).lower()
                if behavior in {"vic", "vip", "ultimate", "platinum"}:
                    return 1.0
        return 0.0

    def _build_feature_row(
        self,
        *,
        timestamp: Optional[datetime],
        extraction: Dict[str, Any],
        routing: Dict[str, Any],
        client_status: Optional[str],
    ) -> Dict[str, float]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        note_ts = timestamp or now
        days_since_last_visit = max(0.0, float((now - note_ts).days))

        p1 = extraction.get("pilier_1_univers_produit", {}) if isinstance(extraction, dict) else {}
        p4 = extraction.get("pilier_4_action_business", {}) if isinstance(extraction, dict) else {}
        tags = extraction.get("tags")
        if not isinstance(tags, list):
            tags = p1.get("categories", []) if isinstance(p1, dict) else []
        tags_count = float(len([t for t in tags if isinstance(t, (str, int, float)) and str(t).strip()]))

        budget_value = self._extract_budget_value(
            p4.get("budget_specific") if isinstance(p4, dict) else None
        )
        if budget_value <= 0 and isinstance(p4, dict):
            budget_value = self._extract_budget_value(p4.get("budget_potential"))

        confidence = self._normalize_confidence(routing.get("confidence"))
        tier_hint = float(routing.get("tier", 1)) if str(routing.get("tier", "1")).isdigit() else 1.0
        vip_flag = self._derive_vip_flag(extraction, client_status=client_status)
        urgency_hint = self._normalize_urgency(
            p4.get("urgency") if isinstance(p4, dict) else None
        )
        if isinstance(p4, dict):
            urgency_hint = self._normalize_urgency(p4.get("urgency") or p4.get("lead_temperature"))

        avg_spend_trend = min(1.0, budget_value / 50_000.0) if budget_value > 0 else 0.0
        engagement_score = min(100.0, confidence * 100.0 + tags_count * 2.0 + urgency_hint * 4.0)

        return {
            "days_since_last_visit": days_since_last_visit,
            "avg_spend_trend": avg_spend_trend,
            "engagement_score": engagement_score,
            "tier_hint": tier_hint,
            "confidence_hint": confidence,
            "vip_flag": vip_flag,
            "urgency_hint": urgency_hint,
            "budget_value": budget_value,
        }

    def _synthetic_targets(self, features: Dict[str, float]) -> tuple[int, float]:
        inactivity = min(1.0, features["days_since_last_visit"] / 120.0)
        low_spend = 1.0 - min(1.0, features["avg_spend_trend"])
        low_engagement = 1.0 - min(1.0, features["engagement_score"] / 100.0)
        non_vip = 1.0 - min(1.0, features["vip_flag"])

        churn_score = (
            0.35 * inactivity
            + 0.25 * low_spend
            + 0.25 * low_engagement
            + 0.15 * non_vip
        )
        churned = 1 if churn_score >= 0.58 else 0

        recency_bonus = max(0.0, 90.0 - features["days_since_last_visit"]) * 80.0
        clv = (
            features["budget_value"] * 4.0
            + features["engagement_score"] * 120.0
            + features["vip_flag"] * 15_000.0
            + recency_bonus
        )
        return churned, max(0.0, clv)

    def _load_note_rows_from_db(self, db_path: str = "lvmh.db", limit: int = 5000) -> List[Dict[str, Any]]:
        if not Path(db_path).exists():
            return []

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows: List[Dict[str, Any]] = []
        try:
            cur = con.cursor()
            cur.execute(
                """
                SELECT n.timestamp, n.analysis_json, c.vic_status AS client_status
                FROM notes n
                LEFT JOIN clients c ON c.id = n.client_id
                ORDER BY n.timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cur.fetchall():
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "analysis_json": row["analysis_json"],
                        "client_status": row["client_status"],
                    }
                )
        finally:
            con.close()
        return rows

    def train_from_history(self, db_path: str = "lvmh.db", limit: int = 5000) -> Dict[str, Any]:
        note_rows = self._load_note_rows_from_db(db_path=db_path, limit=limit)
        if not note_rows:
            return {"trained": False, "reason": "no_history"}

        features_matrix: List[List[float]] = []
        churn_labels: List[int] = []
        clv_targets: List[float] = []

        for row in note_rows:
            parsed = self._safe_json_load(row.get("analysis_json"))
            extraction = parsed.get("extraction", {}) if isinstance(parsed, dict) else {}
            if not isinstance(extraction, dict):
                extraction = {}
            routing = parsed.get("routing", {}) if isinstance(parsed, dict) else {}
            if not isinstance(routing, dict):
                routing = {}

            feature_row = self._build_feature_row(
                timestamp=self._to_datetime(row.get("timestamp")),
                extraction=extraction,
                routing=routing,
                client_status=row.get("client_status"),
            )
            churned, clv = self._synthetic_targets(feature_row)
            features_matrix.append([feature_row[col] for col in self.FEATURE_COLUMNS])
            churn_labels.append(churned)
            clv_targets.append(clv)

        if len(features_matrix) < 20:
            return {"trained": False, "reason": "insufficient_samples", "samples": len(features_matrix)}

        X = np.array(features_matrix, dtype=float)
        y_churn = np.array(churn_labels, dtype=int)
        y_clv = np.array(clv_targets, dtype=float)

        churn_train_acc = None
        churn_test_acc = None
        clv_train_r2 = None
        clv_test_r2 = None

        stratify = y_churn if len(set(y_churn.tolist())) > 1 else None
        X_train, X_test, y_churn_train, y_churn_test, y_clv_train, y_clv_test = train_test_split(
            X,
            y_churn,
            y_clv,
            test_size=0.2,
            random_state=42,
            stratify=stratify,
        )

        churn_model = RandomForestClassifier(
            n_estimators=120,
            random_state=42,
            class_weight="balanced",
            min_samples_leaf=3,
        )
        churn_model.fit(X_train, y_churn_train)
        churn_train_pred = churn_model.predict(X_train)
        churn_test_pred = churn_model.predict(X_test)
        churn_train_acc = float(accuracy_score(y_churn_train, churn_train_pred))
        churn_test_acc = float(accuracy_score(y_churn_test, churn_test_pred))

        clv_model = LinearRegression()
        clv_model.fit(X_train, y_clv_train)
        clv_train_pred = clv_model.predict(X_train)
        clv_test_pred = clv_model.predict(X_test)
        clv_train_r2 = float(r2_score(y_clv_train, clv_train_pred))
        clv_test_r2 = float(r2_score(y_clv_test, clv_test_pred))

        self.churn_model = churn_model
        self.clv_model = clv_model
        self.metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_source": "synthetic_from_notes_history",
            "samples": len(features_matrix),
            "features": list(self.FEATURE_COLUMNS),
            "metrics": {
                "churn_train_accuracy": round(churn_train_acc, 4),
                "churn_test_accuracy": round(churn_test_acc, 4),
                "clv_train_r2": round(clv_train_r2, 4),
                "clv_test_r2": round(clv_test_r2, 4),
            },
        }
        self._save_artifacts()

        return {
            "trained": True,
            "samples": len(features_matrix),
            "metrics": self.metadata["metrics"],
            "training_source": "synthetic_from_notes_history",
        }

    def ensure_model(self) -> None:
        if self.churn_model is not None and self.clv_model is not None:
            return
        if self._training_attempted:
            return
        self._training_attempted = True
        outcome = self.train_from_history()
        logger.info("Synthetic prediction training outcome: %s", outcome)

    def _risk_level(self, value: float) -> str:
        if value >= 0.7:
            return "high"
        if value >= 0.4:
            return "medium"
        return "low"

    def _clv_tier(self, value: float) -> str:
        if value >= 50_000:
            return "platinum"
        if value >= 20_000:
            return "gold"
        return "silver"

    def predict_from_feature_row(self, feature_row: Dict[str, float]) -> Dict[str, Any]:
        self.ensure_model()

        X = np.array([[feature_row[col] for col in self.FEATURE_COLUMNS]], dtype=float)
        churn_risk: float
        clv_estimate: float

        if self.churn_model is not None and hasattr(self.churn_model, "predict_proba"):
            probabilities = self.churn_model.predict_proba(X)[0]
            classes = list(getattr(self.churn_model, "classes_", []))
            if 1 in classes:
                churn_risk = float(probabilities[classes.index(1)])
            elif classes:
                # Degenerate model trained on a single class.
                churn_risk = 1.0 if int(classes[0]) == 1 else 0.0
            else:
                churn_risk = 0.0
        else:
            inactivity = min(1.0, feature_row["days_since_last_visit"] / 120.0)
            churn_risk = (
                0.35 * inactivity
                + 0.25 * (1.0 - feature_row["avg_spend_trend"])
                + 0.25 * (1.0 - min(1.0, feature_row["engagement_score"] / 100.0))
                + 0.15 * (1.0 - feature_row["vip_flag"])
            )

        if self.clv_model is not None:
            clv_estimate = float(self.clv_model.predict(X)[0])
        else:
            _, synthetic_clv = self._synthetic_targets(feature_row)
            clv_estimate = synthetic_clv

        churn_risk = min(1.0, max(0.0, churn_risk))
        clv_estimate = max(0.0, clv_estimate)

        return {
            "churn_risk": round(churn_risk, 4),
            "churn_level": self._risk_level(churn_risk),
            "clv_estimate": round(clv_estimate, 2),
            "clv_tier": self._clv_tier(clv_estimate),
            "prediction_source": "synthetic_supervised_v1",
            "model_metadata": self.metadata.get("metrics", {}),
        }

    def predict_from_extraction(
        self,
        extraction: ExtractionResult,
        *,
        source_text: str = "",
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        payload = extraction.model_dump() if hasattr(extraction, "model_dump") else {}
        routing_hint = {
            "tier": 1 if extraction.processing_tier == "tier1" else 2 if extraction.processing_tier == "tier2" else 3,
            "confidence": extraction.confidence,
        }
        feature_row = self._build_feature_row(
            timestamp=timestamp,
            extraction=payload,
            routing=routing_hint,
            client_status=None,
        )
        # Slightly boost engagement if text is rich.
        token_count = len((source_text or "").split())
        if token_count >= 20:
            feature_row["engagement_score"] = min(100.0, feature_row["engagement_score"] + 8.0)
        return self.predict_from_feature_row(feature_row)
