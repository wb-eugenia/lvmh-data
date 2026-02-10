import asyncio
import json
import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simuler l'appel debug
from src.event_pipeline import EventPipeline

async def test_debug():
    pipeline = EventPipeline()
    
    test_note = """Madame Dupont a appelé pour un Speedy 30 en cuir noir. 
Budget 3200-3800€. Elle veut le voir samedi prochain.
Adresse: 88 Champs Elysées 75008 Paris. Paiement carte 3782 8224 6310 005X"""
    
    result = await pipeline.analyze_note_debug(test_note, 'FR')
    print('=== Résultat Debug ===')
    print(f"Quality Score: {result.get('quality_score')}")
    print(f"Confidence Score: {result.get('confidence_score')}")
    print(f"Completeness Score: {result.get('completeness_score')}")
    print(f"Meta Analysis: {result.get('meta_analysis')}")
    print(f"Tier Used: {result.get('tier_used')}")
    print()
    
    # Check extraction result
    extraction = result.get('extraction_result', {})
    p1 = extraction.get('pilier_1_univers_produit', {})
    p4 = extraction.get('pilier_4_action_business', {})
    
    print(f"Pilier 1 - Produits: {p1.get('produits_mentionnes')}")
    print(f"Pilier 1 - Catégories: {p1.get('categories')}")
    print(f"Pilier 4 - Budget: {p4.get('budget_specific')}")
    print(f"Pilier 4 - Budget Potential: {p4.get('budget_potential')}")
    print(f"Pilier 4 - NBA: {p4.get('next_best_action')}")

if __name__ == "__main__":
    asyncio.run(test_debug())
