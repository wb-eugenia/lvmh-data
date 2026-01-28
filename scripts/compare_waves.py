"""
Compare Wave 1 vs Wave 2 results.
Generates comparison report for presentation.
"""

import json
import os
from pathlib import Path

import pandas as pd


def load_wave1():
    """Load Wave 1 results."""
    files = [
        'outputs/wave1_migrated_v2.xlsx',
        'outputs/wave1_tagged_dataset.xlsx'
    ]
    for f in files:
        if os.path.exists(f):
            return pd.read_excel(f), f
    return None, None


def load_wave2():
    """Load Wave 2 results."""
    f = 'outputs/wave2_final_dataset.xlsx'
    if os.path.exists(f):
        return pd.read_excel(f), f
    return None, None


def compare_waves():
    """Generate comparison report."""
    print("="*60)
    print("📊 WAVE 1 vs WAVE 2 COMPARISON")
    print("="*60)
    
    df1, f1 = load_wave1()
    df2, f2 = load_wave2()
    
    if df1 is None:
        print("❌ Wave 1 data not found")
        return
    if df2 is None:
        print("❌ Wave 2 data not found (pipeline may still be running)")
        return
    
    print(f"\n📂 Wave 1: {f1} ({len(df1)} notes)")
    print(f"📂 Wave 2: {f2} ({len(df2)} notes)")
    
    # Parse tags if they're strings
    def parse_tags(x):
        if isinstance(x, str):
            return [t.strip() for t in x.split(',') if t.strip()]
        elif isinstance(x, list):
            return x
        return []
    
    # Calculate metrics
    if 'tags' in df1.columns:
        df1['tags_list'] = df1['tags'].apply(parse_tags)
        wave1_tags = df1['tags_list'].apply(len).sum()
        wave1_avg = df1['tags_list'].apply(len).mean()
    elif 'tags_extracted' in df1.columns:
        df1['tags_list'] = df1['tags_extracted'].apply(parse_tags)
        wave1_tags = df1['tags_list'].apply(len).sum()
        wave1_avg = df1['tags_list'].apply(len).mean()
    else:
        wave1_tags = 0
        wave1_avg = 0
    
    if 'tags' in df2.columns:
        df2['tags_list'] = df2['tags'].apply(parse_tags)
        wave2_tags = df2['tags_list'].apply(len).sum()
        wave2_avg = df2['tags_list'].apply(len).mean()
    elif 'tags_count' in df2.columns:
        wave2_tags = df2['tags_count'].sum()
        wave2_avg = df2['tags_count'].mean()
    else:
        wave2_tags = 0
        wave2_avg = 0
    
    # Confidence
    wave1_conf = df1['confidence'].mean() if 'confidence' in df1.columns else 0
    wave2_conf = df2['confidence'].mean() if 'confidence' in df2.columns else 0
    
    # RGPD stats (Wave 2 only)
    wave2_rgpd = df2['rgpd_sensitive'].sum() if 'rgpd_sensitive' in df2.columns else 0
    
    # Compression stats (Wave 2 only)
    wave2_compression = df2['compression_ratio'].mean() if 'compression_ratio' in df2.columns else 1.0
    
    report = {
        'Wave 1': {
            'notes': len(df1),
            'total_tags': int(wave1_tags),
            'avg_tags_per_note': round(wave1_avg, 2),
            'avg_confidence': round(wave1_conf, 3),
            'dataset_type': 'Clean (manual)',
            'rgpd_filter': 'No',
            'text_cleaning': 'No'
        },
        'Wave 2': {
            'notes': len(df2),
            'total_tags': int(wave2_tags),
            'avg_tags_per_note': round(wave2_avg, 2),
            'avg_confidence': round(wave2_conf, 3),
            'dataset_type': 'Raw → Auto-cleaned',
            'rgpd_filter': 'Yes',
            'text_cleaning': 'Yes',
            'compression_ratio': f"{wave2_compression:.1%}",
            'notes_with_sensitive_data': int(wave2_rgpd)
        },
        'Improvement': {
            'tag_increase': f"+{wave2_tags - wave1_tags} tags",
            'tag_increase_pct': f"+{(wave2_tags/wave1_tags - 1)*100:.1f}%" if wave1_tags > 0 else "N/A",
            'coverage_increase': f"+{len(df2) - len(df1)} notes",
            'confidence_delta': f"{(wave2_conf - wave1_conf)*100:+.1f}%"
        }
    }
    
    print("\n" + "="*60)
    print("📈 COMPARISON RESULTS")
    print("="*60)
    
    print("\n┌─────────────────────┬───────────┬───────────┐")
    print("│      Metric         │  Wave 1   │  Wave 2   │")
    print("├─────────────────────┼───────────┼───────────┤")
    print(f"│ Notes               │ {len(df1):>9} │ {len(df2):>9} │")
    print(f"│ Total Tags          │ {int(wave1_tags):>9} │ {int(wave2_tags):>9} │")
    print(f"│ Avg Tags/Note       │ {wave1_avg:>9.1f} │ {wave2_avg:>9.1f} │")
    print(f"│ Avg Confidence      │ {wave1_conf:>9.1%} │ {wave2_conf:>9.1%} │")
    print(f"│ RGPD Filter         │       No  │      Yes  │")
    print(f"│ Text Cleaning       │       No  │      Yes  │")
    print("└─────────────────────┴───────────┴───────────┘")
    
    if wave2_rgpd > 0:
        print(f"\n⚠️ Wave 2: {wave2_rgpd} notes with sensitive RGPD data detected")
    
    # Save report
    output_file = 'outputs/wave_comparison_report.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Report saved to {output_file}")
    
    return report


if __name__ == "__main__":
    compare_waves()
