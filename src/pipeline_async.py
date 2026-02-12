"""
Async Pipeline Orchestrator (v3).
Handles massive batch processing with asyncio, concurrency control, and resilience.
Integrates:
- Smart Router v2
- Tier 1 (Rules)
- Tier 2 (Async Mistral)
- Tier 3 (Async Mistral Premium)
- DLQ & Caching
"""

import asyncio
import json
import logging
import time
import sys
import os
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv(override=True)

from datetime import datetime
from typing import Any, List, Dict, Optional, Callable

# Add project root to path to allow imports from config
sys.path.append(os.getcwd())

import pandas as pd
from tqdm.asyncio import tqdm

from config.production import settings, RuntimeProfile
from src.models import PipelineOutput, RoutingDecision, ExtractionResult, RGPDResult
from src.smart_router import SmartRouterV2
from src.tier1_rules import Tier1RulesEngine
from src.tier2_mistral import Tier2Mistral
from src.extractor import TagExtractor
from src.text_cleaner import MultilingualTextCleaner, HAS_EMBEDDINGS
from src.cache_manager import CacheManager
from src.dlq_manager import DeadLetterQueue
from src.resilience import safe_execution
from src.semantic_cache import SemanticCache
from src.cross_validator import CrossValidator
from src.recommender import RecommenderEngine
from src.product_matcher import ProductMatcher
from src.rgpd_filter import RGPDFilter

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AsyncPipeline:
    """
    Production-ready Async Pipeline.
    """

    RGPD_MARKERS = [
        '[EMAIL]',
        '[PHONE]',
        '[CARTE]',
        '[NAME]',
        '[RIB]',
        '[CVC]',
        '[CARTE_VITALE]',
        '[DNI]',
        '[NIF]',
        '[PASSPORT]',
        '[SSN]',
        '[FISCAL]',
    ]
    HIGH_SIGNAL_KEYWORDS = (
        "budget",
        "cadeau",
        "gift",
        "vip",
        "vic",
        "urgent",
        "birthday",
        "wedding",
        "allerg",
        "marriage",
        "anniversaire",
        "travel",
        "work",
    )
    PRODUCT_HINTS = (
        "sac",
        "bag",
        "ceinture",
        "belt",
        "watch",
        "montre",
        "wallet",
        "portefeuille",
        "chaussure",
        "shoe",
        "fragrance",
        "parfum",
        "jewelry",
        "bijou",
    )
    
    def __init__(self, use_cache: bool = True, use_semantic_cache: bool = True, use_cross_validation: bool = True):
        self.router = SmartRouterV2()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = Tier2Mistral()
        self.tier3 = TagExtractor()
        self.recommender = RecommenderEngine()
        self.matcher = ProductMatcher()
        self.cleaner = MultilingualTextCleaner(use_embeddings=False) # Keep it light by default
        self.rgpd_filter = None
        self.rgpd_enabled = False

        if settings.enable_rgpd_llm:
            try:
                self.rgpd_filter = RGPDFilter(model=settings.rgpd_model)
                self.rgpd_enabled = True
            except Exception as rgpd_init_error:
                logger.warning(
                    "RGPD LLM filter disabled, fallback mode enabled: %s",
                    rgpd_init_error
                )
        
        # Caching systems
        self.cache = CacheManager() if use_cache else None
        self.semantic_cache = SemanticCache() if use_semantic_cache and HAS_EMBEDDINGS else None
        self.cross_validator = CrossValidator() if use_cross_validation else None
        self.profile_configs: Dict[str, RuntimeProfile] = {
            settings.single_note_profile.name: settings.single_note_profile,
            settings.batch_csv_profile.name: settings.batch_csv_profile,
            settings.fast_batch_profile.name: settings.fast_batch_profile,
        }
        if "single_note" not in self.profile_configs:
            self.profile_configs["single_note"] = settings.single_note_profile
        if "batch_csv" not in self.profile_configs:
            self.profile_configs["batch_csv"] = settings.batch_csv_profile
        if "fast_batch" not in self.profile_configs:
            self.profile_configs["fast_batch"] = settings.fast_batch_profile
        
        self.dlq = DeadLetterQueue()
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_notes)
        self.ollama_semaphore = asyncio.Semaphore(settings.max_concurrent_tier2_calls)
        self.openai_semaphore = asyncio.Semaphore(settings.max_concurrent_tier3_calls)
        
        # Stats
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'tier1': 0,
            'tier2': 0,
            'tier3': 0,
            'tier1_exec': 0,
            'tier2_exec': 0,
            'tier3_exec': 0,
            'semantic_cache_hits': 0,
            'cross_validated': 0,
            'rag_attempted': 0,
            'rag_hits': 0,
            'rag_disabled': 0,
            'start_time': None
        }
        self.profile_runtime_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "latencies_ms": deque(maxlen=1000),
                "fallback_count": 0,
                "notes_without_tags": 0,
                "stage_totals_ms": defaultdict(float),
            }
        )

    @staticmethod
    def _build_heuristic_rgpd(text: str) -> RGPDResult:
        categories = [token for token in AsyncPipeline.RGPD_MARKERS if token in text]
        has_critical = any(token in text for token in ['[CARTE]', '[RIB]', '[SSN]', '[CARTE_VITALE]'])
        return RGPDResult(
            contains_sensitive=bool(categories),
            categories_detected=categories,
            safe_to_store=True,
            severity="medium" if has_critical else ("low" if categories else "low"),
            anonymized_text=text
        )

    @staticmethod
    def _derive_rgpd_severity(detection: Dict) -> str:
        spans = detection.get("sensitive_spans") or []
        severities = {str(span.get("severity", "")).lower() for span in spans if isinstance(span, dict)}
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    @staticmethod
    def _merge_unique(primary: List[str], secondary: List[str]) -> List[str]:
        merged: List[str] = []
        for value in list(primary or []) + list(secondary or []):
            if not isinstance(value, str):
                continue
            item = value.strip()
            if not item:
                continue
            if item not in merged:
                merged.append(item)
        return merged

    def _resolve_profile(self, profile: str) -> RuntimeProfile:
        if profile in self.profile_configs:
            return self.profile_configs[profile]
        return self.profile_configs["single_note"]

    def _has_high_signal(self, text: str) -> bool:
        lowered = (text or "").lower()
        if len(lowered.split()) >= 18:
            return True
        hits = sum(1 for token in self.HIGH_SIGNAL_KEYWORDS if token in lowered)
        return hits >= 2

    def _deterministic_minimum_tag(self, text: str) -> str:
        lowered = (text or "").lower()
        if any(token in lowered for token in ("watch", "montre", "timepiece", "orologio")):
            return "watches"
        if any(token in lowered for token in ("jewel", "bijou", "bracelet", "ring", "bague")):
            return "jewelry"
        if any(token in lowered for token in ("shoe", "chaussure", "sneaker", "basket")):
            return "shoes"
        if any(token in lowered for token in ("fragrance", "parfum", "perfume", "cologne")):
            return "fragrance"
        if any(token in lowered for token in ("ceinture", "belt", "cintura")):
            return "belts"
        if any(token in lowered for token in ("wallet", "portefeuille", "card holder", "pochette")):
            return "small_leather"
        if any(token in lowered for token in ("travel", "voyage", "luggage", "valise")):
            return "travel_luggage"
        if any(token in lowered for token in self.PRODUCT_HINTS):
            return "leather_goods"
        return "accessories"

    def _apply_quality_fallback(
        self,
        extraction_result: Optional[ExtractionResult],
        *,
        text: str,
        language: str,
        require_non_empty_tags: bool,
    ) -> tuple[Optional[ExtractionResult], List[str]]:
        fallbacks: List[str] = []

        if extraction_result is None:
            extraction_result = self.tier1.extract(text, language)
            fallbacks.append("tier1_recovery")

        if extraction_result is None:
            return None, fallbacks

        if not require_non_empty_tags or extraction_result.tags:
            return extraction_result, fallbacks

        tier1_candidate = self.tier1.extract(text, language)
        if tier1_candidate and tier1_candidate.tags:
            p1 = extraction_result.pilier_1_univers_produit
            p1.categories = self._merge_unique(p1.categories, tier1_candidate.pilier_1_univers_produit.categories)
            p1.produits_mentionnes = self._merge_unique(
                p1.produits_mentionnes,
                tier1_candidate.pilier_1_univers_produit.produits_mentionnes,
            )
            p1.usage = self._merge_unique(p1.usage, tier1_candidate.pilier_1_univers_produit.usage)
            p1.preferences.colors = self._merge_unique(
                p1.preferences.colors,
                tier1_candidate.pilier_1_univers_produit.preferences.colors,
            )
            p1.preferences.materials = self._merge_unique(
                p1.preferences.materials,
                tier1_candidate.pilier_1_univers_produit.preferences.materials,
            )
            p1.preferences.styles = self._merge_unique(
                p1.preferences.styles,
                tier1_candidate.pilier_1_univers_produit.preferences.styles,
            )
            p1.preferences.hardware = self._merge_unique(
                p1.preferences.hardware,
                tier1_candidate.pilier_1_univers_produit.preferences.hardware,
            )
            fallbacks.append("tier1_no_tag_merge")

        if not extraction_result.tags:
            p1 = extraction_result.pilier_1_univers_produit
            p1.categories = self._merge_unique(p1.categories, [self._deterministic_minimum_tag(text)])
            fallbacks.append("deterministic_minimum_tag")

        if not extraction_result.tags and require_non_empty_tags:
            # Last-resort safety net for strict contracts.
            p1 = extraction_result.pilier_1_univers_produit
            p1.categories = self._merge_unique(p1.categories, ["customer_intent"])
            fallbacks.append("contractual_forced_tag")

        return extraction_result, fallbacks

    def _record_profile_runtime(
        self,
        profile: str,
        processing_time_ms: float,
        stage_timings_ms: Dict[str, float],
        *,
        tags_count: int,
        fallback_used: bool,
    ) -> None:
        pstats = self.profile_runtime_stats[profile]
        pstats["count"] += 1
        pstats["latencies_ms"].append(float(processing_time_ms))
        if tags_count == 0:
            pstats["notes_without_tags"] += 1
        if fallback_used:
            pstats["fallback_count"] += 1
        for stage, value in stage_timings_ms.items():
            pstats["stage_totals_ms"][stage] += float(value)

    @staticmethod
    def _percentile(values: List[float], p: float) -> float:
        if not values:
            return 0.0
        arr = sorted(values)
        idx = int(round((p / 100.0) * (len(arr) - 1)))
        return float(arr[idx])

    def get_profile_metrics(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for profile, stats in self.profile_runtime_stats.items():
            latencies = list(stats["latencies_ms"])
            count = int(stats["count"])
            stage_avgs = {}
            if count > 0:
                for stage, total in stats["stage_totals_ms"].items():
                    stage_avgs[stage] = round(float(total) / count, 2)
            payload[profile] = {
                "count": count,
                "p50_ms": round(self._percentile(latencies, 50), 2),
                "p95_ms": round(self._percentile(latencies, 95), 2),
                "avg_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                "notes_without_tags": int(stats["notes_without_tags"]),
                "fallback_rate_pct": round((stats["fallback_count"] / count) * 100, 2) if count else 0.0,
                "stage_avg_ms": stage_avgs,
            }
        return payload

    async def process_note(
        self,
        note: Dict,
        on_progress: Optional[Callable] = None,
        profile: str = "single_note",
        **kwargs,
    ) -> Optional[PipelineOutput]:
        """
        Process a single note through the pipeline.
        """
        async with self.semaphore:
            start_time = time.time()
            perf_start = time.perf_counter()
            note_id = str(note.get('ID', 'unknown'))
            raw_text = note.get('Transcription') or ''  # Handle None or missing
            language = note.get('Language', 'FR') or 'FR'
            runtime_profile = self._resolve_profile(str(kwargs.get("profile") or profile or "single_note"))
            timeout_budget = max(5, int(kwargs.get("timeout_seconds") or runtime_profile.timeout_seconds))
            cache_enabled = bool(kwargs.get("save_to_cache", runtime_profile.save_to_cache))
            semantic_cache_enabled = bool(self.semantic_cache and runtime_profile.save_to_semantic_cache)
            fast_batch_mode = runtime_profile.name == settings.fast_batch_profile.name
            cache_namespace = f"pipeline_v3_{runtime_profile.name}"
            high_signal_input = self._has_high_signal(raw_text)
            stage_timings_ms: Dict[str, float] = {}
            fallbacks_applied: List[str] = []

            def mark_stage(stage: str, started_at: float) -> None:
                stage_timings_ms[stage] = round((time.perf_counter() - started_at) * 1000.0, 2)

            # Helper for safe progress reporting
            async def safe_progress(step_data):
                if on_progress:
                    try:
                        payload = {**step_data}
                        if "note_id" not in payload: payload["note_id"] = note_id
                        payload["profile"] = runtime_profile.name
                        await on_progress(payload)
                    except Exception as pe:
                        logger.warning(f"Progress report failed for step {step_data.get('step')}: {pe}")

            def remaining_budget_seconds() -> float:
                return timeout_budget - (time.time() - start_time)

            def budget_exhausted(buffer_seconds: float = 0.0) -> bool:
                return remaining_budget_seconds() <= buffer_seconds

            async def run_with_semaphore_timeout(semaphore: asyncio.Semaphore, coro_factory, timeout_seconds: float):
                async def runner():
                    async with semaphore:
                        return await coro_factory()
                return await asyncio.wait_for(runner(), timeout=timeout_seconds)

            # 0. Data Cleaning
            cleaning_started = time.perf_counter()
            await safe_progress({"step": "cleaning", "tokens_saved": 0})
            clean_res = self.cleaner.clean_text(raw_text, language)
            text = clean_res['cleaned']
            tokens_saved = clean_res.get('fillers_removed', 0)
            await safe_progress({"step": "cleaning", "tokens_saved": tokens_saved})
            mark_stage("cleaning", cleaning_started)
            
            logger.debug(
                "Cleaned note %s: chars=%s tokens_saved=%s",
                note_id,
                len(text),
                tokens_saved
            )

            # 0b. RGPD layer (LLM if available, heuristic fallback otherwise)
            rgpd_started = time.perf_counter()
            await safe_progress({"step": "rgpd", "status": "processing"})
            rgpd_result = self._build_heuristic_rgpd(text)

            if self.rgpd_enabled and self.rgpd_filter:
                try:
                    rgpd_payload = self.rgpd_filter.process_note(
                        {
                            "ID": note_id,
                            "Transcription": text,
                            "Language": language,
                        }
                    )
                    detection = rgpd_payload.get("rgpd_result") or {}
                    anonymized_text = rgpd_payload.get("anonymized_text") or text
                    text = anonymized_text
                    rgpd_result = RGPDResult(
                        contains_sensitive=bool(detection.get("contains_sensitive", False)),
                        categories_detected=[
                            str(category) for category in (detection.get("categories_detected") or [])
                        ],
                        safe_to_store=bool(detection.get("safe_to_store", True)),
                        severity=self._derive_rgpd_severity(detection),
                        reasoning=detection.get("reasoning"),
                        anonymized_text=anonymized_text,
                    )
                    await safe_progress(
                        {
                            "step": "rgpd",
                            "status": "llm",
                            "contains_sensitive": rgpd_result.contains_sensitive,
                            "categories": rgpd_result.categories_detected,
                        }
                    )
                except Exception as rgpd_error:
                    logger.warning("RGPD LLM step failed for note %s: %s", note_id, rgpd_error)
                    rgpd_result = self._build_heuristic_rgpd(text)
                    text = rgpd_result.anonymized_text or text
                    await safe_progress(
                        {
                            "step": "rgpd",
                            "status": "fallback",
                            "contains_sensitive": rgpd_result.contains_sensitive,
                            "categories": rgpd_result.categories_detected,
                        }
                    )
            else:
                await safe_progress(
                    {
                        "step": "rgpd",
                        "status": "heuristic",
                        "contains_sensitive": rgpd_result.contains_sensitive,
                        "categories": rgpd_result.categories_detected,
                    }
                )
            mark_stage("rgpd", rgpd_started)
            
            try:
                # 1. Check Exact Match Cache
                cache_lookup_started = time.perf_counter()
                if self.cache and cache_enabled:
                    cached_data = self.cache.load(
                        self.cache.get_cache_key(text, cache_namespace),
                        cache_namespace
                    )
                    if cached_data:
                        mark_stage("cache_lookup", cache_lookup_started)
                        await safe_progress({"step": "cache_hit"})
                        await safe_progress({"step": "done"})
                        # Reconstruct PipelineOutput from dict
                        output = PipelineOutput(**cached_data)
                        output.profile = runtime_profile.name
                        output.stage_timings_ms = output.stage_timings_ms or stage_timings_ms
                        output.processing_time_ms = float(
                            output.processing_time_ms or ((time.time() - start_time) * 1000.0)
                        )
                        self._record_profile_runtime(
                            runtime_profile.name,
                            output.processing_time_ms,
                            output.stage_timings_ms,
                            tags_count=len(output.extraction.tags) if output.extraction else 0,
                            fallback_used=False,
                        )
                        return output
                mark_stage("cache_lookup", cache_lookup_started)
                
                # 2. Check Semantic Cache (similarity-based)
                semantic_lookup_started = time.perf_counter()
                if semantic_cache_enabled:
                    semantic_result = self.semantic_cache.get(text, language)
                    if semantic_result:
                        await safe_progress({"step": "semantic_cache_hit", "similarity": semantic_result.get('_cache_metadata', {}).get('similarity', 0)})
                        await safe_progress({"step": "done"})
                        self.stats['semantic_cache_hits'] += 1
                        # Convert dict back to PipelineOutput
                        output = PipelineOutput(**semantic_result)
                        output.profile = runtime_profile.name
                        output.stage_timings_ms = output.stage_timings_ms or stage_timings_ms
                        output.processing_time_ms = float(
                            output.processing_time_ms or ((time.time() - start_time) * 1000.0)
                        )
                        self._record_profile_runtime(
                            runtime_profile.name,
                            output.processing_time_ms,
                            output.stage_timings_ms,
                            tags_count=len(output.extraction.tags) if output.extraction else 0,
                            fallback_used=False,
                        )
                        return output
                mark_stage("semantic_cache_lookup", semantic_lookup_started)

                # 3. Routing (Use ML Router)
                routing_started = time.perf_counter()
                decision = self.router.route_ml(text, language, note)
                if fast_batch_mode:
                    decision.tier = 1
                    decision.priority = "low"
                    decision.reasons.append("Fast batch profile: Tier 1 only mode")
                predicted_tier = decision.tier
                await safe_progress({
                    "step": "routing", 
                    "tier": decision.tier,
                    "score": f"{int(decision.score.total)}/100",
                    "priority": decision.priority.upper(),
                    "engine": (
                        "Fast Tier1"
                        if fast_batch_mode
                        else ("Machine Learning" if any("ML" in r for r in decision.reasons) else "Heuristic Engine")
                    ),
                })
                mark_stage("routing", routing_started)
                
                # 4. Extraction with Cross-Validation
                tier_results = {}
                tier_confidences = {}
                
                # Always run Tier 1 for baseline (fast, cheap)
                tier1_started = time.perf_counter()
                await safe_progress({"step": "tier1_extraction"})
                tier1_result = self.tier1.extract(text, language)
                if tier1_result:
                    tier_results[1] = tier1_result.model_dump() if hasattr(tier1_result, 'model_dump') else tier1_result
                    tier_confidences[1] = getattr(tier1_result, 'confidence', 0.7)
                self.stats['tier1_exec'] += 1
                mark_stage("tier1", tier1_started)
                
                # Run Tier 2 if routed
                if decision.tier >= 2 and not fast_batch_mode:
                    tier2_started = time.perf_counter()
                    await safe_progress({"step": "tier2_extraction"})
                    tier2_result = None
                    if budget_exhausted(buffer_seconds=3):
                        decision.tier = 1
                        decision.reasons.append("Timeout budget reached before Tier 2")
                        logger.warning("Note %s skipped Tier 2 due timeout budget", note_id)
                    else:
                        try:
                            tier2_timeout = max(3.0, min(remaining_budget_seconds(), float(timeout_budget)))
                            tier2_result = await run_with_semaphore_timeout(
                                self.ollama_semaphore,
                                lambda: self.tier2.extract(text, language),
                                timeout_seconds=tier2_timeout
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Tier 2 timed out for note %s after %.1fs", note_id, tier2_timeout)
                            decision.tier = 1
                            decision.reasons.append("Tier 2 timeout")
                        except Exception as tier2_err:
                            logger.warning("Tier 2 failed for note %s: %s", note_id, tier2_err)
                            decision.tier = 1
                            decision.reasons.append("Tier 2 failure")
                    
                    if tier2_result:
                        tier_results[2] = tier2_result.model_dump() if hasattr(tier2_result, 'model_dump') else tier2_result
                        tier_confidences[2] = getattr(tier2_result, 'confidence', 0.85)
                    
                    # Escalation guardrail:
                    # Tier 3 is expensive/slow and currently less stable for some multilingual cases.
                    # Escalate only on clearly critical uncertainty.
                    client_status = (
                        getattr(tier2_result.pilier_2_profil_client.purchase_context, 'behavior', None)
                        if tier2_result else None
                    )
                    should_escalate = False

                    if tier2_result:
                        tier2_conf = float(getattr(tier2_result, "confidence", 0.0) or 0.0)
                        critical_client = str(client_status or "").lower() in {'vic', 'ultimate', 'platinum'}
                        high_risk_note = str(decision.priority or "").lower() in {'high', 'critical'}

                        # Escalate for critical clients if confidence is clearly below premium bar.
                        if critical_client and tier2_conf < 0.90:
                            should_escalate = True
                        # Escalate only if extremely uncertain on high-risk notes.
                        elif high_risk_note and tier2_conf < 0.60:
                            should_escalate = True

                    if should_escalate:
                        logger.info(
                            "Summary: Escalating Note %s to Tier 3 (critical confidence gate)",
                            note_id,
                        )
                        decision.tier = 3
                        decision.reasons.append("Escalated from Tier 2 (critical confidence gate)")
                    else:
                        self.stats['tier2_exec'] += 1
                    mark_stage("tier2", tier2_started)
                
                # Run Tier 3 if routed
                if decision.tier >= 3 and not fast_batch_mode:
                    tier3_started = time.perf_counter()
                    await safe_progress({"step": "tier3_extraction"})
                    tier3_result = None
                    if budget_exhausted(buffer_seconds=3):
                        decision.tier = 2 if 2 in tier_results else 1
                        decision.reasons.append("Timeout budget reached before Tier 3")
                        logger.warning("Note %s skipped Tier 3 due timeout budget", note_id)
                    else:
                        try:
                            tier3_timeout = max(3.0, min(remaining_budget_seconds(), float(timeout_budget)))
                            tier3_result = await run_with_semaphore_timeout(
                                self.openai_semaphore,
                                lambda: self.tier3.extract(
                                    text,
                                    language,
                                    client_status=None,
                                    escalation_reason=decision.reasons[-1] if decision.reasons else None,
                                    use_cache=False
                                ),
                                timeout_seconds=tier3_timeout
                            )
                        except asyncio.TimeoutError:
                            decision.tier = 2 if 2 in tier_results else 1
                            decision.reasons.append("Tier 3 timeout")
                            logger.warning("Tier 3 timed out for note %s after %.1fs", note_id, tier3_timeout)
                        except Exception as tier3_err:
                            decision.tier = 2 if 2 in tier_results else 1
                            decision.reasons.append("Tier 3 failure")
                            logger.warning("Tier 3 failed for note %s: %s", note_id, tier3_err)
                    
                    if tier3_result:
                        tier_results[3] = tier3_result.model_dump() if hasattr(tier3_result, 'model_dump') else tier3_result
                        tier_confidences[3] = getattr(tier3_result, 'confidence', 0.95)
                    self.stats['tier3_exec'] += 1
                    mark_stage("tier3", tier3_started)
                
                # Cross-Validation: Merge results from all tiers
                crossval_started = time.perf_counter()
                if (
                    not fast_batch_mode
                    and runtime_profile.allow_cross_validation
                    and self.cross_validator
                    and len(tier_results) > 1
                ):
                    await safe_progress({"step": "cross_validation", "tiers": list(tier_results.keys())})
                    
                    validation = self.cross_validator.validate(tier_results, tier_confidences)
                    
                    # Log validation insights
                    if validation.validation_notes:
                        for note in validation.validation_notes:
                            logger.debug(f"Cross-Validation: {note}")
                    
                    # Reconstruct extraction result from merged data
                    # Use the highest tier result as base, override with merged fields
                    base_tier = max(tier_results.keys())
                    from src.models import ExtractionResult
                    
                    # Convert merged dict back to ExtractionResult
                    try:
                        merged_result = validation.merged_result
                        # Add metadata about validation
                        merged_result['_validation'] = {
                            'agreement_score': validation.agreement_score,
                            'dominant_tier': validation.dominant_tier,
                            'tiers_used': list(tier_results.keys())
                        }
                        extraction_result = ExtractionResult(**merged_result)
                        self.stats['cross_validated'] += 1
                    except Exception as e:
                        logger.warning(f"Cross-validation reconstruction failed: {e}, using Tier {base_tier} result")
                        extraction_result = tier_results[base_tier]
                        if isinstance(extraction_result, dict):
                            extraction_result = ExtractionResult(**extraction_result)
                else:
                    # Use single tier result
                    extraction_result = tier_results.get(decision.tier) or tier_results.get(max(tier_results.keys()))
                    if isinstance(extraction_result, dict):
                        from src.models import ExtractionResult
                        extraction_result = ExtractionResult(**extraction_result)
                mark_stage("cross_validation", crossval_started)
                
                final_tier_used = (
                    decision.tier
                    if decision.tier in tier_results
                    else (max(tier_results.keys()) if tier_results else decision.tier)
                )
                if final_tier_used in (1, 2, 3):
                    self.stats[f'tier{final_tier_used}'] += 1

                # 5. RAG (real product matching)
                rag_started = time.perf_counter()
                if extraction_result:
                    try:
                        self.stats['rag_attempted'] += 1
                        rag_matches = []

                        if fast_batch_mode:
                            self.stats['rag_disabled'] += 1
                            await safe_progress({"step": "rag", "status": "skipped_fast_batch", "matches": 0})
                        elif budget_exhausted(buffer_seconds=1.5):
                            self.stats['rag_disabled'] += 1
                            await safe_progress({"step": "rag", "status": "skipped_timeout_budget", "matches": 0})
                        elif self.matcher and getattr(self.matcher, 'enabled', False):
                            rag_matches = self.matcher.match(
                                text,
                                top_k=int(runtime_profile.rag_top_k),
                                threshold=float(runtime_profile.rag_threshold)
                            )
                            extraction_result.pilier_1_univers_produit.matched_products = rag_matches
                            if rag_matches:
                                self.stats['rag_hits'] += 1
                            await safe_progress({
                                "step": "rag",
                                "matches": len(rag_matches),
                                "best_score": rag_matches[0].get("match_score", 0) if rag_matches else 0
                            })
                        else:
                            self.stats['rag_disabled'] += 1
                            await safe_progress({"step": "rag", "status": "disabled", "matches": 0})
                    except Exception as rag_err:
                        logger.warning(f"RAG enrichment failed for note {note_id}: {rag_err}")
                        await safe_progress({"step": "rag", "status": "error", "matches": 0})
                mark_stage("rag", rag_started)

                # 6. Enrich extraction with NBA recommendation and unified quality scoring.
                recommendation_started = time.perf_counter()
                if extraction_result and not fast_batch_mode:
                    try:
                        extraction_result = self.recommender.generate_recommendation(
                            extraction_result,
                            source_text=text
                        )
                    except Exception as rec_err:
                        logger.warning(f"Recommender enrichment failed for note {note_id}: {rec_err}")
                mark_stage("recommendation", recommendation_started)

                quality_gate_started = time.perf_counter()
                if fast_batch_mode:
                    gate_fallbacks = []
                    tags_count = len(extraction_result.tags) if extraction_result else 0
                else:
                    extraction_result, gate_fallbacks = self._apply_quality_fallback(
                        extraction_result,
                        text=text,
                        language=language,
                        require_non_empty_tags=runtime_profile.require_non_empty_tags,
                    )
                    if gate_fallbacks:
                        fallbacks_applied.extend(gate_fallbacks)
                    tags_count = len(extraction_result.tags) if extraction_result else 0
                quality_gate_passed = True
                quality_gate_reason = None
                if runtime_profile.strict_quality_gate and high_signal_input and tags_count == 0:
                    quality_gate_passed = False
                    quality_gate_reason = "High-signal note produced empty tags after fallback."
                mark_stage("quality_gate", quality_gate_started)

                # Progress after extraction to show count
                if extraction_result:
                    await safe_progress({
                        "step": "extraction",
                        "tag_count": tags_count,
                        "model": "Tier1-Fast" if fast_batch_mode else ("Mistral-Medium" if decision.tier <= 2 else "Mistral-Large")
                    })

                # 7. CRM Injection & Gamification
                injection_started = time.perf_counter()
                quality = 0
                feedback = "Note traitée."
                points = 5
                
                if extraction_result:
                    meta = getattr(extraction_result, 'meta_analysis', None)
                    quality = getattr(meta, 'quality_score', 0) if meta else 0
                    quality_pct = quality * 100 if quality <= 1 else quality
                    feedback = getattr(meta, 'advisor_feedback', "Note traitée.") if meta else "Note traitée."
                    points = 10 if quality_pct > 50 else 5
                    if fast_batch_mode:
                        points = 0
                        feedback = "Mode fast_batch: extraction Tier 1 prioritaire."
                else:
                    quality_pct = 0

                await safe_progress({
                    "step": "injection", 
                    "points": points,
                    "quality_score": f"{int(quality_pct)}%",
                    "feedback": feedback
                })
                mark_stage("injection", injection_started)

                # 8. Build Output
                stage_timings_ms["total"] = round((time.perf_counter() - perf_start) * 1000.0, 2)
                total_processing_ms = (time.time() - start_time) * 1000
                output = PipelineOutput(
                    id=note_id,
                    original_text=raw_text,
                    processed_text=text,
                    language=language,
                    timestamp=datetime.now(),
                    routing=RoutingDecision(
                        tier=final_tier_used,
                        reasons=decision.reasons,
                        confidence=decision.confidence,
                        priority=decision.priority
                    ),
                    rgpd=rgpd_result,
                    extraction=extraction_result,
                    profile=runtime_profile.name,
                    stage_timings_ms=stage_timings_ms,
                    fallbacks_applied=fallbacks_applied,
                    quality_gate_passed=quality_gate_passed,
                    quality_gate_reason=quality_gate_reason,
                    high_signal_input=high_signal_input,
                    processing_time_ms=total_processing_ms,
                    from_cache=False
                )
                
                # 8b. Online ML feedback loop for router learning in production.
                if (
                    extraction_result
                    and not fast_batch_mode
                    and settings.enable_router_feedback_learning
                    and hasattr(self.router, "record_feedback")
                ):
                    try:
                        final_confidence = float(
                            getattr(extraction_result, "confidence", decision.confidence) or decision.confidence or 0.0
                        )
                        self.router.record_feedback(
                            text=text,
                            predicted_tier=predicted_tier,
                            executed_tier=predicted_tier,
                            confidence_achieved=final_confidence,
                            was_escalated=(final_tier_used != predicted_tier),
                            final_tier=final_tier_used,
                            final_confidence=final_confidence,
                        )
                    except Exception as fb_err:
                        logger.debug(f"Router feedback record failed for note {note_id}: {fb_err}")
                
                # 9. Cache Results
                # 9a. Exact Match Cache
                if self.cache and cache_enabled:
                    serialized = output.model_dump(mode="json")
                    self.cache.save(
                        self.cache.get_cache_key(text, cache_namespace), 
                        cache_namespace, 
                        serialized
                    )
                
                # 9b. Semantic Cache (for similarity-based retrieval)
                if self.semantic_cache and semantic_cache_enabled:
                    result_dict = output.model_dump() if hasattr(output, 'model_dump') else json.loads(output.json())
                    self.semantic_cache.store(
                        text=text,
                        result=result_dict,
                        tier_used=decision.tier,
                        language=language
                    )
                
                self.stats['success'] += 1
                self._record_profile_runtime(
                    runtime_profile.name,
                    total_processing_ms,
                    stage_timings_ms,
                    tags_count=tags_count,
                    fallback_used=bool(fallbacks_applied),
                )
                await safe_progress({"step": "done", "quality_gate_passed": quality_gate_passed})
                return output

            except Exception as e:
                self.stats['failed'] += 1
                logger.error(f"Pipeline error for note {note_id}: {e}")
                await safe_progress({"step": "failed", "error": str(e)})
                
                # Send to DLQ
                self.dlq.add(
                    note_id=note_id,
                    note_text=text,
                    error=str(e),
                    tier_attempted=f"tier{decision.tier}" if 'decision' in locals() else "unknown",
                    retry_count=settings.retry_max_attempts
                )
                return None

    async def process_batch(self, notes: List[Dict], profile: str = "batch_csv") -> List[PipelineOutput]:
        """
        Process a batch of notes concurrently.
        """
        self.stats['start_time'] = time.time()
        for key in (
            'processed',
            'success',
            'failed',
            'tier1',
            'tier2',
            'tier3',
            'tier1_exec',
            'tier2_exec',
            'tier3_exec',
            'semantic_cache_hits',
            'cross_validated',
            'rag_attempted',
            'rag_hits',
            'rag_disabled',
        ):
            self.stats[key] = 0
        
        tasks = [self.process_note(note, profile=profile) for note in notes]
        
        results = []
        for f in tqdm.as_completed(tasks, total=len(notes), desc="🚀 Async Pipeline"):
            result = await f
            if result:
                results.append(result)
        
        return results

    def get_summary(self) -> Dict:
        """Get execution summary."""
        duration = time.time() - (self.stats['start_time'] or time.time())
        total_processed = self.stats['success'] + self.stats['failed']
        
        summary = {
            "duration_seconds": round(duration, 2),
            "processed": total_processed,
            "success": self.stats['success'],
            "failed": self.stats['failed'],
            "tiers": {
                "tier1": self.stats['tier1'],
                "tier2": self.stats['tier2'],
                "tier3": self.stats['tier3']
            },
            "tiers_executed": {
                "tier1": self.stats.get('tier1_exec', 0),
                "tier2": self.stats.get('tier2_exec', 0),
                "tier3": self.stats.get('tier3_exec', 0)
            },
        }
        
        # Add semantic cache stats
        if self.semantic_cache:
            cache_stats = self.semantic_cache.get_stats()
            summary['semantic_cache'] = cache_stats
        
        # Add cross-validation stats
        summary['cross_validation'] = {
            'enabled': self.cross_validator is not None,
            'notes_merged': self.stats.get('cross_validated', 0)
        }
        summary['rag'] = {
            'attempted': self.stats.get('rag_attempted', 0),
            'hits': self.stats.get('rag_hits', 0),
            'hit_rate': round(
                (self.stats.get('rag_hits', 0) / self.stats.get('rag_attempted', 1)) * 100, 2
            ) if self.stats.get('rag_attempted', 0) > 0 else 0.0,
            'disabled': self.stats.get('rag_disabled', 0)
        }
        summary['profiles'] = self.get_profile_metrics()
        
        return summary

if __name__ == "__main__":
    # Test run
    async def main():
        pipeline = AsyncPipeline()
        
        try:
            input_file = 'LVMH_Realistic_Merged_CA001-100.csv'
            # Try loading from root or data folder
            if not os.path.exists(input_file):
                input_file = os.path.join('data', 'processed', 'LVMH_Notes_CA101-400_cleaned.csv') # Fallback if direct file not found
            
            # Prefer the realistic file if available in root
            if os.path.exists('LVMH_Realistic_Merged_CA001-100.csv'):
                input_file = 'LVMH_Realistic_Merged_CA001-100.csv'

            df = pd.read_csv(input_file)
            notes = df.to_dict('records')
            
            # LIMIT TO 100 for the test as requested
            notes = notes[:100]
            
            print(f"🚀 Starting Async Pipeline on {len(notes)} notes...")
            results = await pipeline.process_batch(notes)
            
            print(f"\n✅ Completed {len(results)} notes.")
            print(json.dumps(pipeline.get_summary(), indent=2))
            
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())
