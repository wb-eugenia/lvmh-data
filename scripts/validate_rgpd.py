"""
RGPD Validation CLI.
Manual validation interface to measure Precision/Recall on RGPD detection.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rgpd_filter import RGPDFilter


def load_sample(sample_size: int = 20) -> pd.DataFrame:
    """Load a sample of notes for validation."""
    # Try Wave 2 cleaned data first
    cleaned_file = 'data/processed/LVMH_Notes_CA101-400_cleaned.csv'
    if os.path.exists(cleaned_file):
        df = pd.read_csv(cleaned_file)
    else:
        raw_file = 'data/raw/LVMH_Notes_CA101-400.csv'
        df = pd.read_csv(raw_file)
    
    # Sample with mixed languages
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)
    return sample


def run_validation():
    """Interactive CLI for RGPD validation."""
    print("="*60)
    print("🔒 RGPD DETECTION VALIDATION CLI")
    print("="*60)
    print("\nThis tool validates the accuracy of RGPD detection.")
    print("For each note, you will see the LLM's detection and can mark it as:")
    print("  - TP (True Positive): Correctly detected sensitive data")
    print("  - FP (False Positive): Incorrectly flagged as sensitive")
    print("  - FN (False Negative): Missed sensitive data")
    print("  - TN (True Negative): Correctly identified as safe")
    print("\nPress Enter to start, or 'q' to quit.\n")
    
    if input().lower() == 'q':
        return
    
    # Initialize
    rgpd_filter = RGPDFilter()
    sample = load_sample(20)
    
    validations = []
    
    for idx, row in sample.iterrows():
        note_id = row['ID']
        text = row['Transcription']
        language = row['Language']
        
        print(f"\n{'='*60}")
        print(f"📝 Note {note_id} ({language})")
        print(f"{'='*60}")
        print(f"\n{text[:500]}{'...' if len(text) > 500 else ''}\n")
        
        # Run RGPD detection
        note_dict = {'ID': note_id, 'Transcription': text, 'Language': language}
        result = rgpd_filter.process_note(note_dict)
        
        print(f"🔍 LLM Detection:")
        print(f"   Contains Sensitive: {result['contains_sensitive']}")
        print(f"   Categories: {result['categories_detected']}")
        if result.get('rgpd_result', {}).get('sensitive_spans'):
            print(f"   Spans: {result['rgpd_result']['sensitive_spans']}")
        print(f"   Reasoning: {result['rgpd_result'].get('reasoning', 'N/A')}")
        
        # Get user validation
        print("\n📊 Your validation:")
        print("   [1] TP - Correctly detected sensitive data")
        print("   [2] FP - False alarm (not actually sensitive)")
        print("   [3] FN - Missed sensitive data (add what was missed)")
        print("   [4] TN - Correctly identified as safe")
        print("   [s] Skip this note")
        print("   [q] Quit validation")
        
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 's':
            continue
        
        validation = {
            'ID': note_id,
            'language': language,
            'llm_detected': result['contains_sensitive'],
            'llm_categories': result['categories_detected'],
            'validation': None,
            'actual_categories': [],
            'notes': ''
        }
        
        if choice == '1':
            validation['validation'] = 'TP'
        elif choice == '2':
            validation['validation'] = 'FP'
        elif choice == '3':
            validation['validation'] = 'FN'
            actual = input("What categories were missed? (comma-separated): ")
            validation['actual_categories'] = [c.strip() for c in actual.split(',')]
        elif choice == '4':
            validation['validation'] = 'TN'
        
        notes = input("Additional notes (optional): ")
        validation['notes'] = notes
        
        validations.append(validation)
        print(f"✅ Recorded: {validation['validation']}")
    
    # Calculate metrics
    if validations:
        tp = sum(1 for v in validations if v['validation'] == 'TP')
        fp = sum(1 for v in validations if v['validation'] == 'FP')
        fn = sum(1 for v in validations if v['validation'] == 'FN')
        tn = sum(1 for v in validations if v['validation'] == 'TN')
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'notes_validated': len(validations),
            'confusion_matrix': {
                'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn
            },
            'metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1
            },
            'validations': validations
        }
        
        # Save report
        output_file = 'outputs/rgpd_validation_report.json'
        Path('outputs').mkdir(exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print("📊 VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Notes validated: {len(validations)}")
        print(f"TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")
        print(f"\nPrecision: {precision:.1%}")
        print(f"Recall: {recall:.1%}")
        print(f"F1-Score: {f1:.1%}")
        print(f"\n✅ Report saved to {output_file}")


if __name__ == "__main__":
    run_validation()
