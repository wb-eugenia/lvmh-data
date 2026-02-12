from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


class LexiconBuilder:
    """
    Build a review queue of taxonomy candidates from historical notes.
    This module does not mutate taxonomy files.
    """

    def __init__(self, language: str = "fr", max_features: int = 800):
        self.language = language
        self.max_features = max_features

    @staticmethod
    def _normalize_phrase(value: str) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _flatten_keywords_map(taxonomy: Dict[str, Any]) -> set[str]:
        values = set()
        product_keywords = taxonomy.get("product_keywords", {}) if isinstance(taxonomy, dict) else {}
        if not isinstance(product_keywords, dict):
            return values
        for keywords in product_keywords.values():
            if not isinstance(keywords, list):
                continue
            for keyword in keywords:
                if isinstance(keyword, (str, int, float)):
                    normalized = LexiconBuilder._normalize_phrase(str(keyword))
                    if normalized:
                        values.add(normalized)
        return values

    def _extract_with_yake(self, notes: List[str], top_per_note: int = 8) -> List[Tuple[str, float]]:
        try:
            import yake
        except Exception:
            logger.warning("YAKE not installed. Falling back to TF-IDF only extraction.")
            return []

        extractor = yake.KeywordExtractor(lan=self.language, n=3, top=top_per_note)
        results: List[Tuple[str, float]] = []
        for note in notes:
            try:
                for phrase, score in extractor.extract_keywords(note):
                    normalized = self._normalize_phrase(phrase)
                    if normalized:
                        results.append((normalized, float(score)))
            except Exception:
                continue
        return results

    def _extract_with_tfidf(self, notes: List[str], top_k: int = 600) -> List[Tuple[str, float]]:
        if not notes:
            return []

        vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=(1, 3),
            min_df=2,
            token_pattern=r"(?u)\b[\w-]{2,}\b",
            strip_accents="unicode",
        )
        matrix = vectorizer.fit_transform(notes)
        feature_names = vectorizer.get_feature_names_out()
        mean_scores = matrix.mean(axis=0).A1

        ranked_indices = mean_scores.argsort()[::-1][:top_k]
        return [
            (self._normalize_phrase(feature_names[idx]), float(mean_scores[idx]))
            for idx in ranked_indices
            if self._normalize_phrase(feature_names[idx])
        ]

    def build_review_queue(
        self,
        notes: List[str],
        taxonomy: Dict[str, Any],
        *,
        min_occurrences: int = 2,
        min_combined_score: float = 0.05,
        limit: int = 300,
    ) -> Dict[str, Any]:
        clean_notes = [str(note).strip() for note in notes if isinstance(note, (str, int, float)) and str(note).strip()]
        existing_keywords = self._flatten_keywords_map(taxonomy)

        yake_candidates = self._extract_with_yake(clean_notes)
        tfidf_candidates = self._extract_with_tfidf(clean_notes)

        source_hits: Dict[str, Dict[str, float]] = defaultdict(lambda: {"yake": 0.0, "tfidf": 0.0})
        occurrences = Counter()

        for phrase, score in tfidf_candidates:
            if phrase:
                source_hits[phrase]["tfidf"] = max(source_hits[phrase]["tfidf"], score)

        for phrase, yake_score in yake_candidates:
            if phrase:
                # YAKE: lower is better -> invert into [0,1]-like confidence.
                transformed = 1.0 / (1.0 + max(0.0, yake_score))
                source_hits[phrase]["yake"] = max(source_hits[phrase]["yake"], transformed)

        for note in clean_notes:
            lowered = f" {self._normalize_phrase(note)} "
            for phrase in source_hits.keys():
                if not phrase:
                    continue
                if f" {phrase} " in lowered:
                    occurrences[phrase] += 1

        queue: List[Dict[str, Any]] = []
        for phrase, scores in source_hits.items():
            if phrase in existing_keywords:
                continue
            if len(phrase) < 3:
                continue
            occ = int(occurrences.get(phrase, 0))
            if occ < min_occurrences:
                continue

            combined_score = float(scores["tfidf"]) * 0.65 + float(scores["yake"]) * 0.35
            if combined_score < min_combined_score:
                continue

            queue.append(
                {
                    "candidate": phrase,
                    "occurrences": occ,
                    "combined_score": round(combined_score, 6),
                    "tfidf_score": round(float(scores["tfidf"]), 6),
                    "yake_score": round(float(scores["yake"]), 6),
                    "proposed_category": "auto_generated_review",
                    "status": "pending_review",
                }
            )

        queue.sort(key=lambda item: (item["combined_score"], item["occurrences"]), reverse=True)
        queue = queue[:limit]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notes_analyzed": len(clean_notes),
            "taxonomy_version": taxonomy.get("version"),
            "existing_keywords_count": len(existing_keywords),
            "candidate_count": len(queue),
            "review_queue": queue,
            "policy": {
                "auto_merge": False,
                "review_required": True,
                "target_file_unchanged": "config/taxonomy_v2.2.json",
            },
        }


def load_taxonomy(path: str) -> Dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {path}")
    return json.loads(target.read_text(encoding="utf-8"))
