import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.taxonomy import TaxonomyManager
from src.models import ExtractionResult
from src.smart_router import SmartRouterV2
from src.tier1_rules import Tier1RulesEngine
from src.pipeline_async import AsyncPipeline

async def test_architecture():
    print("🧪 Testing Architecture Refactoring...\n")
    
    # 1. Test Taxonomy
    print("1. Testing TaxonomyManager...")
    taxonomy = TaxonomyManager()
    tags = taxonomy.get_core_tags()
    print(f"   ✅ Loaded {len(tags)} core tags.")
    print(f"   ✅ 'capucines' valid? {taxonomy.validate_tag('capucines')}")
    print(f"   ✅ 'invalid_tag' valid? {taxonomy.validate_tag('invalid_tag')}")
    
    # 2. Test Validation Layer
    print("\n2. Testing Validation Layer...")
    try:
        res = ExtractionResult(
            tags=['capucines', 'leather_goods'],
            processing_tier='tier1',
            confidence=0.9,
            extracted_by='test'
        )
        print("   ✅ Valid result created.")
    except Exception as e:
        print(f"   ❌ Valid result failed: {e}")
        
    try:
        res = ExtractionResult(
            tags=['invalid_tag_123'],
            processing_tier='tier1',
            confidence=0.9,
            extracted_by='test'
        )
        print("   ❌ Invalid result SHOULD have failed but didn't.")
    except ValueError as e:
        print(f"   ✅ Invalid result caught correctly: {e}")
    except Exception as e:
        print(f"   ⚠️ Unexpected error: {e}")

    # 3. Test Smart Router V2
    print("\n3. Testing SmartRouterV2...")
    router = SmartRouterV2()
    
    # Simple
    decision = router.route("Je cherche un sac Capucines budget 5000€")
    print(f"   Simple Note -> Tier {decision.tier} ({decision.reasons[0]})")
    
    # Complex
    decision = router.route("Client VIC très important, plainte sur la qualité.")
    print(f"   Complex Note -> Tier {decision.tier} ({decision.reasons[0]})")
    
    # RGPD Critical
    decision = router.route("Client en dépression suite à un divorce difficile.")
    print(f"   RGPD Note -> Tier {decision.tier} ({decision.reasons[0]})")
    
    # 4. Test Tier 1 Engine
    print("\n4. Testing Tier 1 Engine...")
    engine = Tier1RulesEngine()
    res = engine.extract("Mme Martin cherche un sac Capucines. Budget 6K€.")
    print(f"   Extracted: {res.tags}")
    print(f"   Budget: {res.budget_range}")
    print(f"   Tier: {res.processing_tier}")
    
    print("\n✅ Verification Complete!")

if __name__ == "__main__":
    asyncio.run(test_architecture())
