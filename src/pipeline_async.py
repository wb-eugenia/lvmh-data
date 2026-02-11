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
from dotenv import load_dotenv

load_dotenv(override=True)

from datetime import datetime
from typing import List, Dict, Optional, Callable

# Add project root to path to allow imports from config
sys.path.append(os.getcwd())

import pandas as pd
from tqdm.asyncio import tqdm

from config.production import settings
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

    async def process_note(self, note: Dict, on_progress: Optional[Callable] = None, **kwargs) -> Optional[PipelineOutput]:
        """
        Process a single note through the pipeline.
        """
        async with self.semaphore:
            start_time = time.time()
            note_id = str(note.get('ID', 'unknown'))
            raw_text = note.get('Transcription') or ''  # Handle None or missing
            language = note.get('Language', 'FR') or 'FR'
            timeout_budget = max(5, int(settings.processing_timeout_seconds))

            # Helper for safe progress reporting
            async def safe_progress(step_data):
                if on_progress:
                    try:
                        payload = {**step_data}
                        if "note_id" not in payload: payload["note_id"] = note_id
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
            await safe_progress({"step": "cleaning", "tokens_saved": 0})
            clean_res = self.cleaner.clean_text(raw_text, language)
            text = clean_res['cleaned']
            tokens_saved = clean_res.get('fillers_removed', 0)
            await safe_progress({"step": "cleaning", "tokens_saved": tokens_saved})
            
            logger.debug(
                "Cleaned note %s: chars=%s tokens_saved=%s",
                note_id,
                len(text),
                tokens_saved
            )

            # 0b. RGPD layer (LLM if available, heuristic fallback otherwise)
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
            
            try:
                # 1. Check Exact Match Cache
                if self.cache:
                    cached_data = self.cache.load(self.cache.get_cache_key(text, 'pipeline_v3'), 'pipeline_v3')
                    if cached_data:
                        await safe_progress({"step": "cache_hit"})
                        await safe_progress({"step": "done"})
                        # Reconstruct PipelineOutput from dict
                        return PipelineOutput(**cached_data)
                
                # 2. Check Semantic Cache (similarity-based)
                if self.semantic_cache:
                    semantic_result = self.semantic_cache.get(text, language)
                    if semantic_result:
                        await safe_progress({"step": "semantic_cache_hit", "similarity": semantic_result.get('_cache_metadata', {}).get('similarity', 0)})
                        await safe_progress({"step": "done"})
                        self.stats['semantic_cache_hits'] += 1
                        # Convert dict back to PipelineOutput
                        return PipelineOutput(**semantic_result)

                # 3. Routing (Use ML Router)
                decision = self.router.route_ml(text, language, note)
                predicted_tier = decision.tier
                await safe_progress({
                    "step": "routing", 
                    "tier": decision.tier,
                    "score": f"{int(decision.score.total)}/100",
                    "priority": decision.priority.upper(),
                    "engine": "Machine Learning" if any("ML" in r for r in decision.reasons) else "Heuristic Engine"
                })
                
                # 4. Extraction with Cross-Validation
                tier_results = {}
                tier_confidences = {}
                
                # Always run Tier 1 for baseline (fast, cheap)
                await safe_progress({"step": "tier1_extraction"})
                tier1_result = self.tier1.extract(text, language)
                if tier1_result:
                    tier_results[1] = tier1_result.model_dump() if hasattr(tier1_result, 'model_dump') else tier1_result
                    tier_confidences[1] = getattr(tier1_result, 'confidence', 0.7)
                self.stats['tier1_exec'] += 1
                
                # Run Tier 2 if routed
                if decision.tier >= 2:
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
                    
                    # Check if we should escalate to Tier 3
                    client_status = getattr(tier2_result.pilier_2_profil_client.purchase_context, 'behavior', None) if tier2_result else None
                    should_escalate = False
                    
                    if tier2_result:
                        if tier2_result.confidence < 0.85:
                            should_escalate = True
                        elif client_status in ['vic', 'ultimate'] and tier2_result.confidence < 0.95:
                            should_escalate = True
                    
                    if should_escalate:
                        logger.info(f"Summary: Escalating Note {note_id} to Tier 3 (Safety/Confidence)")
                        decision.tier = 3
                        decision.reasons.append("Escalated from Tier 2 (Safety/Confidence)")
                    else:
                        self.stats['tier2_exec'] += 1
                
                # Run Tier 3 if routed
                if decision.tier >= 3:
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
                
                # Cross-Validation: Merge results from all tiers
                if self.cross_validator and len(tier_results) > 1:
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
                
                final_tier_used = (
                    decision.tier
                    if decision.tier in tier_results
                    else (max(tier_results.keys()) if tier_results else decision.tier)
                )
                if final_tier_used in (1, 2, 3):
                    self.stats[f'tier{final_tier_used}'] += 1

                # 5. RAG (real product matching)
                if extraction_result:
                    try:
                        self.stats['rag_attempted'] += 1
                        rag_matches = []

                        if budget_exhausted(buffer_seconds=1.5):
                            self.stats['rag_disabled'] += 1
                            await safe_progress({"step": "rag", "status": "skipped_timeout_budget", "matches": 0})
                        elif self.matcher and getattr(self.matcher, 'enabled', False):
                            rag_matches = self.matcher.match(text, top_k=3, threshold=0.35)
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

                # 6. Enrich extraction with NBA recommendation and unified quality scoring.
                if extraction_result:
                    try:
                        extraction_result = self.recommender.generate_recommendation(
                            extraction_result,
                            source_text=text
                        )
                    except Exception as rec_err:
                        logger.warning(f"Recommender enrichment failed for note {note_id}: {rec_err}")

                # Progress after extraction to show count
                if extraction_result:
                    tags = extraction_result.tags
                    await safe_progress({
                        "step": "extraction",
                        "tag_count": len(tags),
                        "model": "Mistral-Medium" if decision.tier <= 2 else "Mistral-Large"
                    })

                # 7. CRM Injection & Gamification
                quality = 0
                feedback = "Note traitée."
                points = 5
                
                if extraction_result:
                    meta = getattr(extraction_result, 'meta_analysis', None)
                    quality = getattr(meta, 'quality_score', 0) if meta else 0
                    quality_pct = quality * 100 if quality <= 1 else quality
                    feedback = getattr(meta, 'advisor_feedback', "Note traitée.") if meta else "Note traitée."
                    points = 10 if quality_pct > 50 else 5
                else:
                    quality_pct = 0

                await safe_progress({
                    "step": "injection", 
                    "points": points,
                    "quality_score": f"{int(quality_pct)}%",
                    "feedback": feedback
                })

                # 8. Build Output
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
                    processing_time_ms=(time.time() - start_time) * 1000,
                    from_cache=False
                )
                
                # 8b. Online ML feedback loop for router learning in production.
                if (
                    extraction_result
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
                if self.cache and kwargs.get('save_to_cache', True):
                    serialized = output.model_dump(mode="json")
                    self.cache.save(
                        self.cache.get_cache_key(text, 'pipeline_v3'), 
                        'pipeline_v3', 
                        serialized
                    )
                
                # 9b. Semantic Cache (for similarity-based retrieval)
                if self.semantic_cache and kwargs.get('save_to_cache', True):
                    result_dict = output.model_dump() if hasattr(output, 'model_dump') else json.loads(output.json())
                    self.semantic_cache.store(
                        text=text,
                        result=result_dict,
                        tier_used=decision.tier,
                        language=language
                    )
                
                self.stats['success'] += 1
                await safe_progress({"step": "done"})
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

    async def process_batch(self, notes: List[Dict]) -> List[PipelineOutput]:
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
        
        tasks = [self.process_note(note) for note in notes]
        
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
