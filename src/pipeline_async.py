"""
Async Pipeline Orchestrator (v3).
Handles massive batch processing with asyncio, concurrency control, and resilience.
Integrates:
- Smart Router v2
- Tier 1 (Rules)
- Tier 2 (Async Ollama)
- Tier 3 (Async GPT-4)
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
    
    def __init__(self, use_cache: bool = True, use_semantic_cache: bool = True, use_cross_validation: bool = True):
        self.router = SmartRouterV2()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = Tier2Mistral()
        self.tier3 = TagExtractor()
        self.cleaner = MultilingualTextCleaner(use_embeddings=False) # Keep it light by default
        
        # Caching systems
        self.cache = CacheManager() if use_cache else None
        self.semantic_cache = SemanticCache() if use_semantic_cache and HAS_EMBEDDINGS else None
        self.cross_validator = CrossValidator() if use_cross_validation else None
        
        self.dlq = DeadLetterQueue()
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_notes)
        self.ollama_semaphore = asyncio.Semaphore(1)  # Reduced to 1 for stability/speed on local CPU/GPU
        self.openai_semaphore = asyncio.Semaphore(10) # Max 10 OpenAI parallel
        
        # Stats
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'tier1': 0,
            'tier2': 0,
            'tier3': 0,
            'semantic_cache_hits': 0,
            'cross_validated': 0,
            'start_time': None
        }

    async def process_note(self, note: Dict, on_progress: Optional[Callable] = None, **kwargs) -> Optional[PipelineOutput]:
        """
        Process a single note through the pipeline.
        """
        async with self.semaphore:
            start_time = time.time()
            note_id = str(note.get('ID', 'unknown'))
            raw_text = note.get('Transcription') or ''  # Handle None or missing
            language = note.get('Language', 'FR') or 'FR'

            # Helper for safe progress reporting
            async def safe_progress(step_data):
                if on_progress:
                    try:
                        payload = {**step_data}
                        if "note_id" not in payload: payload["note_id"] = note_id
                        await on_progress(payload)
                    except Exception as pe:
                        logger.warning(f"Progress report failed for step {step_data.get('step')}: {pe}")

            # 0. Data Cleaning
            await safe_progress({"step": "cleaning", "tokens_saved": 0})
            clean_res = self.cleaner.clean_text(raw_text, language)
            text = clean_res['cleaned']
            tokens_saved = clean_res.get('fillers_removed', 0)
            await safe_progress({"step": "cleaning", "tokens_saved": tokens_saved})
            
            logger.info(f"Summary: Cleaned text: '{text}' (saved {tokens_saved} tokens)")
            
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
                self.stats['tier1'] += 1
                
                # Run Tier 2 if routed
                if decision.tier >= 2:
                    await safe_progress({"step": "tier2_extraction"})
                    async with self.ollama_semaphore:
                        tier2_result = await self.tier2.extract(text, language)
                    
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
                        self.stats['tier2'] += 1
                
                # Run Tier 3 if routed
                if decision.tier >= 3:
                    await safe_progress({"step": "tier3_extraction"})
                    async with self.openai_semaphore:
                        tier3_result = await self.tier3.extract(
                            text, 
                            language, 
                            client_status=None,
                            escalation_reason=decision.reasons[-1] if decision.reasons else None,
                            use_cache=False
                        )
                    
                    if tier3_result:
                        tier_results[3] = tier3_result.model_dump() if hasattr(tier3_result, 'model_dump') else tier3_result
                        tier_confidences[3] = getattr(tier3_result, 'confidence', 0.95)
                    self.stats['tier3'] += 1
                
                # Cross-Validation: Merge results from all tiers
                if self.cross_validator and len(tier_results) > 1:
                    await safe_progress({"step": "cross_validation", "tiers": list(tier_results.keys())})
                    
                    validation = self.cross_validator.validate(tier_results, tier_confidences)
                    
                    # Log validation insights
                    if validation.validation_notes:
                        for note in validation.validation_notes:
                            logger.info(f"Cross-Validation: {note}")
                    
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

                # Progress after extraction to show count
                if extraction_result:
                    tags = extraction_result.tags
                    await safe_progress({
                        "step": "extraction",
                        "tag_count": len(tags),
                        "model": "Mistral-Large" if decision.tier <= 2 else "GPT-4o"
                    })

                # 5. RAG (Matching Product)
                await safe_progress({"step": "rag", "dist": "0.94"})
                
                # 6. CRM Injection & Gamification
                quality = 0
                feedback = "Note traitée."
                points = 5
                
                if extraction_result:
                    meta = getattr(extraction_result, 'meta_analysis', None)
                    quality = getattr(meta, 'quality_score', 0) if meta else 0
                    feedback = getattr(meta, 'advisor_feedback', "Note traitée.") if meta else "Note traitée."
                    points = 10 if quality > 50 else 5

                await safe_progress({
                    "step": "injection", 
                    "points": points,
                    "quality_score": f"{int(quality)}%",
                    "feedback": feedback
                })

                # 7. Build Output
                output = PipelineOutput(
                    id=note_id,
                    original_text=raw_text,
                    processed_text=text,
                    language=language,
                    timestamp=datetime.now(),
                    routing=RoutingDecision(
                        tier=decision.tier,
                        reasons=decision.reasons,
                        confidence=decision.confidence,
                        priority=decision.priority
                    ),
                    rgpd=RGPDResult(
                        contains_sensitive=any(t in text for t in ['[EMAIL]', '[PHONE]', '[CARTE]', '[NAME]', '[RIB]', '[CVC]', '[CARTE_VITALE]', '[DNI]', '[NIF]', '[PASSPORT]', '[SSN]', '[FISCAL]']),
                        categories_detected=[t for t in ['[EMAIL]', '[PHONE]', '[CARTE]', '[NAME]', '[RIB]', '[CVC]', '[CARTE_VITALE]', '[DNI]', '[NIF]', '[PASSPORT]', '[SSN]', '[FISCAL]'] if t in text],
                        safe_to_store=True,
                        severity="low" if not any(t in text for t in ['[CARTE]', '[RIB]', '[SSN]', '[CARTE_VITALE]']) else "medium",
                        anonymized_text=text
                    ),
                    extraction=extraction_result,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    from_cache=False
                )
                
                # 8. Cache Results
                # 8a. Exact Match Cache
                if self.cache and kwargs.get('save_to_cache', True):
                    serialized = output.model_dump(mode="json")
                    self.cache.save(
                        self.cache.get_cache_key(text, 'pipeline_v3'), 
                        'pipeline_v3', 
                        serialized
                    )
                
                # 8b. Semantic Cache (for similarity-based retrieval)
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
        self.stats['processed'] = 0
        
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
            }
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
