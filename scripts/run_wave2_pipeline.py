"""
Wave 2 Pipeline - Complete orchestration.
Runs: Load → Clean → RGPD → Extract → Export
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.text_cleaner import MultilingualTextCleaner
from src.rgpd_filter import RGPDFilter
from src.cache_manager import CacheManager
from src.cost_tracker import CostTracker
from src.extractor import TagExtractor


# Create logs directory first
Path('logs').mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/wave2_pipeline.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_wave2_pipeline(
    input_file: str = 'data/raw/LVMH_Notes_CA101-400.csv',
    output_dir: str = 'outputs',
    use_cache: bool = True,
    checkpoint_interval: int = 50
):
    """
    Run complete Wave 2 pipeline.
    
    Steps:
    1. Load raw CSV
    2. Clean fillers
    3. RGPD filter
    4. Extract tags
    5. Export (multiple formats)
    """
    
    start_time = datetime.now()
    print(f"🚀 WAVE 2 PIPELINE STARTED - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create directories
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path('logs').mkdir(parents=True, exist_ok=True)
    Path('data/processed').mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    print("\n📦 Initializing components...")
    cleaner = MultilingualTextCleaner()
    cache = CacheManager('cache/wave2')
    cost_tracker = CostTracker()
    
    try:
        rgpd_filter = RGPDFilter()
        print("  ✅ RGPD Filter ready")
    except Exception as e:
        print(f"  ❌ RGPD Filter error: {e}")
        rgpd_filter = None
    
    try:
        extractor = TagExtractor()
        print("  ✅ Tag Extractor ready")
    except Exception as e:
        print(f"  ❌ Tag Extractor error: {e}")
        return
    
    # STEP 1: Load raw data
    print(f"\n📂 STEP 1: Loading {input_file}...")
    try:
        df_raw = pd.read_csv(input_file)
        print(f"  ✅ Loaded {len(df_raw)} notes")
        logger.info(f"Loaded {len(df_raw)} notes from {input_file}")
    except FileNotFoundError:
        print(f"  ❌ File not found: {input_file}")
        return
    
    # STEP 2: Clean fillers
    print("\n🧹 STEP 2: Cleaning fillers...")
    df_cleaned = cleaner.clean_dataset(df_raw)
    
    # Save cleaned data
    cleaned_file = 'data/processed/LVMH_Notes_CA101-400_cleaned.csv'
    df_cleaned.to_csv(cleaned_file, index=False)
    print(f"  ✅ Saved cleaned data to {cleaned_file}")
    
    # STEP 3 & 4: RGPD + Extraction
    print("\n🔒 STEP 3-4: RGPD Filter + Tag Extraction...")
    results = []
    rgpd_results = []
    
    for idx, row in tqdm(df_cleaned.iterrows(), total=len(df_cleaned), desc="Processing"):
        note_id = row['ID']
        cleaned_text = row['Transcription']
        language = row['Language']
        
        try:
            # RGPD Check (with cache)
            if rgpd_filter:
                cache_key_rgpd = cache.get_cache_key(cleaned_text, 'rgpd')
                cached_rgpd = cache.load(cache_key_rgpd, 'rgpd') if use_cache else None
                
                if cached_rgpd:
                    rgpd_result = cached_rgpd
                else:
                    note_dict = {'ID': note_id, 'Transcription': cleaned_text, 'Language': language}
                    rgpd_result = rgpd_filter.process_note(note_dict, cost_tracker)
                    cache.save(cache_key_rgpd, 'rgpd', rgpd_result)
                
                rgpd_results.append(rgpd_result)
                
                # Use anonymized text if sensitive
                text_for_extraction = rgpd_result.get('anonymized_text', cleaned_text)
            else:
                text_for_extraction = cleaned_text
                rgpd_result = {'contains_sensitive': False, 'categories_detected': []}
            
            # Tag Extraction (with cache)
            extraction_result = extractor.extract(
                transcription=text_for_extraction,
                language=language,
                client_id=note_id,
                use_cache=use_cache
            )
            
            # Combine results
            combined = {
                'ID': note_id,
                'Date': row['Date'],
                'Duration': row['Duration'],
                'Language': language,
                'Transcription_original': row['Transcription_original'],
                'Transcription_cleaned': cleaned_text,
                'fillers_removed': row['fillers_removed'],
                'compression_ratio': row['compression_ratio'],
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
            print(f"\n  ⚠️ Error on {note_id}: {e}")
            continue
        
        # Checkpoint
        if (idx + 1) % checkpoint_interval == 0:
            checkpoint_df = pd.DataFrame(results)
            checkpoint_df.to_pickle(f'cache/wave2/checkpoint_{idx+1}.pkl')
            logger.info(f"Checkpoint saved: {idx+1} notes")
    
    # STEP 5: Export
    print("\n💾 STEP 5: Exporting results...")
    df_output = pd.DataFrame(results)
    
    # Convert lists to strings for Excel compatibility
    df_export = df_output.copy()
    for col in ['tags', 'allergies', 'dietary', 'rgpd_categories']:
        if col in df_export.columns:
            df_export[col] = df_export[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
    for col in ['allergy_severity', 'relationship_context']:
        if col in df_export.columns:
            df_export[col] = df_export[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x))
    
    # Multiple formats
    base_name = f'{output_dir}/wave2_final_dataset'
    df_export.to_excel(f'{base_name}.xlsx', index=False)
    df_export.to_csv(f'{base_name}.csv', index=False)
    df_output.to_parquet(f'{base_name}.parquet', index=False)
    df_output.to_json(f'{base_name}.json', orient='records', indent=2, force_ascii=False)
    
    print(f"  ✅ Exported to {base_name}.[xlsx|csv|parquet|json]")
    
    # RGPD Report
    if rgpd_filter and rgpd_results:
        rgpd_report = rgpd_filter.generate_report(rgpd_results)
        with open(f'{output_dir}/wave2_rgpd_report.json', 'w') as f:
            json.dump(rgpd_report, f, indent=2)
        print(f"  ✅ RGPD Report: {output_dir}/wave2_rgpd_report.json")
    
    # Final stats
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*60)
    print("📊 PIPELINE COMPLETE")
    print("="*60)
    print(f"Notes processed: {len(results)}")
    print(f"Total tags: {sum(r['tags_count'] for r in results)}")
    print(f"Avg tags/note: {sum(r['tags_count'] for r in results) / len(results):.1f}")
    print(f"Duration: {duration/60:.1f} min")
    print(cache.report())
    print(cost_tracker.report())
    
    # Save stats
    stats = {
        'notes_processed': len(results),
        'total_tags': sum(r['tags_count'] for r in results),
        'avg_tags_per_note': sum(r['tags_count'] for r in results) / len(results),
        'duration_seconds': duration,
        'cache_stats': cache.stats,
        'cost': cost_tracker.get_total_cost()
    }
    with open(f'{output_dir}/wave2_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    return df_output


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Wave 2 Pipeline')
    parser.add_argument('-i', '--input', default='data/raw/LVMH_Notes_CA101-400.csv',
                       help='Input CSV file')
    parser.add_argument('-o', '--output', default='outputs',
                       help='Output directory')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching')
    parser.add_argument('--checkpoint', type=int, default=50,
                       help='Checkpoint interval')
    
    args = parser.parse_args()
    
    run_wave2_pipeline(
        input_file=args.input,
        output_dir=args.output,
        use_cache=not args.no_cache,
        checkpoint_interval=args.checkpoint
    )
