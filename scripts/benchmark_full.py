"""
Full Benchmark Script
Tests AsyncPipeline performance with configurable datasets.

Usage:
    python scripts/benchmark_full.py                          # Default paths
    python scripts/benchmark_full.py --no-cache               # Disable cache
    python scripts/benchmark_full.py -i data/custom.csv      # Custom input
    python scripts/benchmark_full.py -o outputs/bench.json    # Custom output
"""

import asyncio
import argparse
import sys
import os
import pandas as pd
import time
import json
from pathlib import Path

sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline


def parse_args():
    parser = argparse.ArgumentParser(description='Run full pipeline benchmark')
    parser.add_argument('-i', '--input', nargs='+', 
                       default=['data/raw/LVMH_Notes_CA101-400.csv', 'LVMH_Realistic_Merged_CA001-100.csv'],
                       help='Input CSV files (space-separated)')
    parser.add_argument('-o', '--output', default='outputs/benchmark_results.json',
                       help='Output JSON file')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    parser.add_argument('--limit', type=int, help='Limit total notes processed')
    return parser.parse_args()


def load_csv_files(file_paths):
    """Load and merge multiple CSV files."""
    all_notes = []
    
    for path in file_paths:
        if not os.path.exists(path):
            print(f"⚠️  File not found: {path}, skipping")
            continue
        
        print(f"📂 Loading: {path}")
        df = pd.read_csv(path)
        
        required_cols = ['ID', 'Transcription', 'Language']
        if 'Transcription' not in df.columns:
            df['Transcription'] = df.iloc[:, 0]
        if 'Language' not in df.columns:
            df['Language'] = 'fr'
        if 'ID' not in df.columns:
            df['ID'] = [f"NOTE_{i}" for i in range(len(df))]
        
        notes = df[required_cols].to_dict('records')
        all_notes.extend(notes)
        print(f"   Loaded {len(notes)} notes")
    
    return all_notes


async def run_benchmark():
    args = parse_args()
    
    print("="*60)
    print("🚀 FULL PIPELINE BENCHMARK")
    print("="*60)
    print(f"Cache: {'Disabled' if args.no_cache else 'Enabled'}")
    print(f"Output: {args.output}")
    
    notes = load_csv_files(args.input)
    
    if args.limit:
        notes = notes[:args.limit]
    
    print(f"\n📊 Total notes to process: {len(notes)}")
    
    pipeline = AsyncPipeline(use_cache=not args.no_cache)
    
    start_time = time.time()
    results = await pipeline.process_batch(notes)
    total_time = time.time() - start_time
    
    success_count = len(results)
    failed_count = len(notes) - success_count
    
    tier_counts = {1: 0, 2: 0, 3: 0}
    total_cost = 0.0
    total_confidence = 0.0
    
    for res in results:
        tier = res.routing.tier
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total_confidence += res.extraction.confidence
        total_cost += res.extraction.cost
    
    avg_confidence = total_confidence / success_count if success_count > 0 else 0
    speed = success_count / total_time if total_time > 0 else 0
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'config': {
            'input_files': args.input,
            'cache_enabled': not args.no_cache,
            'limit': args.limit
        },
        'metrics': {
            'total_notes': len(notes),
            'successful': success_count,
            'failed': failed_count,
            'time_seconds': round(total_time, 2),
            'notes_per_second': round(speed, 2),
            'seconds_per_note': round(total_time / len(notes), 3) if notes else 0,
            'total_cost_eur': round(total_cost, 4),
            'avg_confidence': round(avg_confidence, 3)
        },
        'tier_distribution': {
            'tier_1': {'count': tier_counts.get(1, 0), 'pct': round(tier_counts.get(1, 0) / success_count * 100, 1) if success_count else 0},
            'tier_2': {'count': tier_counts.get(2, 0), 'pct': round(tier_counts.get(2, 0) / success_count * 100, 1) if success_count else 0},
            'tier_3': {'count': tier_counts.get(3, 0), 'pct': round(tier_counts.get(3, 0) / success_count * 100, 1) if success_count else 0},
        }
    }
    
    print("\n" + "="*60)
    print("🏁 BENCHMARK RESULTS")
    print("="*60)
    print(f"Total Notes:      {len(notes)}")
    print(f"Successful:       {success_count}")
    print(f"Failed:           {failed_count}")
    print(f"Time Taken:       {total_time:.2f}s")
    print(f"Speed:            {speed:.2f} notes/sec")
    print("-" * 50)
    print(f"💰 Total Cost:     {total_cost:.4f}€")
    print(f"🎯 Avg Confidence: {avg_confidence:.1%}")
    print("-" * 50)
    print("📊 Tier Distribution:")
    print(f"   Tier 1 (Rules):  {tier_counts.get(1, 0)} ({tier_counts.get(1, 0)/success_count:.1%})")
    print(f"   Tier 2 (Ollama): {tier_counts.get(2, 0)} ({tier_counts.get(2, 0)/success_count:.1%})")
    print(f"   Tier 3 (GPT-4):  {tier_counts.get(3, 0)} ({tier_counts.get(3, 0)/success_count:.1%})")
    print("="*60)
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Report saved to: {args.output}")
    
    return report


if __name__ == "__main__":
    asyncio.run(run_benchmark())
