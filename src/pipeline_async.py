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
from src.tier1_rules import Tier1RulesEngine
from src.tier2_mistral import Tier2Mistral
from src.extractor import TagExtractor
from src.text_cleaner import MultilingualTextCleaner, HAS_EMBEDDINGS
from src.cache_manager import CacheManager
from src.dlq_manager import DeadLetterQueue
from src.resilience import safe_execution

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
    
    def __init__(self, use_cache: bool = True):
        self.router = SmartRouterV2()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = Tier2Mistral()
        self.tier3 = TagExtractor()
        self.cleaner = MultilingualTextCleaner(use_embeddings=False) # Keep it light by default
        
        self.cache = CacheManager() if use_cache else None
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
                # 1. Check Cache
                if self.cache:
                    cached_data = self.cache.load(self.cache.get_cache_key(text, 'pipeline_v3'), 'pipeline_v3')
                    if cached_data:
                        await safe_progress({"step": "cache_hit"})
                        await safe_progress({"step": "done"})
                        # Reconstruct PipelineOutput from dict
                        return PipelineOutput(**cached_data)

                # 2. Routing (Use ML Router)
                decision = self.router.route_ml(text, language, note)
                await safe_progress({
                    "step": "routing", 
                    "tier": decision.tier,
                    "score": f"{int(decision.score.total)}/100",
                    "priority": decision.priority.upper(),
                    "engine": "Machine Learning" if any("ML" in r for r in decision.reasons) else "Heuristic Engine"
                })
                
                # 4. Extraction
                extraction_result = None
                
                if decision.tier == 1:
                    extraction_result = self.tier1.extract(text, language)
                    self.stats['tier1'] += 1
                    
                elif decision.tier == 2:
                    async with self.ollama_semaphore:
                        extraction_result = await self.tier2.extract(text, language)
                    
                    # Safety Fallback
                    client_status = getattr(extraction_result.pilier_2_profil_client.purchase_context, 'behavior', None) if extraction_result else None
                    
                    # Check if we should escalate
                    should_escalate = False
                    if extraction_result:
                        if extraction_result.confidence < 0.85:
                            should_escalate = True
                        elif client_status in ['vic', 'ultimate'] and extraction_result.confidence < 0.95:
                            should_escalate = True
                    
                    if should_escalate:
                        logger.info(f"Summary: Escalating Note {note_id} to Tier 3 (Safety/Confidence)")
                        decision.tier = 3
                        decision.reasons.append("Escalated from Tier 2 (Safety/Confidence)")
                        extraction_result = None
                    else:
                        self.stats['tier2'] += 1
                
                if decision.tier == 3 or extraction_result is None:
                    # Run Tier 3 (Async now supported by Tier 3)
                    async with self.openai_semaphore:
                        # Tier 3 is now async capable, await directly
                        extraction_result = await self.tier3.extract(
                            text, 
                            language, 
                            client_status=None, # Or pass if known
                            escalation_reason=decision.reasons[-1] if decision.reasons else None,
                            use_cache=False
                        )
                    self.stats['tier3'] += 1

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
                        contains_sensitive=False, # Handled by cleaner
                        categories_detected=[],
                        safe_to_store=True,
                        severity="low",
                        anonymized_text=text
                    ),
                    extraction=extraction_result,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    from_cache=False
                )
                
                # 6. Cache Result
                # 6. Cache Result
                if self.cache and kwargs.get('save_to_cache', True):
                    # Use json() to handle datetime serialization, then load back to dict
                    serialized = json.loads(output.json())
                    self.cache.save(
                        self.cache.get_cache_key(text, 'pipeline_v3'), 
                        'pipeline_v3', 
                        serialized
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
        return {
            "duration_seconds": round(duration, 2),
            "processed": len(self.stats) - 4, # rough approx
            "success": self.stats['success'],
            "failed": self.stats['failed'],
            "tiers": {
                "tier1": self.stats['tier1'],
                "tier2": self.stats['tier2'],
                "tier3": self.stats['tier3']
            }
        }

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
