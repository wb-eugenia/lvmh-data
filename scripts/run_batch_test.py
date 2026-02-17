
import asyncio
import pandas as pd
import json
import os
import sys
import time
import shutil
from collections import Counter

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline_batch_v2 import PipelineBatchV2

async def run_test(num_notes=50):
    # Clear cache just in case
    if os.path.exists('cache/pipeline_batch'):
        shutil.rmtree('cache/pipeline_batch')
        print("🧹 Cache pipeline nettoyé")
        
    print(f"{'='*60}")
    print(f"🚀 BATCH TEST: {num_notes} NOTES")
    print(f"{'='*60}")

    # 1. Load Data
    csv_path = "data/raw/LVMH_Notes_CA101-400.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Fichier non trouvé: {csv_path}")
        return

    print("Unknown separator, attempting regex or default engine...")
    try:
        df = pd.read_csv(csv_path, sep=None, engine='python') # Auto-detect separator
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Rename columns if needed to match pipeline expectations
    # Pipeline expects: 'Transcription', 'Language' (optional), 'ID' (optional)
    # Check what columns we have
    print(f"Columns found: {list(df.columns)}")
    
    # Normalize columns
    col_map = {
        'Note': 'Transcription',
        'text': 'Transcription',
        'Note_Text': 'Transcription'
    }
    df = df.rename(columns=col_map)
    
    if 'Transcription' not in df.columns:
        # Fallback: assume 1st column is text
        print("⚠️ Colonne 'Transcription' non trouvée, utilisation de la 1ère colonne.")
        df['Transcription'] = df.iloc[:, 0]

    # Sample
    sample_notes = df.head(num_notes).to_dict('records')
    
    # Add fake IDs if missing
    for i, note in enumerate(sample_notes):
        if 'ID' not in note: note['ID'] = f"TEST-{i+1:03d}"
        if 'Language' not in note: note['Language'] = 'fr' # Force FR default

    # 2. Run Pipeline
    print(f"\n⚙️  Processing {len(sample_notes)} notes...")
    start_time = time.time()
    
    pipeline = PipelineBatchV2(use_cache=True, use_bq=False)
    results = await pipeline.process_batch_async(sample_notes)
    
    total_time = time.time() - start_time
    print(f"\n✅ Terminé en {total_time:.2f}s ({total_time/len(sample_notes):.2f}s/note)")

    # 3. Analyze Results
    print("\n📊 ANALYSE DES RÉSULTATS :")
    
    tier_counts = Counter(r.get('tier', 'unknown') for r in results)
    print(f"\n🔹 Distribution des Tiers :")
    for tier, count in tier_counts.items():
        print(f"   Tier {tier}: {count} ({count/len(results)*100:.1f}%)")

    # RAG Stats
    rag_hits = sum(1 for r in results if r.get('matched_products'))
    print(f"\n🔹 RAG Performance :")
    print(f"   Matches trouvés : {rag_hits}/{len(results)} ({rag_hits/len(results)*100:.1f}%)")

    # Detailed Inspection (Errors & Empty)
    errors = [r for r in results if r.get('error')]
    if errors:
        print(f"\n❌ Erreurs ({len(errors)}) :")
        for err in errors[:3]: # Show first 3 errors
            print(f"   - {err.get('ID')}: {err.get('error')}")

    # Quality Check (Tier 1 vs Tier 2 richness)
    # On regarde si Tier 1 a réussi à extraire des tags
    t1_empty = 0
    t1_notes = [r for r in results if r.get('tier') == 1]
    for r in t1_notes:
        p1 = r.get('pilier_1_univers_produit', {})
        cats = p1.get('categories', []) if isinstance(p1, dict) else []
        if not cats:
            t1_empty += 1
            
    if t1_notes:
        print(f"\n🔹 Qualité Tier 1 :")
        print(f"   Notes vides (pas de catégories) : {t1_empty}/{len(t1_notes)}")

    # 4. Save Output
    os.makedirs('outputs', exist_ok=True)
    out_file = 'outputs/batch_test_results.json'
    
    # Helper for JSON serialization
    def json_serial(obj):
        if hasattr(obj, 'model_dump'): return obj.model_dump()
        return str(obj)

    with open(out_file, 'w', encoding='utf-8') as f:
        # Convert Pydantic models to dicts in results
        clean_results = []
        for r in results:
            clean_r = r.copy()
            # Flatten extraction if needed or model_dump
            clean_results.append(clean_r)
            
        json.dump(clean_results, f, default=json_serial, indent=2, ensure_ascii=False)
        
    print(f"\n💾 Résultats sauvegardés dans {out_file}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_test(50))
