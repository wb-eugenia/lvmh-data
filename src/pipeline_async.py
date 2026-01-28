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
from typing import List, Dict, Optional

# Add project root to path to allow imports from config
sys.path.append(os.getcwd())

import pandas as pd
from tqdm.asyncio import tqdm

from config.production import settings
from src.models import PipelineOutput, RoutingDecision, ExtractionResult, RGPDResult
from src.smart_router import SmartRouterV2
from src.tier1_rules import Tier1RulesEngine
from src.tier1_rules import Tier1RulesEngine
from src.tier2_groq import Tier2Groq
from src.extractor import TagExtractor
from src.rgpd_ollama import RGPDOllamaFilter
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
        self.router = SmartRouterV2()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = Tier2Groq()
        self.tier3 = TagExtractor() # Tier 3 is sync but we wrap it or use async client if available (using sync for now in thread)
        self.rgpd = RGPDOllamaFilter()
        
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

    async def process_note(self, note: Dict) -> Optional[PipelineOutput]:
        """
        Process a single note through the pipeline.
        """
        async with self.semaphore:
            start_time = time.time()
            note_id = str(note.get('ID', 'unknown'))
            text = note.get('Transcription') or ''  # Handle None or missing
            language = note.get('Language', 'FR') or 'FR'
            
            try:
                # 1. Check Cache
                if self.cache:
                    cached_data = self.cache.load(self.cache.get_cache_key(text, 'pipeline_v3'), 'pipeline_v3')
                    if cached_data:
                        # Reconstruct PipelineOutput from dict
                        return PipelineOutput(**cached_data)

                # 2. RGPD Check (Async wrap)
                loop = asyncio.get_event_loop()
                rgpd_result = await loop.run_in_executor(
                    None, 
                    lambda: self.rgpd.detect(text, language)
                )
                
                # 3. Routing
                decision = self.router.route(text, language, note)
                
                # Force Tier 3 if RGPD sensitive
                if rgpd_result.contains_sensitive:
                    if decision.tier < 3:
                        decision.tier = 3
                        decision.reasons.insert(0, f"RGPD Sensitive: {rgpd_result.categories_detected}")
                
                # 4. Extraction
                extraction_result = None
                
                if decision.tier == 1:
                    extraction_result = self.tier1.extract(text, language)
                    self.stats['tier1'] += 1
                    
                elif decision.tier == 2:
                    async with self.ollama_semaphore:
                        extraction_result = await self.tier2.extract(text, language)
                    
                    # Safety Fallback
                    if extraction_result.allergy_severity == 'high' or \
                       (extraction_result.client_status in ['vic', 'ultimate'] and extraction_result.confidence < 0.9):
                        
                        logger.info(f"⚠️ Escalating Note {note_id} to Tier 3")
                        decision.tier = 3
                        decision.reasons.append("Escalated from Tier 2 (Safety)")
                        # Fallthrough to Tier 3
                        extraction_result = None
                    else:
                        self.stats['tier2'] += 1
                
                if decision.tier == 3 or extraction_result is None:
                    # Run Tier 3 (Sync in thread pool) with Semaphore
                    async with self.openai_semaphore:
                        loop = asyncio.get_event_loop()
                        extraction_result = await loop.run_in_executor(
                            None, 
                            lambda: self.tier3.extract(text, language, client_id=note_id, use_cache=False)
                        )
                    self.stats['tier3'] += 1

                # 5. Build Output
                output = PipelineOutput(
                    id=note_id,
                    original_text=text,
                    processed_text=rgpd_result.anonymized_text or text,
                    language=language,
                    timestamp=datetime.now(),
                    routing=RoutingDecision(
                        tier=decision.tier,
                        reasons=decision.reasons,
                        confidence=decision.confidence,
                        priority=decision.priority
                    ),
                    rgpd=RGPDResult(
                        contains_sensitive=rgpd_result.contains_sensitive,
                        categories_detected=rgpd_result.categories_detected,
                        safe_to_store=rgpd_result.safe_to_store,
                        severity=rgpd_result.severity,
                        reasoning=rgpd_result.reasoning,
                        anonymized_text=rgpd_result.anonymized_text
                    ),
                    extraction=extraction_result,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    from_cache=False
                )
                
                # 6. Cache Result
                if self.cache:
                    # Use json() to handle datetime serialization, then load back to dict
                    serialized = json.loads(output.json())
                    self.cache.save(
                        self.cache.get_cache_key(text, 'pipeline_v3'), 
                        'pipeline_v3', 
                        serialized
                    )
                
                self.stats['success'] += 1
                return output

            except Exception as e:
                self.stats['failed'] += 1
                logger.error(f"Pipeline error for note {note_id}: {e}")
                
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
