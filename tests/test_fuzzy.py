import sys
import os
sys.path.append(os.getcwd())

from src.taxonomy import TaxonomyManager
from src.models import ExtractionResult

def test_fuzzy_matching():
    print("🧪 Testing Fuzzy Matching & Normalization...\n")
    
    taxonomy = TaxonomyManager()
    
    # Test cases
    cases = [
        ("tech_entrepreneur", "entrepreneur_tech"),  # Alias
        ("fashion_designer", "designer"),            # Alias
        ("leather_good", "leather_goods"),           # Fuzzy (singular)
        ("capucine", "capucines"),                   # Fuzzy (typo)
        ("unknown_tag_xyz", None),                   # Invalid
    ]
    
    print("1. Testing TaxonomyManager.normalize_tag:")
    for input_tag, expected in cases:
        result = taxonomy.normalize_tag(input_tag)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{input_tag}' -> '{result}' (Expected: '{expected}')")

    print("\n2. Testing ExtractionResult Validation:")
    try:
        res = ExtractionResult(
            tags=['tech_entrepreneur', 'capucine'], # Should be normalized
            processing_tier='tier2',
            confidence=0.9,
            extracted_by='test'
        )
        print(f"   ✅ Created successfully. Tags: {res.tags}")
        if 'entrepreneur_tech' in res.tags and 'capucines' in res.tags:
            print("   ✅ Normalization applied correctly in model.")
        else:
            print("   ❌ Normalization FAILED in model.")
            
    except Exception as e:
        print(f"   ❌ Creation failed: {e}")

    try:
        res = ExtractionResult(
            tags=['completely_invalid_tag'],
            processing_tier='tier2',
            confidence=0.9,
            extracted_by='test'
        )
        print("   ❌ Invalid tag was NOT caught.")
    except ValueError as e:
        print(f"   ✅ Invalid tag caught correctly: {e}")

if __name__ == "__main__":
    test_fuzzy_matching()
