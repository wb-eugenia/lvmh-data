import json
import os
import sys
from collections import Counter
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.taxonomy import TaxonomyManager

def analyze_taxonomy(results_path: str, min_frequency: int = 5):
    print(f"📊 ANALYSE TAXONOMIE (Seuil Fréquence: {min_frequency})")
    
    if not os.path.exists(results_path):
        print(f"❌ Fichier non trouvé: {results_path}")
        return

    with open(results_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    tm = TaxonomyManager()
    valid_tags = set(tm.get_core_tags())
    
    extracted_tags = []
    
    for note in data:
        p1 = note.get('pilier_1_univers_produit', {})
        cats = p1.get('categories', []) if isinstance(p1, dict) else []
        for tag in cats:
            extracted_tags.append(tag)
            
    total_tags = len(extracted_tags)
    counts = Counter(extracted_tags)
    
    # Separation Valid vs Invalid
    known_tags = {t: c for t, c in counts.items() if t in valid_tags}
    unknown_tags = {t: c for t, c in counts.items() if t not in valid_tags}
    
    print(f"\n🔹 Total Tags Extraits: {total_tags}")
    print(f"🔹 Tags Connus: {sum(known_tags.values())} occurrences ({len(known_tags)} uniques)")
    print(f"🔹 Tags Inconnus (Hallucinations): {sum(unknown_tags.values())} occurrences ({len(unknown_tags)} uniques)")
    
    print("\n🔍 TOP HALLUCINATIONS (Fréquentes):")
    candidates_to_add = []
    candidates_to_map = []
    
    sorted_unknown = sorted(unknown_tags.items(), key=lambda x: x[1], reverse=True)
    
    for tag, count in sorted_unknown:
        if count >= min_frequency:
            print(f"   [ADD?]  {tag}: {count}")
            candidates_to_add.append(tag)
        else:
            candidates_to_map.append(tag)
            
    print(f"\n📉 Tags rares (< {min_frequency}) à mapper/ignorer: {len(candidates_to_map)} (Ex: {candidates_to_map[:5]})")
    
    print("\n💡 RECOMMANDATION ACTIONS:")
    print("------------------------------------------------")
    print("1. AJOUTER CES TAGS AU FICHIER JSON (Core / Keywords) :")
    print(json.dumps(candidates_to_add, indent=2))
    print("------------------------------------------------")

if __name__ == "__main__":
    analyze_taxonomy("outputs/batch_run_400.json")
