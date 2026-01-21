#!/usr/bin/env python3
"""
Main extraction script for LVMH Voice to Tag pipeline.
Processes transcriptions and extracts structured tags using LLM.

Usage:
    python scripts/run_extraction.py                    # Process all notes
    python scripts/run_extraction.py --test --sample 5  # Test with 5 samples
    python scripts/run_extraction.py --clear-cache      # Clear cached results
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

from src.extractor import TagExtractor
from src.utils import (
    load_csv_data,
    results_to_dataframe,
    export_to_excel,
    export_stats_json,
    print_extraction_summary,
    clear_cache,
    format_tags_for_display
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LVMH Voice to Tag - Extract structured tags from transcriptions"
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        default="LVMH_Realistic_Merged_CA001-100.csv",
        help="Input CSV file path"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="outputs/wave1_tagged_dataset.xlsx",
        help="Output Excel file path"
    )
    
    parser.add_argument(
        "--taxonomy", "-t",
        type=str,
        default="config/taxonomy_v1.json",
        help="Taxonomy JSON file path"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (print results, don't save)"
    )
    
    parser.add_argument(
        "--sample", "-s",
        type=int,
        default=None,
        help="Process only N random samples"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (re-process all)"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cache and exit"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use"
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    
    print("\n" + "="*60)
    print("🏷️  LVMH VOICE TO TAG - Extraction Pipeline")
    print("="*60)
    
    # Handle cache clearing
    if args.clear_cache:
        clear_cache()
        return 0
    
    # Load data
    print(f"\n📂 Loading data from: {args.input}")
    try:
        df = load_csv_data(args.input)
        print(f"   Loaded {len(df)} transcriptions")
    except FileNotFoundError:
        print(f"❌ Error: File not found: {args.input}")
        return 1
    
    # Sample if requested
    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42)
        print(f"   Sampled {len(df)} notes for testing")
    
    # Initialize extractor
    print(f"\n🤖 Initializing extractor...")
    print(f"   Model: {args.model}")
    print(f"   Taxonomy: {args.taxonomy}")
    
    try:
        extractor = TagExtractor(
            taxonomy_path=args.taxonomy,
            model=args.model,
            cache_dir=None if args.no_cache else "cache"
        )
        print(f"   ✅ Loaded {extractor.taxonomy.num_tags} tags in {extractor.taxonomy.num_categories} categories")
    except Exception as e:
        print(f"❌ Error initializing extractor: {e}")
        return 1
    
    # Convert DataFrame to list of dicts
    data = df.to_dict('records')
    
    # Process with progress bar
    print(f"\n🔄 Processing {len(data)} transcriptions...")
    
    results = []
    with tqdm(total=len(data), desc="Extracting", unit="note") as pbar:
        for row in data:
            result = extractor.extract(
                transcription=row.get('Transcription', ''),
                language=row.get('Language', 'EN'),
                client_id=row.get('ID'),
                use_cache=not args.no_cache
            )
            results.append(result)
            pbar.update(1)
    
    # Calculate stats
    stats = extractor.get_stats(results)
    
    # Print summary
    print_extraction_summary(stats)
    
    # Test mode: just show results
    if args.test:
        print("\n📋 SAMPLE RESULTS (Test Mode):")
        print("-"*60)
        for i, (row, result) in enumerate(zip(data[:5], results[:5])):
            print(f"\n{result['client_id']} ({result['language']}):")
            print(f"  Tags: {format_tags_for_display(result['tags'])}")
            print(f"  Confidence: {result['confidence']:.0%}")
            print(f"  Budget: {result.get('budget_range', 'N/A')}")
            print(f"  Status: {result.get('client_status', 'N/A')}")
            if result.get('allergies'):
                print(f"  ⚠️ Allergies: {', '.join(result['allergies'])}")
            if result.get('dietary'):
                print(f"  🥗 Dietary: {', '.join(result['dietary'])}")
        print("\n[Test mode - results not saved]")
        return 0
    
    # Merge results with original data
    print(f"\n📊 Preparing output...")
    merged_df = results_to_dataframe(df, results, id_col="ID")
    
    # Export to Excel
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    export_to_excel(merged_df, str(output_path))
    
    # Export stats
    stats_path = output_path.with_suffix('.stats.json')
    export_stats_json(stats, str(stats_path))
    
    print(f"\n✅ EXTRACTION COMPLETE!")
    print(f"   Output: {output_path}")
    print(f"   Stats: {stats_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
