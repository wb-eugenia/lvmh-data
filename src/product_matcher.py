"""
Product Matcher (RAG Component)
Encapsulates vector-search based product matching with light business reranking.
"""

import os
import pickle
import logging
import json
import re
from typing import List, Dict, Any, Set, Optional

import numpy as np
import pandas as pd

try:
    from sentence_transformers import SentenceTransformer
    HAS_ML = True
except ImportError:
    HAS_ML = False

try:
    from mistralai import Mistral
    HAS_MISTRAL = True
except ImportError:
    HAS_MISTRAL = False

logger = logging.getLogger(__name__)


class ProductMatcher:
    """Semantic product search over a prebuilt embedding index."""

    RAG_QUERY_GENERATION_PROMPT = """
Tu es un expert catalogue LVMH.
Objectif: générer une requête structurée pour un matching produits précis.

DONNÉES EXTRAITES:
{analysis_summary}

RÈGLES:
1. Prioriser modèles/produits explicitement mentionnés.
2. Inclure couleurs et matières si disponibles.
3. Déduire un filtre catégorie (bags, small_leather_goods, watches, jewelry, fragrance, ready_to_wear).
4. Respecter le budget si connu.
5. Exclure les familles hors contexte (ex: pantalon si intention sac).

Réponds en JSON strict:
{
  "primary_query": "string",
  "category_filter": "string|null",
  "color_filter": ["string"],
  "price_range": [min, max],
  "exclude_keywords": ["string"],
  "boost_keywords": ["string"]
}
"""

    COLOR_ALIASES: Dict[str, List[str]] = {
        "black": ["black", "noir", "nero", "schwarz", "negro"],
        "navy": ["navy", "marine"],
        "blue": ["blue", "bleu", "azul", "blau"],
        "red": ["red", "rouge", "rojo", "rot", "bordeaux", "burgundy", "wine"],
        "brown": ["brown", "marron", "marrón", "braun", "cognac"],
        "beige": ["beige", "neutral"],
        "white": ["white", "blanc", "bianco", "weiss", "weiß"],
        "green": ["green", "vert", "verde", "grün"],
    }

    def __init__(self, index_path: str = "data/vector_store/lv_index.pkl"):
        self.enabled = False
        self.model = None
        self.df = None
        self.embeddings = None
        self.norm_embeddings = None
        self.rag_query_llm_enabled = os.getenv("LVMH_ENABLE_RAG_QUERY_LLM", "false").lower() in {"1", "true", "yes"}
        self.rag_query_model = os.getenv("RAG_QUERY_LLM_MODEL", "mistral-small-latest")
        self.rag_query_client = None

        if self.rag_query_llm_enabled:
            api_key = os.getenv("MISTRAL_API_KEY")
            if HAS_MISTRAL and api_key:
                try:
                    self.rag_query_client = Mistral(api_key=api_key)
                except Exception as exc:
                    logger.warning("RAG query LLM disabled (client init failed): %s", exc)
            else:
                logger.warning("RAG query LLM requested but Mistral client/api key unavailable.")

        if not HAS_ML:
            logger.warning("SentenceTransformers not installed. RAG disabled.")
            return

        if not os.path.exists(index_path):
            logger.warning("Vector index not found at %s. Run scripts/build_vector_store.py first.", index_path)
            return

        try:
            logger.info("Loading RAG index and model...")
            with open(index_path, "rb") as f:
                data = pickle.load(f)
                self.embeddings = data["embeddings"]
                self.df = data["df"]

            self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            self.norm_embeddings = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            self.enabled = True
            logger.info("ProductMatcher ready: %s products indexed.", len(self.df))
        except Exception as exc:
            logger.error("Failed to initialize ProductMatcher: %s", exc)
            self.enabled = False

    def match(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.35,
        extraction: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Return top-k product matches for the query."""
        if not self.enabled or not query:
            return []

        try:
            query_struct = self._build_query_struct(query, extraction=extraction)
            search_query = query_struct.get("primary_query") or query
            category_filter = query_struct.get("category_filter")
            color_filter = set(query_struct.get("color_filter") or [])
            price_range = query_struct.get("price_range")
            exclude_keywords = {kw.lower() for kw in (query_struct.get("exclude_keywords") or []) if str(kw).strip()}
            boost_keywords = {kw.lower() for kw in (query_struct.get("boost_keywords") or []) if str(kw).strip()}

            logger.info("RAG query raw=%s", str(query)[:180])
            logger.info("RAG query structured=%s", query_struct)

            query_vec = self.model.encode([search_query])
            norm_query = query_vec / np.linalg.norm(query_vec, axis=1, keepdims=True)
            similarities = np.dot(norm_query, self.norm_embeddings.T).flatten()

            shortlist_k = min(max(top_k * 6, 12), len(similarities))
            top_indices = similarities.argsort()[-shortlist_k:][::-1]

            intents = self._infer_query_intents(search_query, extraction=extraction)
            color_hints = color_filter or self._extract_color_hints(search_query)
            logger.info(
                "RAG intents=%s colors=%s category=%s threshold=%.2f",
                sorted(intents),
                sorted(color_hints),
                category_filter,
                threshold,
            )

            results: List[Dict[str, Any]] = []
            for idx in top_indices:
                base_score = float(similarities[idx])
                prod = self.df.iloc[idx].to_dict()
                product_text = self._build_product_text(prod)

                if category_filter and not self._category_matches(self._get_best_category(prod), category_filter):
                    continue
                if color_hints and not self._product_matches_colors(product_text, color_hints):
                    continue
                if exclude_keywords and any(token in product_text for token in exclude_keywords):
                    continue

                product_price = self._coerce_price(prod.get("price"))
                if price_range and product_price is not None:
                    min_price, max_price = price_range
                    if product_price < min_price or product_price > max_price:
                        continue

                adjusted_score = self._apply_business_rerank(
                    base_score=base_score,
                    product_text=product_text,
                    intents=intents,
                    color_hints=color_hints,
                    boost_keywords=boost_keywords,
                    category_filter=category_filter,
                )
                if adjusted_score < threshold:
                    continue

                category = self._get_best_category(prod)
                clean_prod = {
                    "sku": str(prod.get("product_code", "N/A")),
                    "name": self._get_best_name(prod),
                    "category": category,
                    "price": product_price,
                    "url": str(prod.get("itemurl", "")),
                    "match_score": round(adjusted_score, 2),
                    "similarity": round(adjusted_score, 2),
                    "base_score": round(base_score, 2),
                    "rerank_delta": round(adjusted_score - base_score, 3),
                    "query_used": search_query,
                }
                results.append(clean_prod)

            results.sort(key=lambda item: item.get("match_score", 0.0), reverse=True)
            final_results = results[:top_k]
            logger.info(
                "RAG top results: %s",
                [f"{item.get('name', 'N/A')} ({item.get('match_score', 0):.2f})" for item in final_results],
            )
            return final_results
        except Exception as exc:
            logger.error("RAG search failed: %s", exc)
            return []

    def _get_best_name(self, prod: Dict[str, Any]) -> str:
        candidates = ["title", "name", "product_name", "model", "description"]
        for key in candidates:
            found_key = next((k for k in prod.keys() if k.lower() == key), None)
            if found_key and prod[found_key] and str(prod[found_key]).strip().lower() != "nan":
                value = str(prod[found_key]).strip()
                if value.lower() != "louis vuitton":
                    return value
        return "Unknown Product"

    def _get_best_category(self, prod: Dict[str, Any]) -> str:
        candidates = ["category", "categorie", "universe", "department", "line", "product_type"]
        for key in candidates:
            found_key = next((k for k in prod.keys() if k.lower() == key), None)
            if found_key and prod[found_key] and str(prod[found_key]).strip().lower() != "nan":
                return str(prod[found_key]).strip()
        return "unknown"

    def _build_product_text(self, prod: Dict[str, Any]) -> str:
        parts = [
            self._get_best_name(prod),
            self._get_best_category(prod),
            str(prod.get("description", "")),
            str(prod.get("title", "")),
            str(prod.get("model", "")),
        ]
        return " ".join(parts).lower()

    def _infer_query_intents(self, query: str, extraction: Optional[Any] = None) -> Set[str]:
        text = (query or "").lower()
        intents: Set[str] = set()
        if any(token in text for token in ("sac", "bag", "handbag", "capucines", "alma", "tote", "clutch")):
            intents.add("bags")
        if any(token in text for token in ("wallet", "portefeuille", "small leather", "card holder", "slg")):
            intents.add("small_leather")
        if any(token in text for token in ("shoe", "chaussure", "sneaker", "boots", "pantalon", "cargo", "shirt")):
            intents.add("apparel")
        if extraction is not None:
            p1 = getattr(extraction, "pilier_1_univers_produit", None)
            categories = [str(item).lower() for item in (getattr(p1, "categories", []) if p1 else [])]
            if any("leather" in item for item in categories):
                intents.add("bags")
            if any("small_leather" in item or "accessor" in item for item in categories):
                intents.add("small_leather")
            if any("ready_to_wear" in item or "shoes" in item for item in categories):
                intents.add("apparel")
        return intents

    def _extract_color_hints(self, query: str) -> Set[str]:
        text = (query or "").lower()
        hints: Set[str] = set()
        for canonical, aliases in self.COLOR_ALIASES.items():
            if any(alias in text for alias in aliases):
                hints.add(canonical)
        return hints

    def _apply_business_rerank(
        self,
        *,
        base_score: float,
        product_text: str,
        intents: Set[str],
        color_hints: Set[str],
        boost_keywords: Set[str],
        category_filter: Optional[str],
    ) -> float:
        score = base_score
        bag_terms = ("bag", "sac", "handbag", "capucines", "alma", "neverfull", "speedy", "twist")
        slg_terms = ("wallet", "portefeuille", "card holder", "small leather", "pochette")
        apparel_terms = ("pant", "pantalon", "cargo", "shirt", "jacket", "jean", "sweater", "dress")

        if "bags" in intents:
            if any(term in product_text for term in bag_terms):
                score += 0.12
            if any(term in product_text for term in apparel_terms):
                score -= 0.30
        if "small_leather" in intents:
            if any(term in product_text for term in slg_terms):
                score += 0.10
            if any(term in product_text for term in apparel_terms):
                score -= 0.20
        if "apparel" in intents and any(term in product_text for term in apparel_terms):
            score += 0.08

        if color_hints and any(color in product_text for color in color_hints):
            score += 0.06

        if category_filter:
            category_signals = {
                "bags": bag_terms,
                "small_leather_goods": slg_terms,
                "ready_to_wear": apparel_terms,
            }
            if any(term in product_text for term in category_signals.get(category_filter, ())):
                score += 0.06

        if boost_keywords and any(kw in product_text for kw in boost_keywords):
            score += 0.06

        return max(0.0, min(1.0, score))

    def _build_query_struct(self, query: str, extraction: Optional[Any]) -> Dict[str, Any]:
        analysis_summary = self._extract_analysis_summary(query, extraction)
        llm_query_struct = self._generate_rag_query_llm(analysis_summary)
        if llm_query_struct:
            return self._sanitize_query_struct(llm_query_struct, fallback_query=query)
        heuristic = self._generate_rag_query_heuristic(analysis_summary, fallback_query=query)
        return self._sanitize_query_struct(heuristic, fallback_query=query)

    def _extract_analysis_summary(self, query: str, extraction: Optional[Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "raw_query": query,
            "pillar1": {"products": [], "colors": [], "categories": []},
            "pillar4": {"budget_specific": None, "budget_potential": None},
        }
        if extraction is None:
            return summary

        p1 = getattr(extraction, "pilier_1_univers_produit", None)
        if p1 is not None:
            summary["pillar1"]["products"] = [str(item) for item in getattr(p1, "produits_mentionnes", []) if str(item).strip()]
            preferences = getattr(p1, "preferences", None)
            if preferences is not None:
                summary["pillar1"]["colors"] = [str(item) for item in getattr(preferences, "colors", []) if str(item).strip()]
            summary["pillar1"]["categories"] = [str(item) for item in getattr(p1, "categories", []) if str(item).strip()]

        p4 = getattr(extraction, "pilier_4_action_business", None)
        if p4 is not None:
            summary["pillar4"]["budget_specific"] = getattr(p4, "budget_specific", None)
            summary["pillar4"]["budget_potential"] = getattr(p4, "budget_potential", None)

        return summary

    def _generate_rag_query_llm(self, analysis_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.rag_query_client:
            return None
        try:
            prompt = self.RAG_QUERY_GENERATION_PROMPT.format(
                analysis_summary=json.dumps(analysis_summary, ensure_ascii=False, indent=2)
            )
            request_args = {
                "model": self.rag_query_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            }
            try:
                response = self.rag_query_client.chat.complete(
                    **request_args,
                    response_format={"type": "json_object"},
                )
            except TypeError:
                # Fallback for SDK versions not exposing response_format.
                response = self.rag_query_client.chat.complete(**request_args)

            content = response.choices[0].message.content
            if isinstance(content, list):
                content = "".join(
                    chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                    for chunk in content
                )
            if not isinstance(content, str):
                return None

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", content)
                if not match:
                    return None
                return json.loads(match.group(0))
        except Exception as exc:
            logger.warning("RAG query LLM generation failed, fallback heuristic: %s", exc)
            return None

    def _generate_rag_query_heuristic(self, analysis_summary: Dict[str, Any], fallback_query: str) -> Dict[str, Any]:
        p1 = analysis_summary.get("pillar1", {}) if isinstance(analysis_summary, dict) else {}
        p4 = analysis_summary.get("pillar4", {}) if isinstance(analysis_summary, dict) else {}

        products = self._normalize_list(p1.get("products"))
        colors = self._normalize_list(p1.get("colors"))
        categories = self._normalize_list(p1.get("categories"))

        category_filter = self._infer_category_filter(categories=categories, fallback_query=fallback_query)
        price_range = self._infer_price_range(
            budget_specific=p4.get("budget_specific"),
            budget_potential=p4.get("budget_potential"),
        )

        exclude_by_category = {
            "bags": ["pantalon", "cargo", "shirt", "jacket", "jean", "ready_to_wear", "rtw"],
            "small_leather_goods": ["pantalon", "cargo", "valise", "travel_luggage", "rtw"],
            "ready_to_wear": ["wallet", "portefeuille"],
            "watches": ["pantalon", "cargo", "wallet", "portefeuille"],
            "jewelry": ["pantalon", "cargo", "wallet", "portefeuille"],
            "fragrance": ["pantalon", "cargo", "wallet", "portefeuille"],
        }

        boost_keywords = [*products[:2], *categories[:2]]
        if category_filter == "bags":
            boost_keywords.extend(["sac", "iconique", "maroquinerie"])
        elif category_filter == "small_leather_goods":
            boost_keywords.extend(["portefeuille", "small leather", "compact"])

        primary_tokens: List[str] = []
        primary_tokens.extend(products[:2])
        primary_tokens.extend(colors[:2])
        primary_tokens.extend(categories[:2])
        if category_filter == "bags":
            primary_tokens.append("sac")
        if category_filter == "small_leather_goods":
            primary_tokens.append("portefeuille")
        if not primary_tokens:
            primary_tokens = [fallback_query]
        primary_query = " ".join(dict.fromkeys([token for token in primary_tokens if token])).strip()

        return {
            "primary_query": primary_query or fallback_query,
            "category_filter": category_filter,
            "color_filter": colors,
            "price_range": price_range,
            "exclude_keywords": exclude_by_category.get(category_filter, []),
            "boost_keywords": list(dict.fromkeys([kw for kw in boost_keywords if kw])),
        }

    def _sanitize_query_struct(self, data: Dict[str, Any], fallback_query: str) -> Dict[str, Any]:
        if not isinstance(data, dict):
            data = {}

        primary_query = str(data.get("primary_query") or fallback_query).strip() or fallback_query
        category_filter = data.get("category_filter")
        if category_filter is not None:
            category_filter = str(category_filter).strip().lower() or None

        color_filter = [str(v).strip().lower() for v in self._normalize_list(data.get("color_filter")) if str(v).strip()]
        exclude_keywords = [str(v).strip().lower() for v in self._normalize_list(data.get("exclude_keywords")) if str(v).strip()]
        boost_keywords = [str(v).strip().lower() for v in self._normalize_list(data.get("boost_keywords")) if str(v).strip()]

        price_range = None
        raw_price = data.get("price_range")
        if isinstance(raw_price, (list, tuple)) and len(raw_price) == 2:
            try:
                min_price = float(raw_price[0])
                max_price = float(raw_price[1])
                if min_price > max_price:
                    min_price, max_price = max_price, min_price
                price_range = [min_price, max_price]
            except (TypeError, ValueError):
                price_range = None

        return {
            "primary_query": primary_query,
            "category_filter": category_filter,
            "color_filter": color_filter,
            "price_range": price_range,
            "exclude_keywords": exclude_keywords,
            "boost_keywords": boost_keywords,
        }

    def _infer_category_filter(self, categories: List[str], fallback_query: str) -> Optional[str]:
        text = " ".join(categories + [fallback_query]).lower()
        if any(token in text for token in ("small_leather", "slg", "wallet", "portefeuille", "card holder")):
            return "small_leather_goods"
        if any(token in text for token in ("watch", "montre", "watches")):
            return "watches"
        if any(token in text for token in ("jewelry", "jewellery", "bijou")):
            return "jewelry"
        if any(token in text for token in ("fragrance", "parfum", "perfume")):
            return "fragrance"
        if any(token in text for token in ("ready_to_wear", "rtw", "pantalon", "shirt", "jacket", "shoes")):
            return "ready_to_wear"
        if any(
            token in text
            for token in (
                "leather_goods",
                "maroquinerie",
                "bag",
                "sac",
                "handbag",
                "capucines",
                "alma",
                "neverfull",
                "speedy",
            )
        ):
            return "bags"
        return None

    def _infer_price_range(self, budget_specific: Any, budget_potential: Any) -> Optional[List[float]]:
        if budget_specific is not None:
            try:
                value = float(budget_specific)
                if value > 0:
                    return [max(0.0, value * 0.75), value * 1.25]
            except (TypeError, ValueError):
                pass

        potential = str(budget_potential or "").lower()
        if not potential:
            return None

        # Examples handled: "5K-15K", "20K+", "under_2K", "high (5K-15K)"
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*k\s*-\s*(\d+(?:\.\d+)?)\s*k", potential)
        if range_match:
            low = float(range_match.group(1)) * 1000
            high = float(range_match.group(2)) * 1000
            return [low, high]

        plus_match = re.search(r"(\d+(?:\.\d+)?)\s*k\+", potential)
        if plus_match:
            low = float(plus_match.group(1)) * 1000
            return [low, low * 2.0]

        under_match = re.search(r"under[_\s-]*(\d+(?:\.\d+)?)\s*k", potential)
        if under_match:
            high = float(under_match.group(1)) * 1000
            return [0.0, high]

        fallback_map = {
            "entry_level": [500.0, 2000.0],
            "core": [2000.0, 5000.0],
            "high": [5000.0, 15000.0],
            "ultra_high": [15000.0, 50000.0],
        }
        for key, value in fallback_map.items():
            if key in potential:
                return value
        return None

    def _normalize_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if value is None:
            return []
        as_str = str(value).strip()
        if not as_str:
            return []
        return [as_str]

    def _category_matches(self, product_category: str, target_category: str) -> bool:
        if not target_category:
            return True
        product_cat = (product_category or "").lower()
        target = target_category.lower()

        aliases = {
            "bags": ("bag", "sac", "maroquinerie", "leather", "handbag"),
            "small_leather_goods": ("small leather", "slg", "wallet", "portefeuille", "card holder"),
            "ready_to_wear": ("ready to wear", "rtw", "apparel", "clothing", "pantalon", "shirt", "shoes"),
            "watches": ("watch", "montre", "horlog"),
            "jewelry": ("jewel", "bijou", "joailler"),
            "fragrance": ("fragrance", "parfum", "perfume"),
        }
        target_aliases = aliases.get(target, (target,))
        return any(alias in product_cat for alias in target_aliases)

    def _product_matches_colors(self, product_text: str, color_hints: Set[str]) -> bool:
        if not color_hints:
            return True
        normalized_text = product_text.lower()
        for color in color_hints:
            aliases = self.COLOR_ALIASES.get(color, [color])
            if any(alias in normalized_text for alias in aliases):
                return True
        return False

    def _coerce_price(self, raw_value: Any) -> Optional[float]:
        if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
            return None
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None


if __name__ == "__main__":
    matcher = ProductMatcher()
    if matcher.enabled:
        print(matcher.match("Sac noir elegant"))
