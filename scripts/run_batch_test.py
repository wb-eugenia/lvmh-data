
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

from src.pipeline_async import AsyncPipeline

async def run_test(num_notes=50):
    print(f"{'='*60}")
    print(f"🚀 BATCH TEST: {num_notes} NOTES")
    print(f"{'='*60}")

    # 1. Load Data
    csv_path = "data/raw/LVMH_Notes_CA101-400.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Fichier non trouvé: {csv_path}")
        return

    print("Reading CSV...")
    try:
        df = pd.read_csv(csv_path, sep=None, engine='python')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(f"Columns found: {list(df.columns)}")
    
    col_map = {
        'Note': 'Transcription',
        'text': 'Transcription',
        'Note_Text': 'Transcription'
    }
    df = df.rename(columns=col_map)
    
    if 'Transcription' not in df.columns:
        print("⚠️ Colonne 'Transcription' non trouvée, utilisation de la 1ère colonne.")
        df['Transcription'] = df.iloc[:, 0]

    # Sample
    sample_notes = df.head(num_notes).to_dict('records')
    
    # Add fake IDs if missing
    for i, note in enumerate(sample_notes):
        if 'ID' not in note: note['ID'] = f"TEST-{i+1:03d}"
        if 'Language' not in note: note['Language'] = 'FR'

    # 2. Run Pipeline
    print(f"\n⚙️  Processing {len(sample_notes)} notes...")
    start_time = time.time()
    
    pipeline = AsyncPipeline(use_cache=True)
    results = await pipeline.process_batch(sample_notes)
    
    total_time = time.time() - start_time
    print(f"\n✅ Terminé en {total_time:.2f}s ({total_time/len(sample_notes):.2f}s/note)")

    # 3. Analyze Results
    print("\n📊 ANALYSE DES RÉSULTATS :")
    
    tier_counts = Counter()
    for r in results:
        if hasattr(r, 'routing') and r.routing:
            tier_counts[r.routing.tier] += 1
        elif hasattr(r, 'tier'):
            tier_counts[r.tier] += 1
    
    print(f"\n🔹 Distribution des Tiers :")
    for tier, count in tier_counts.items():
        print(f"   Tier {tier}: {count} ({count/len(results)*100:.1f}%)")

    # RAG Stats
    rag_hits = sum(1 for r in results if hasattr(r, 'products') and r.products)
    print(f"\n🔹 RAG Performance :")
    print(f"   Matches trouvés : {rag_hits}/{len(results)} ({rag_hits/len(results)*100:.1f}%)")

    # Errors
    errors = [r for r in results if hasattr(r, 'error') and r.error]
    if errors:
        print(f"\n❌ Erreurs ({len(errors)}) :")
        for err in errors[:3]:
            print(f"   - {err.id}: {err.error}")

    # 4. Save Output
    os.makedirs('outputs', exist_ok=True)
    out_file = 'outputs/batch_test_results.json'
    
    def json_serial(obj):
        if hasattr(obj, 'model_dump'): return obj.model_dump()
        return str(obj)

    with open(out_file, 'w', encoding='utf-8') as f:
        clean_results = []
        for r in results:
            clean_results.append(r)
        json.dump(clean_results, f, default=json_serial, indent=2, ensure_ascii=False)
        
    print(f"\n💾 Résultats sauvegardés dans {out_file}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_test(50))
