"""
Test CSV en local avec AsyncPipeline
"""
import asyncio
import csv
import time
import os
import sys
import json

sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline

async def test_csv_local(csv_file, max_notes=100):
    print(f"\n=== Test local: {csv_file} ===")
    
    # Load CSV
    rows = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)[:max_notes]
    
    print(f"Nb notes: {len(rows)}")
    
    # Prepare notes
    notes = []
    for row in rows:
        text = row.get('Transcription', row.get('text', ''))
        if text:
            notes.append({
                'ID': row.get('ID', ''),
                'Transcription': text,
                'Language': row.get('Language', 'FR')
            })
    
    # Run pipeline
    pipeline = AsyncPipeline(use_cache=True)
    
    start_time = time.time()
    results = await pipeline.process_batch(notes)
    elapsed = time.time() - start_time
    
    # Stats
    success = sum(1 for r in results if r is not None)
    errors = len(results) - success
    
    tier_counts = {}
    tag_counts = {}
    for r in results:
        if r:
            tier = r.routing.tier
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            for tag in r.extraction.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    avg_time = sum(r.processing_time_ms for r in results if r) / success if success > 0 else 0
    
    print(f"\n=== Resultats ===")
    print(f"Temps total: {elapsed:.1f}s")
    print(f"Temps/note: {elapsed/len(notes):.2f}s")
    print(f"Temps moyen API: {avg_time:.0f}ms")
    print(f"Reussis: {success}, Erreurs: {errors}")
    print(f"\nDistribution tiers:")
    for tier, count in sorted(tier_counts.items()):
        print(f"   Tier {tier}: {count}")
    
    print(f"\nTop tags:")
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for tag, count in sorted_tags:
        print(f"   {tag}: {count}")
    
    # Save results
    output_data = []
    for r in results:
        if r:
            output_data.append({
                "id": r.id,
                "tier": r.routing.tier,
                "confidence": r.routing.confidence,
                "tags": r.extraction.tags,
                "budget": r.action.budget_specific if hasattr(r.action, 'budget_specific') else None,
                "processing_time_ms": r.processing_time_ms,
            })
    
    output_file = f"output/test_{os.path.basename(csv_file).replace('.csv', '')}.json"
    os.makedirs("output", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nResultats sauvegardes: {output_file}")
    
    return results

async def main():
    csv1 = "LVMH_Realistic_Merged_CA001-100.csv"
    if os.path.exists(csv1):
        await test_csv_local(csv1, 100)

if __name__ == "__main__":
    asyncio.run(main())
