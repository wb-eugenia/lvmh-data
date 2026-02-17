
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

async def run_full_batch(num_notes=400):
    # Clear cache usually? Maybe NOT for 400 notes to save money/time if re-running.
    # But for a clean Generalization run, let's clear it.
    if os.path.exists('cache/pipeline_batch'):
        # shutil.rmtree('cache/pipeline_batch') # Keep cache for speed if partial
        print("ℹ️  Cache pipeline préservé pour vitesse")
        
    print(f"{'='*60}")
    print(f"🚀 FULL BATCH RUN: {num_notes} NOTES")
    print(f"{'='*60}")

    # 1. Load Data
    csv_path = "data/raw/LVMH_Notes_CA101-400.csv"
    if not os.path.exists(csv_path):
        # Fallback to cleaned if raw not found
        csv_path = "data/LVMH_Notes_CA101-400_cleaned.csv"
        
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

    # Full set
    # Limit to num_notes if specified, else all
    if num_notes:
        sample_notes = df.head(num_notes).to_dict('records')
    else:
        sample_notes = df.to_dict('records')
    
    # Add IDs
    for i, note in enumerate(sample_notes):
        if 'ID' not in note: note['ID'] = f"CA_{101+i}" # Align with dataset ID convention
        if 'Language' not in note: note['Language'] = 'fr'

    # 2. Run Pipeline
    print(f"\n⚙️  Processing {len(sample_notes)} notes...")
    start_time = time.time()
    
    pipeline = PipelineBatchV2(use_cache=True, use_bq=False)
    results = await pipeline.process_batch_async(sample_notes)
    
    total_time = time.time() - start_time
    print(f"\n✅ Terminé en {total_time:.2f}s ({total_time/len(sample_notes):.2f}s/note)")

    # 3. Save Output
    os.makedirs('outputs', exist_ok=True)
    out_file = 'outputs/batch_run_400.json'
    
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
    asyncio.run(run_full_batch(400))
