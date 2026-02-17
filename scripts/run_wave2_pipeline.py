"""
Wave 2 Pipeline - Complete orchestration.
Runs: Load → Clean → RGPD → Extract → Export

Usage:
    python scripts/run_wave2_pipeline.py                    # Default
    python scripts/run_wave2_pipeline.py -i data/custom.csv # Custom input
    python scripts/run_wave2_pipeline.py -o outputs/mydir    # Custom output
    python scripts/run_wave2_pipeline.py --no-cache         # Disable cache
    python scripts/run_wave2_pipeline.py --checkpoint 100    # Checkpoint every 100
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.text_cleaner import MultilingualTextCleaner
from src.rgpd_filter import RGPDFilter
from src.cache_manager import CacheManager
from src.cost_tracker import CostTracker
from src.extractor import TagExtractor


def parse_args():
    parser = argparse.ArgumentParser(description='Run Wave 2 Pipeline')
    parser.add_argument('-i', '--input', default='data/raw/LVMH_Notes_CA101-400.csv',
                       help='Input CSV file')
    parser.add_argument('-o', '--output', default='outputs',
                       help='Output directory')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching')
    parser.add_argument('--checkpoint', type=int, default=50,
                       help='Checkpoint interval')
    parser.add_argument('--skip-rgpd', action='store_true',
                       help='Skip RGPD filtering')
    return parser.parse_args()


def run_wave2_pipeline(args):
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path(args.output).mkdir(parents=True, exist_ok=True)
    Path('data/processed').mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        filename='logs/wave2_pipeline.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    start_time = datetime.now()
    print(f"[START] WAVE 2 PIPELINE - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print(f"Input:    {args.input}")
    print(f"Output:   {args.output}")
    print(f"Cache:    {'Disabled' if args.no_cache else 'Enabled'}")
    print(f"Checkpoint every: {args.checkpoint}")
    print("="*60)
    
    cleaner = MultilingualTextCleaner()
    cache = CacheManager('cache/wave2')
    cost_tracker = CostTracker()
    
    if not args.skip_rgpd:
        try:
            rgpd_filter = RGPDFilter()
            print("  [OK] RGPDFilter ready")
        except Exception as e:
            print(f"  [WARN] RGPDFilter failed: {e}, skipping")
            rgpd_filter = None
    else:
        rgpd_filter = None
        print("  [SKIP] RGPD filtering disabled")
    
    try:
        extractor = TagExtractor()
        print("  [OK] TagExtractor ready")
    except Exception as e:
        print(f"  [ERROR] TagExtractor: {e}")
        return
    
    print(f"\n[STEP 1] Loading {args.input}...")
    try:
        df_raw = pd.read_csv(args.input)
        print(f"  [OK] Loaded {len(df_raw)} notes")
        logger.info(f"Loaded {len(df_raw)} notes from {args.input}")
    except FileNotFoundError:
        print(f"  [ERROR] File not found: {args.input}")
        return
    
    print("\n[STEP 2] Cleaning fillers...")
    df_cleaned = cleaner.clean_dataset(df_raw)
    
    cleaned_file = 'data/processed/cleaned_' + Path(args.input).name
    df_cleaned.to_csv(cleaned_file, index=False)
    print(f"  [OK] Saved to {cleaned_file}")
    
    print("\n[STEP 3-4] RGPD + Extraction...")
    results = []
    rgpd_results = []
    
    for idx, row in tqdm(df_cleaned.iterrows(), total=len(df_cleaned), desc="Processing"):
        note_id = row.get('ID', f'note_{idx}')
        cleaned_text = row['Transcription']
        language = row.get('Language', 'fr')
        
        try:
            if rgpd_filter:
                cache_key_rgpd = cache.get_cache_key(cleaned_text, 'rgpd')
                cached_rgpd = cache.load(cache_key_rgpd, 'rgpd') if not args.no_cache else None
                
                if cached_rgpd:
                    rgpd_result = cached_rgpd
                else:
                    note_dict = {'ID': note_id, 'Transcription': cleaned_text, 'Language': language}
                    rgpd_result = rgpd_filter.process_note(note_dict, cost_tracker)
                    cache.save(cache_key_rgpd, 'rgpd', rgpd_result)
                
                rgpd_results.append(rgpd_result)
                text_for_extraction = rgpd_result.get('anonymized_text', cleaned_text)
            else:
                text_for_extraction = cleaned_text
                rgpd_result = {'contains_sensitive': False, 'categories_detected': []}
            
            extraction_result = extractor.extract(
                transcription=text_for_extraction,
                language=language,
                client_id=note_id,
                use_cache=not args.no_cache
            )
            
            combined = {
                'ID': note_id,
                'Date': row.get('Date'),
                'Duration': row.get('Duration'),
                'Language': language,
                'Transcription_original': row.get('Transcription_original'),
                'Transcription_cleaned': cleaned_text,
                'fillers_removed': row.get('fillers_removed'),
                'compression_ratio': row.get('compression_ratio'),
                'tags': extraction_result.get('tags', []),
                'tags_count': len(extraction_result.get('tags', [])),
                'confidence': extraction_result.get('confidence', 0),
                'budget_range': extraction_result.get('budget_range'),
                'client_status': extraction_result.get('client_status'),
                'profession': extraction_result.get('profession'),
                'allergies': extraction_result.get('allergies', []),
                'allergy_severity': extraction_result.get('allergy_severity', {}),
                'dietary': extraction_result.get('dietary', []),
                'relationship_context': extraction_result.get('relationship_context', {}),
                'rgpd_sensitive': rgpd_result.get('contains_sensitive', False),
                'rgpd_categories': rgpd_result.get('categories_detected', []),
                'reasoning': extraction_result.get('reasoning')
            }
            
            results.append(combined)
            logger.info(f"Processed {note_id}: {combined['tags_count']} tags")
            
        except Exception as e:
            logger.error(f"Failed {note_id}: {str(e)}")
            print(f"\n  [WARNING] Error on {note_id}: {e}")
            continue
        
        if (idx + 1) % args.checkpoint == 0:
            checkpoint_df = pd.DataFrame(results)
            checkpoint_df.to_pickle(f'cache/wave2/checkpoint_{idx+1}.pkl')
            logger.info(f"Checkpoint saved: {idx+1} notes")
    
    print("\n[STEP 5] Exporting...")
    df_output = pd.DataFrame(results)
    
    for col in ['tags', 'allergies', 'dietary', 'rgpd_categories']:
        if col in df_output.columns:
            df_output[col] = df_output[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
    for col in ['allergy_severity', 'relationship_context']:
        if col in df_output.columns:
            df_output[col] = df_output[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x))
    
    base_name = f'{args.output}/wave2_final'
    df_output.to_excel(f'{base_name}.xlsx', index=False)
    df_output.to_csv(f'{base_name}.csv', index=False)
    df_output.to_parquet(f'{base_name}.parquet', index=False)
    df_output.to_json(f'{base_name}.json', orient='records', indent=2, force_ascii=False)
    
    print(f"  [OK] Exported to {base_name}.[xlsx|csv|parquet|json]")
    
    if rgpd_filter and rgpd_results:
        rgpd_report = rgpd_filter.generate_report(rgpd_results)
        with open(f'{args.output}/wave2_rgpd_report.json', 'w') as f:
            json.dump(rgpd_report, f, indent=2)
        print(f"  [OK] RGPD Report: {args.output}/wave2_rgpd_report.json")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*60)
    print("[DONE] PIPELINE COMPLETE")
    print("="*60)
    print(f"Notes processed: {len(results)}")
    print(f"Total tags: {sum(r['tags_count'] for r in results)}")
    print(f"Avg tags/note: {sum(r['tags_count'] for r in results) / len(results):.1f}")
    print(f"Duration: {duration/60:.1f} min")
    if not args.no_cache:
        print(cache.report())
    print(cost_tracker.report())
    
    stats = {
        'notes_processed': len(results),
        'total_tags': sum(r['tags_count'] for r in results),
        'avg_tags_per_note': sum(r['tags_count'] for r in results) / len(results),
        'duration_seconds': duration,
        'cache_stats': cache.stats if not args.no_cache else {},
        'cost': cost_tracker.get_total_cost()
    }
    with open(f'{args.output}/wave2_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    return df_output


if __name__ == "__main__":
    args = parse_args()
    run_wave2_pipeline(args)
