"""Test complet du pipeline pour debug."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline_async import AsyncPipeline

async def test_full_pipeline():
    """Test avec note réaliste."""
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=True)
    
    test_note = {
        'ID': 'TEST_001',
        'Transcription': """Madame Dupont a appelé pour un Speedy 30 en cuir noir. 
Budget 3200-3800€. Elle veut le voir samedi prochain.
Adresse: 88 Champs Elysées 75008 Paris. Paiement carte 3782 8224 6310 005X""",
        'Language': 'FR'
    }
    
    print("=== Test Pipeline Complet ===\n")
    
    result = await pipeline.process_note(test_note)
    
    # Debug: voir le contenu brut
    if result and result.extraction:
        print("=== Debug Raw Extraction ===")
        ext_dict = result.extraction.model_dump()
        print(f"meta_analysis dict: {ext_dict.get('meta_analysis')}")
        print()
    
    if result:
        ext = result.extraction
        print(f"OK Pipeline terminé avec succès")
        print(f"   Tier utilisé: {result.routing.tier}")
        print(f"   Confiance: {result.routing.confidence}")
        print()
        
        print("=== Meta Analysis ===")
        if ext and ext.meta_analysis:
            meta = ext.meta_analysis
            print(f"   quality_score: {meta.quality_score} (type: {type(meta.quality_score)})")
            print(f"   completeness_score: {getattr(meta, 'completeness_score', 'N/A')}")
            print(f"   confidence_score: {getattr(meta, 'confidence_score', 'N/A')}")
            print(f"   missing_info: {meta.missing_info}")
            print(f"   advisor_feedback: {meta.advisor_feedback}")
        else:
            print("   ERREUR: meta_analysis is None or missing!")
        print()
        
        print("=== Pilier 1 - Produits ===")
        if ext and ext.pilier_1_univers_produit:
            p1 = ext.pilier_1_univers_produit
            print(f"   categories: {p1.categories}")
            print(f"   produits_mentionnes: {getattr(p1, 'produits_mentionnes', 'N/A')}")
            print(f"   marques_detectees: {getattr(p1, 'marques_detectees', 'N/A')}")
        print()
        
        print("=== Pilier 4 - Business ===")
        if ext and ext.pilier_4_action_business:
            p4 = ext.pilier_4_action_business
            print(f"   budget_potential: {p4.budget_potential}")
            print(f"   budget_specific: {getattr(p4, 'budget_specific', 'N/A')}")
            print(f"   next_best_action: {p4.next_best_action}")
        print()
        
        print("=== RGPD ===")
        print(f"   contains_sensitive: {result.rgpd.contains_sensitive}")
        print(f"   categories_detected: {result.rgpd.categories_detected}")
    else:
        print("ERREUR: Pipeline a retourné None")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
