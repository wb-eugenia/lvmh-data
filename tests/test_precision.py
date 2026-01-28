
import sys
import os
sys.path.append(os.getcwd())

from src.tier1_rules import Tier1RulesEngine
from src.tier2_nlp import Tier2OllamaEngine

def test_precision():
    print("🔬 TESTING PRECISION OPTIMIZATIONS\n")
    
    # --- TIER 1 TESTS ---
    print("1️⃣ Tier 1 (Negative Lookaheads)")
    t1 = Tier1RulesEngine()
    
    negation_cases = [
        ("Je ne veux pas de sac, juste une ceinture.", ["belts"], ["leather_goods"]),
        ("Pas de cuir, je préfère la toile.", ["canvas_preference"], ["leather_preference"]),
        ("Sans gluten mais pas d'allergie.", ["gluten_free"], ["nickel_allergy"]),
    ]
    
    for text, expected, should_not_have in negation_cases:
        res = t1.extract(text)
        print(f"Text: '{text}'")
        print(f"  Found: {res.tags}")
        
        # Verify expected
        missing = [t for t in expected if t not in res.tags]
        if missing:
            print(f"  ❌ Missing expected: {missing}")
        
        # Verify negatives
        bad = [t for t in should_not_have if t in res.tags]
        if bad:
            print(f"  ❌ False positive found: {bad}")
        else:
            print(f"  ✅ No false positives")
        print()

    # --- TIER 2 TESTS ---
    print("2️⃣ Tier 2 (Few-Shot Prompting)")
    try:
        t2 = Tier2OllamaEngine()
        
        complex_case = "Client VIC, cherche cadeau pour sa fille. Budget illimité. Attention allergie mortelle aux arachides."
        print(f"Text: '{complex_case}'")
        
        res = t2.extract(complex_case)
        print(f"  Status: {res.client_status} (Expected: vic)")
        print(f"  Severity: {res.allergy_severity} (Expected: high)")
        print(f"  Reasoning: {res.reasoning}")
        
        if res.client_status == 'vic' and res.allergy_severity == 'high':
            print("  ✅ Few-shot logic working")
        else:
            print("  ❌ Logic failed")
            
    except Exception as e:
        print(f"  ⚠️ Tier 2 skipped: {e}")

if __name__ == "__main__":
    test_precision()
