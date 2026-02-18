"""
Test local with detailed scoring - CA101-400
"""
import csv
import os
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

sys.path.append(os.getcwd())

from src.smart_router import SmartRouterV3

router = SmartRouterV3()

# Read CA101-400
with open("atester/LVMH_Notes_CA101-400 (2).csv", 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)[:50]

print("=== Test routing CA101-400 (50 notes) ===\n")

for i, row in enumerate(rows):
    text = row.get('Transcription', '')[:150]
    result = router.route(text)
    
    print(f"Note {i+1}: Score={result.score.total:.1f} -> Tier {result.tier}")
    if result.reasons:
        print(f"   Reasons: {result.reasons[0]}")
    print()

stats = router.get_stats()
print(f"\n=== Stats router ===")
print(f"Tier 1: {stats['tier1_pct']:.1f}%")
print(f"Tier 2: {stats['tier2_pct']:.1f}%")
print(f"Tier 3: {stats['tier3_pct']:.1f}%")