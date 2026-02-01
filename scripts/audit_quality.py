import json
import os
import sys
from pathlib import Path
from collections import Counter
import statistics

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.taxonomy import TaxonomyManager

def audit(results_path: str):
    print("🚀 LANCEMENT AUDIT QUALITÉ & PERFORMANCE\n")
    
    if not os.path.exists(results_path):
        print(f"❌ Fichier non trouvé: {results_path}")
        return

    with open(results_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    total_notes = len(data)
    print(f"📂 Notes analysées: {total_notes}")
    
    # 1. TIER DISTRIBUTION & SPEED
    tiers = Counter()
    failed_t3 = 0
    from collections import defaultdict
    tier_times = defaultdict(list)
    
    for note in data:
        t = note.get('tier', 'Unknown')
        # Ensure it's an int if possible for sorting, or keep as string
        tiers[t] += 1
        
        # Check failures
        if t == 3 and note.get('meta_analysis', {}).get('confidence_score', 0) == 0.0:
            failed_t3 += 1
            
        # Speed (if available)
        if 'processing_time_ms' in note:
            tier_times[t].append(note['processing_time_ms'])
            
    print("\n📊 1. DISTRIBUTION & PERFORMANCE")
    for t in sorted(tiers.keys()):
        count = tiers[t]
        avg_time = f"{statistics.mean(tier_times[t]):.0f}ms" if tier_times[t] else "N/A"
        print(f"   - Tier {t}: {count} notes ({count/total_notes*100:.1f}%) | Vitesse moy: {avg_time}")
        
    print(f"   ⚠️ Tier 3 Échecs: {failed_t3}/{tiers[3]} ({(failed_t3/tiers[3]*100 if tiers[3] else 0):.1f}%)")

    # 2. RAG PERFORMANCE
    print("\n🧠 2. RAG ANALYSIS (Global)")
    rag_hits = 0
    rag_scores = []
    
    for note in data:
        # Check nested key
        p1 = note.get('pilier_1_univers_produit', {})
        p1_matches = p1.get('matched_products', []) if isinstance(p1, dict) else []
        
        # Check root key (fallback)
        root_matches = note.get('matched_products', [])
        
        matches = p1_matches or root_matches or []
        
        if matches:
            rag_hits += 1
            # Collect scores
            for m in matches:
                if 'match_score' in m:
                    rag_scores.append(m['match_score'])
                    
    avg_rag_score = statistics.mean(rag_scores) if rag_scores else 0
    print(f"   - Notes avec RAG Matches: {rag_hits}/{total_notes} ({rag_hits/total_notes*100:.1f}%)")
    print(f"   - Score de pertinence moyen: {avg_rag_score:.2f}")
    if rag_hits < 5:
        print("   ⚠️ RATE DE MATCH FAIBLE. Vérifiez le seuil ou l'index.")

    # 3. QUALITÉ TAXONOMIE (HALLUCINATIONS)
    print("\n🏷️ 3. QUALITÉ TAXONOMIE & PROMPTS")
    tm = TaxonomyManager()
    valid_core = set(tm.get_core_tags())
    
    all_extracted_tags = []
    invalid_tags = []
    empty_cats = 0
    
    for note in data:
        p1 = note.get('pilier_1_univers_produit', {})
        cats = p1.get('categories', []) if isinstance(p1, dict) else []
        
        if not cats:
            empty_cats += 1
            
        for tag in cats:
            all_extracted_tags.append(tag)
            if not tm.validate_tag(tag):
                invalid_tags.append(tag)
                
    print(f"   - Notes sans catégories détectées: {empty_cats}/{total_notes} ({empty_cats/total_notes*100:.1f}%)")
    print(f"   - Total Tags extraits: {len(all_extracted_tags)}")
    print(f"   - Tags Invalides (Hallucinations potentielles): {len(invalid_tags)} ({len(invalid_tags)/len(all_extracted_tags)*100:.1f}%)" if all_extracted_tags else "   - Tags: 0")
    
    if invalid_tags:
        print(f"     Exemples invalides: {list(set(invalid_tags))[:5]}")
        
    print("\n✅ AUDIT TERMINÉ.")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "outputs/batch_test_results.json"
    audit(path)
