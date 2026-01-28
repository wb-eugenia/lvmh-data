import asyncio
import sys
import os
import pandas as pd
import time
import json

# Add project root to path
sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline
from config.production import settings

async def run_benchmark():
    print("🚀 Starting Full Benchmark (100 + 300 notes)...")
    
    # 1. Load Data
    try:
        df_100 = pd.read_csv('LVMH_Realistic_Merged_CA001-100.csv')
        df_300 = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
        
        # Ensure columns exist
        required_cols = ['ID', 'Transcription', 'Language']
        
        # Standardize columns if needed
        # (Assuming they are correct based on checks)
        
        notes_100 = df_100[required_cols].to_dict('records')
        notes_300 = df_300[required_cols].to_dict('records')
        
        all_notes = notes_100 + notes_300
        print(f"📊 Loaded {len(notes_100)} + {len(notes_300)} = {len(all_notes)} notes.")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    # 2. Initialize Pipeline
    # We disable cache to test real processing speed
    pipeline = AsyncPipeline(use_cache=False)
    
    # 3. Run Processing
    start_time = time.time()
    results = await pipeline.process_batch(all_notes)
    total_time = time.time() - start_time
    
    # 4. Calculate Metrics
    success_count = len(results)
    failed_count = len(all_notes) - success_count
    
    tier_counts = {1: 0, 2: 0, 3: 0}
    total_cost = 0.0
    total_confidence = 0.0
    
    # Tier 3 Cost Estimate (approx $0.15 / 1M tokens input, $0.60 / 1M tokens output for gpt-4o-mini)
    # Let's use the cost field from ExtractionResult if available, or estimate
    # The models.py has a cost field.
    
    for res in results:
        tier = res.routing.tier
        tier_counts[tier] += 1
        total_confidence += res.extraction.confidence
        total_cost += res.extraction.cost
        
    avg_confidence = total_confidence / success_count if success_count > 0 else 0
    speed = success_count / total_time if total_time > 0 else 0
    
    # 5. Report
    print("\n" + "="*50)
    print("🏁 BENCHMARK RESULTS")
    print("="*50)
    print(f"Total Notes:      {len(all_notes)}")
    print(f"Successful:       {success_count}")
    print(f"Failed:           {failed_count}")
    print(f"Time Taken:       {total_time:.2f}s")
    print(f"Speed:            {speed:.2f} notes/sec")
    print("-" * 50)
    print(f"💰 Total Cost:     {total_cost:.4f}€")
    print(f"🎯 Avg Confidence: {avg_confidence:.1%}")
    print("-" * 50)
    print("📊 Tier Distribution:")
    print(f"   Tier 1 (Rules):  {tier_counts[1]} ({tier_counts[1]/success_count:.1%}) - 0€")
    print(f"   Tier 2 (Ollama): {tier_counts[2]} ({tier_counts[2]/success_count:.1%}) - 0€")
    print(f"   Tier 3 (GPT-4):  {tier_counts[3]} ({tier_counts[3]/success_count:.1%}) - $$$")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
