"""
Integration tests for Production Hardening (Phase 7).
Verifies Async Pipeline, Error Handling, Caching, and DLQ.
"""

import asyncio
import json
import os
import sys
import pytest
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline
from src.models import PipelineOutput
from config.production import settings


def _integration_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_pipeline():
    if not _integration_enabled():
        pytest.skip("Integration tests disabled. Set RUN_INTEGRATION_TESTS=1.")
    missing = []
    if not os.getenv("MISTRAL_API_KEY"):
        missing.append("MISTRAL_API_KEY")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if missing:
        pytest.skip(f"Missing API keys: {', '.join(missing)}")
    print("🚀 TESTING ASYNC PIPELINE (PRODUCTION MODE)\n")
    
    # Initialize Pipeline
    pipeline = AsyncPipeline(use_cache=True)
    
    # Clear cache for fresh test
    if pipeline.cache:
        pipeline.cache.stats = {'hits': 0, 'misses': 0}
    
    # Test Data (Mix of simple, complex, and error-prone)
    test_notes = [
        {"ID": "TEST_001", "Transcription": "Budget 5000€. Cherche sac noir.", "Language": "FR"}, # Tier 1
        {"ID": "TEST_002", "Transcription": "Client VIC, allergie mortelle arachide. Cadeau femme.", "Language": "FR"}, # Tier 2 -> Tier 3 (Safety)
        {"ID": "TEST_003", "Transcription": "Je cherche un cadeau pour mon mari.", "Language": "FR"}, # Tier 2
        {"ID": "TEST_004", "Transcription": "Budget 5000€. Cherche sac noir.", "Language": "FR"}, # Cache Hit (Duplicate of 001)
    ]
    
    print(f"📦 Processing {len(test_notes)} notes concurrently...")
    
    results = await pipeline.process_batch(test_notes)
    
    print(f"\n✅ Processed {len(results)} notes.\n")
    
    # Verify Results
    for res in results:
        print(f"📝 Note {res.id}:")
        print(f"   Tier: {res.routing.tier}")
        print(f"   Confidence: {res.routing.confidence:.2f}")
        print(f"   Time: {res.processing_time_ms:.1f}ms")
        print(f"   Tags: {res.extraction.tags}")
        if res.rgpd.contains_sensitive:
            print(f"   🛡️ RGPD Sensitive: {res.rgpd.categories_detected}")
        print()

    # Verify Caching
    print("🔍 CACHE VERIFICATION")
    if pipeline.cache:
        print(f"   Hits: {pipeline.cache.stats['hits']}")
        print(f"   Misses: {pipeline.cache.stats['misses']}")
        if pipeline.cache.stats['hits'] >= 1:
            print("   ✅ Cache working (Hit found)")
        else:
            print("   ⚠️ Cache might not be working (No hits)")
    
    # Verify DLQ (Simulate Error)
    print("\n💀 DLQ VERIFICATION (Simulating Error)")
    bad_note = {"ID": "BAD_001", "Transcription": None, "Language": "FR"} # Will cause error
    
    res = await pipeline.process_note(bad_note)
    
    if res is None:
        print("   ✅ Bad note correctly failed (returned None)")
        if pipeline.dlq.size() > 0:
            print(f"   ✅ DLQ caught the error. Size: {pipeline.dlq.size()}")
            print(f"   📄 Exported DLQ: {pipeline.dlq.export_csv()}")
        else:
            print("   ❌ DLQ failed to catch error")
    else:
        print("   ❌ Bad note unexpectedly succeeded")

if __name__ == "__main__":
    asyncio.run(test_async_pipeline())
