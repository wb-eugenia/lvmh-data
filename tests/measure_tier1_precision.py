"""
Tier 1 Precision Measurement Script
Measures baseline precision against ground truth dataset.
"""

import csv
import sys
import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict

sys.path.append(os.getcwd())

from src.tier1_rules import Tier1RulesEngine


def load_ground_truth(csv_path: str) -> List[Dict]:
    """Load ground truth dataset."""
    data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def normalize_tags(tags_str: str) -> Set[str]:
    """Normalize tags from ground truth."""
    if not tags_str or tags_str == 'none':
        return set()
    return set(t.strip().lower() for t in tags_str.split(','))


def normalize_allergies(allergy_str: str) -> Set[str]:
    """Normalize allergies."""
    if not allergy_str or allergy_str == 'none':
        return set()
    return set(a.strip().lower().replace('_allergy', '').replace('_intolerance', '') for a in allergy_str.split(','))


def normalize_relations(rel_str: str) -> Set[str]:
    """Normalize relations."""
    if not rel_str or rel_str == 'none':
        return set()
    return set(r.strip().lower() for r in rel_str.split(','))


def evaluate_tier1(engine: Tier1RulesEngine, test_data: List[Dict]) -> Dict:
    """Evaluate Tier 1 against ground truth."""
    
    results = {
        'tags': {'tp': 0, 'fp': 0, 'fn': 0},
        'budget': {'correct': 0, 'total': 0},
        'status': {'correct': 0, 'total': 0},
        'allergies': {'tp': 0, 'fp': 0, 'fn': 0},
        'relations': {'tp': 0, 'fp': 0, 'fn': 0},
        'gender': {'correct': 0, 'total': 0},
        'dietary': {'tp': 0, 'fp': 0, 'fn': 0},
        'urgency': {'correct': 0, 'total': 0},
    }
    
    errors = []
    
    for idx, row in enumerate(test_data, 1):
        text = row['text']
        lang = row.get('language', 'FR')
        
        expected_tags = normalize_tags(row['expected_tags'])
        expected_budget = row['expected_budget']
        expected_status = row.get('expected_status', '').lower()
        expected_allergies = normalize_allergies(row.get('expected_allergies', ''))
        expected_relations = normalize_relations(row.get('expected_relations', ''))
        expected_gender = row.get('expected_gender', '').lower()
        expected_dietary = normalize_tags(row.get('expected_dietary', ''))
        expected_urgency = row.get('expected_urgency', '').lower()
        
        try:
            result = engine.extract(text, lang)
        except Exception as e:
            errors.append(f"ID {row['id']}: Extraction failed - {e}")
            continue
        
        extracted_tags = set(t.lower() for t in result.tags)
        
        tp_tags = len(expected_tags & extracted_tags)
        fp_tags = len(extracted_tags - expected_tags)
        fn_tags = len(expected_tags - extracted_tags)
        
        results['tags']['tp'] += tp_tags
        results['tags']['fp'] += fp_tags
        results['tags']['fn'] += fn_tags
        
        if expected_budget and expected_budget != 'none':
            results['budget']['total'] += 1
            extracted_budget = result.pilier_4_action_business.budget_specific or 0
            
            if str(expected_budget) == '0':
                if extracted_budget == 0 or extracted_budget > 100000:
                    results['budget']['correct'] += 1
            elif extracted_budget and abs(extracted_budget - int(expected_budget)) < 500:
                results['budget']['correct'] += 1
        
        if expected_status and expected_status != 'none':
            results['status']['total'] += 1
            extracted_status = result.pilier_2_profil_client.lifestyle.family if result.pilier_2_profil_client else 'Unknown'
            if extracted_status and expected_status in extracted_status.lower():
                results['status']['correct'] += 1
        
        if expected_allergies:
            extracted_allergies = set()
            if result.pilier_3_hospitalite_care and result.pilier_3_hospitalite_care.allergies:
                allergies = result.pilier_3_hospitalite_care.allergies
                if hasattr(allergies, 'contact'):
                    for a in allergies.contact:
                        extracted_allergies.add(a.lower().replace('_allergy', '').replace('_intolerance', ''))
                if hasattr(allergies, 'food'):
                    for a in allergies.food:
                        extracted_allergies.add(a.lower().replace('_allergy', '').replace('_intolerance', ''))
            
            tp_allergy = len(expected_allergies & extracted_allergies)
            fp_allergy = len(extracted_allergies - expected_allergies)
            fn_allergy = len(expected_allergies - extracted_allergies)
            
            results['allergies']['tp'] += tp_allergy
            results['allergies']['fp'] += fp_allergy
            results['allergies']['fn'] += fn_allergy
        
        if expected_relations:
            extracted_relations = set()
            if result.pilier_2_profil_client and result.pilier_2_profil_client.purchase_context:
                ptype = result.pilier_2_profil_client.purchase_context.type
                if ptype:
                    extracted_relations.add(ptype.lower())
                    if ptype.lower() == 'gift':
                        extracted_relations.add('gift')
                behavior = result.pilier_2_profil_client.purchase_context.behavior
                if behavior:
                    extracted_relations.add(behavior.lower())
            
            tp_rel = len(expected_relations & extracted_relations)
            fp_rel = len(extracted_relations - expected_relations)
            fn_rel = len(expected_relations - extracted_relations)
            
            results['relations']['tp'] += tp_rel
            results['relations']['fp'] += fp_rel
            results['relations']['fn'] += fn_rel
        
        if expected_gender and expected_gender != 'none':
            results['gender']['total'] += 1
            extracted_gender = result.pilier_2_profil_client.profession.status if result.pilier_2_profil_client else None
            if extracted_gender and expected_gender in extracted_gender.lower():
                results['gender']['correct'] += 1
        
        if expected_dietary:
            extracted_dietary = set()
            if result.pilier_3_hospitalite_care:
                if hasattr(result.pilier_3_hospitalite_care, 'diet') and result.pilier_3_hospitalite_care.diet:
                    for d in result.pilier_3_hospitalite_care.diet:
                        extracted_dietary.add(d.lower())
            
            tp_diet = len(expected_dietary & extracted_dietary)
            fp_diet = len(extracted_dietary - expected_dietary)
            fn_diet = len(expected_dietary - extracted_dietary)
            
            results['dietary']['tp'] += tp_diet
            results['dietary']['fp'] += fp_diet
            results['dietary']['fn'] += fn_diet
        
        if expected_urgency and expected_urgency != 'none':
            results['urgency']['total'] += 1
            extracted_urgency = result.pilier_4_action_business.urgency if result.pilier_4_action_business else None
            if extracted_urgency and expected_urgency in extracted_urgency.lower():
                results['urgency']['correct'] += 1
    
    return results, errors


def calculate_metrics(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Calculate precision, recall, f1."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def print_results(results: Dict):
    """Print evaluation results."""
    print("\n" + "="*60)
    print("TIER 1 PRECISION EVALUATION RESULTS")
    print("="*60)
    
    overall_metrics = []
    
    for metric_name, data in results.items():
        if 'tp' in data:
            p, r, f1 = calculate_metrics(data['tp'], data['fp'], data['fn'])
            overall_metrics.append(f1)
            print(f"\n{metric_name.upper()}):")
            print(f"  Precision: {p:.2%}")
            print(f"  Recall:    {r:.2%}")
            print(f"  F1-Score:  {f1:.2%}")
            if data['fp'] > 0:
                print(f"  False Positives: {data['fp']}")
            if data['fn'] > 0:
                print(f"  False Negatives: {data['fn']}")
        else:
            accuracy = data['correct'] / data['total'] if data['total'] > 0 else 0.0
            overall_metrics.append(accuracy)
            print(f"\n{metric_name.upper()}:")
            print(f"  Accuracy: {accuracy:.2%}")
            print(f"  Correct: {data['correct']}/{data['total']}")
    
    avg_f1 = sum(overall_metrics) / len(overall_metrics) if overall_metrics else 0
    print(f"\n{'='*60}")
    print(f"OVERALL AVERAGE SCORE: {avg_f1:.2%}")
    print(f"{'='*60}")


def main():
    print("Loading Tier 1 Engine...")
    engine = Tier1RulesEngine()
    
    print("Loading Ground Truth Dataset...")
    test_data = load_ground_truth('tests/tier1_ground_truth.csv')
    print(f"Loaded {len(test_data)} test cases\n")
    
    print("Running Tier 1 Evaluation...")
    results, errors = evaluate_tier1(engine, test_data)
    
    print_results(results)
    
    if errors:
        print("\nERRORS:")
        for err in errors:
            print(f"  - {err}")


if __name__ == '__main__':
    main()
