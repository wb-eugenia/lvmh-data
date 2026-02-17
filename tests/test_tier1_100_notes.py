"""
Tier 1 Precision Test on 100 Real Notes
Tests Tier 1 against real LVMH notes to identify failure patterns.
"""

import csv
import sys
import os
from typing import Dict, List, Set
from collections import defaultdict

sys.path.append(os.getcwd())

from src.tier1_rules import Tier1RulesEngine


def load_real_notes(csv_path: str) -> List[Dict]:
    """Load real notes from CSV."""
    data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def run_tier1_on_notes(engine: Tier1RulesEngine, notes: List[Dict]) -> List[Dict]:
    """Run Tier 1 on all notes and return results."""
    results = []
    
    for i, row in enumerate(notes):
        text = row['Transcription']
        lang = 'EN' if row.get('Language', 'FR') == 'EN' else 'FR'
        
        try:
            result = engine.extract(text, lang)
            results.append({
                'id': row['ID'],
                'text': text[:100] + '...',
                'full_text': text,
                'language': lang,
                'tags': result.tags,
                'budget': result.pilier_4_action_business.budget_specific,
                'status': result.pilier_2_profil_client.lifestyle.family,
                'allergies': result.pilier_3_hospitalite_care.allergies.contact,
                'diet': result.pilier_3_hospitalite_care.diet,
                'relation': result.pilier_2_profil_client.purchase_context.type,
                'gender': result.pilier_2_profil_client.profession.status,
                'urgency': result.pilier_4_action_business.urgency,
                'confidence': result.confidence,
            })
        except Exception as e:
            results.append({
                'id': row['ID'],
                'error': str(e),
            })
    
    return results


def analyze_results(results: List[Dict]):
    """Analyze and display results."""
    print("\n" + "="*70)
    print("TIER 1 ANALYSIS ON 100 REAL NOTES")
    print("="*70)
    
    # Stats
    total = len(results)
    errors = sum(1 for r in results if 'error' in r)
    successful = total - errors
    
    print(f"\nTotal Notes: {total}")
    print(f"Successful: {successful}")
    print(f"Errors: {errors}")
    
    # Tags analysis
    all_tags = defaultdict(int)
    for r in results:
        if 'error' not in r:
            for tag in r['tags']:
                all_tags[tag] += 1
    
    print(f"\n--- TAG DISTRIBUTION ---")
    for tag, count in sorted(all_tags.items(), key=lambda x: -x[1])[:20]:
        print(f"  {tag}: {count}")
    
    # Budget detection
    budget_found = sum(1 for r in results if 'error' not in r and r.get('budget'))
    print(f"\n--- BUDGET ---")
    print(f"  Detected: {budget_found}/{successful} ({100*budget_found/successful:.1f}%)")
    
    # Status detection  
    status_found = sum(1 for r in results if 'error' not in r and r.get('status') and r['status'] != 'Unknown')
    print(f"\n--- STATUS ---")
    print(f"  Detected: {status_found}/{successful} ({100*status_found/successful:.1f}%)")
    
    # Allergies detection
    allergies_found = sum(1 for r in results if 'error' not in r and r.get('allergies'))
    print(f"\n--- ALLERGIES ---")
    print(f"  Detected: {allergies_found}/{successful} ({100*allergies_found/successful:.1f}%)")
    
    # Diet detection
    diet_found = sum(1 for r in results if 'error' not in r and r.get('diet'))
    print(f"\n--- DIET ---")
    print(f"  Detected: {diet_found}/{successful} ({100*diet_found/successful:.1f}%)")
    
    # Gender detection
    gender_found = sum(1 for r in results if 'error' not in r and r.get('gender'))
    print(f"\n--- GENDER ---")
    print(f"  Detected: {gender_found}/{successful} ({100*gender_found/successful:.1f}%)")
    
    # Relations (gift vs self)
    gifts = sum(1 for r in results if 'error' not in r and r.get('relation') == 'Gift')
    self_purchases = sum(1 for r in results if 'error' not in r and r.get('relation') == 'Self')
    print(f"\n--- PURCHASE TYPE ---")
    print(f"  Gifts: {gifts}")
    print(f"  Self purchases: {self_purchases}")
    
    # Average confidence
    avg_confidence = sum(r.get('confidence', 0) for r in results if 'error' not in r) / successful
    print(f"\n--- CONFIDENCE ---")
    print(f"  Average: {avg_confidence:.2f}")
    
    # Show some examples with errors
    print(f"\n--- SAMPLE RESULTS ---")
    for r in results[:5]:
        if 'error' not in r:
            print(f"\nID: {r['id']}")
            print(f"  Text: {r['text'][:80]}...")
            print(f"  Tags: {r['tags'][:5]}")
            print(f"  Budget: {r.get('budget')}, Status: {r.get('status')}")
            print(f"  Gender: {r.get('gender')}, Relation: {r.get('relation')}")


def save_results_csv(results: List[Dict], output_path: str):
    """Save results to CSV for analysis."""
    if not results:
        return
    
    # Flatten the results
    flat_results = []
    for r in results:
        if 'error' in r:
            flat_results.append({
                'id': r['id'],
                'error': r['error'],
            })
        else:
            flat_results.append({
                'id': r['id'],
                'text': r['text'],
                'tags': ','.join(r['tags']) if r['tags'] else '',
                'budget': r.get('budget', ''),
                'status': r.get('status', ''),
                'allergies': ','.join(r.get('allergies', [])),
                'diet': ','.join(r.get('diet', [])),
                'relation': r.get('relation', ''),
                'gender': r.get('gender', ''),
                'urgency': r.get('urgency', ''),
                'confidence': r.get('confidence', ''),
            })
    
    fieldnames = ['id', 'text', 'tags', 'budget', 'status', 'allergies', 'diet', 'relation', 'gender', 'urgency', 'confidence']
    if 'error' in results[0]:
        fieldnames.append('error')
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_results)
    
    print(f"\nResults saved to: {output_path}")


def main():
    print("Loading Tier 1 Engine...")
    engine = Tier1RulesEngine()
    
    print("Loading 100 Real Notes...")
    notes = load_real_notes('LVMH_Realistic_Merged_CA001-100.csv')
    print(f"Loaded {len(notes)} notes\n")
    
    print("Running Tier 1 on all notes...")
    results = run_tier1_on_notes(engine, notes)
    
    analyze_results(results)
    save_results_csv(results, 'tests/tier1_100_notes_results.csv')


if __name__ == '__main__':
    main()
