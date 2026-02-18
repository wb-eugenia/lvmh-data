"""
Test local - qualite des resultats
"""
import asyncio
import csv
import os
import sys
from collections import Counter

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline

async def test_quality():
    with open("LVMH_Realistic_Merged_CA001-100.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)[:20]
    
    notes = []
    for row in rows:
        text = row.get('Transcription', '')
        if text:
            notes.append({
                'ID': row.get('ID', ''),
                'Transcription': text,
                'Language': row.get('Language', 'FR')
            })
    
    print(f"=== Test qualite: {len(notes)} notes ===\n")
    
    pipeline = AsyncPipeline(use_cache=False)
    results = await pipeline.process_batch(notes)
    
    tags_extracted = []
    tiers = []
    matched_products = 0
    
    for r in results:
        if r:
            tiers.append(r.routing.tier)
            if r.extraction:
                tags_extracted.extend(r.extraction.tags)
            
            if hasattr(r, 'products') and r.products:
                matched_products += 1
    
    print(f"Tiers: {Counter(tiers)}")
    
    print(f"\nTags extraits: {len(tags_extracted)}")
    print(f"\nTop tags:")
    tag_counts = Counter(tags_extracted)
    for tag, count in tag_counts.most_common(10):
        print(f"   {tag}: {count}")
    
    print(f"\nProduits matches (RAG): {matched_products}/{len(results)}")
    
    print(f"\n=== Exemples ===")
    for r in results[:3]:
        if r:
            print(f"ID: {r.id}")
            print(f"   Tier: {r.routing.tier}")
            print(f"   Tags: {r.extraction.tags if r.extraction else []}")
            print(f"   Confidence: {r.routing.confidence:.2f}")
            print()

asyncio.run(test_quality())
