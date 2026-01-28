
import json
import os
import sys
import pandas as pd
from pathlib import Path
from collections import Counter
import pprint

# Add src to path
sys.path.append(os.getcwd())

from src.cache_manager import CacheManager
from src.models import ExtractionResult

def analyze_results():
    print("🚀 Starting Quality Analysis...\n")
    
    # 1. Load Data
    cache = CacheManager()
    try:
        input_file = 'LVMH_Realistic_Merged_CA001-100.csv'
        if not os.path.exists(input_file):
            input_file = 'data/processed/LVMH_Notes_CA101-400_cleaned.csv'
        
        df = pd.read_csv(input_file).head(100) # Ensure we look at the same 100
        notes = df.to_dict('records')
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    results = []
    missing_cache = 0
    
    # 2. Retrieve from Cache
    for note in notes:
        text = note.get('Transcription') or ''
        key = cache.get_cache_key(text, 'pipeline_v3') # Step used in pipeline_async.py
        
        data = cache.load(key, 'pipeline_v3')
        if data:
            results.append(data)
        else:
            missing_cache += 1
    
    print(f"📊 Found {len(results)} results in cache (Missing: {missing_cache})")
    
    if not results:
        print("❌ No results found. Did you run the pipeline?")
        return

    # 3. Analyze Tiers
    tiers = [r['routing']['tier'] for r in results]
    tier_counts = Counter(tiers)
    
    print("\n📈 Tier Distribution:")
    for t, count in tier_counts.items():
        print(f"   - Tier {t}: {count} ({count/len(results):.1%})")
        
    # 4. Detailed Validation
    print("\n🔍 Deep Dive Analysis:")
    
    tier_samples = {1: [], 2: [], 3: []}
    
    errors = 0
    perfect_notes = 0
    
    for r in results:
        tier = r['routing']['tier']
        try:
            ext = r['extraction']
            if not ext:
                print(f"⚠️ Note {r['id']} has NO EXTRACTION result!")
                errors += 1
                continue
                
            # Check consistency
            tags = ext.get('tags', [])
            budget = ext.get('budget_range')
            
            # Store sample
            if len(tier_samples[tier]) < 3:
                tier_samples[tier].append({
                    'id': r['id'],
                    'text': r['original_text'],
                    'tags': tags,
                    'budget': budget,
                    'status': ext.get('client_status'),
                    'tier': tier,
                    'extracted_by': ext.get('extracted_by')
                })
                
            perfect_notes += 1
            
        except Exception as e:
            print(f"⚠️ Error parsing result for {r.get('id')}: {e}")
            errors += 1

    # 5. Show Samples
    for t in [1, 2, 3]:
        print(f"\n🏷️  TIER {t} SAMPLES:")
        if not tier_samples[t]:
            print("   (None)")
            continue
            
        for s in tier_samples[t]:
            print(f"\n   🆔 {s['id']}")
            print(f"   📝 Text: \"{s['text'][:100]}...\"")
            print(f"   ✅ Tags: {s['tags']}")
            print(f"   💰 Budget: {s['budget']} | Status: {s['status']}")
            print(f"   🤖 By: {s['extracted_by']}")
            print("-" * 40)

    # 6. Global Stats
    print("\n✅ Final Quality Score:")
    print(f"   - Processed: {len(results)}")
    print(f"   - Structure Valid: {perfect_notes}")
    print(f"   - Errors/Empty: {errors}")
    
    print("\n💡 Insights:")
    if tier_counts.get(1, 0) > 30:
        print("   ✅ Good usage of Tier 1 (Free/Fast)")
    else:
        print("   ⚠️ Tier 1 under-utilized? Check rules.")
        
    if tier_counts.get(3, 0) > 40:
        print("   ⚠️ High Tier 3 usage (Expensive). Check if Tier 2 can do more.")

if __name__ == "__main__":
    analyze_results()
