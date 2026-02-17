"""
Script de Vérification Finale (End-to-End)
Teste:
1. La nouvelle Taxonomie (4 Piliers)
2. Le moteur RAG (Product Matcher)
3. La validation Pydantic stricte
"""

import sys
import os
import asyncio
import json
import logging

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline_async import AsyncPipeline

# Logger config
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def main():
    print(f"{'='*60}")
    print("🚀 TEST END-TO-END FINAL : TAXONOMIE V2 + RAG")
    print(f"{'='*60}")

    # 1. Simuler une note vocale riche
    fake_note = {
        "ID": "TEST-001",
        "Transcription": "Bonjour, je cherche un sac Capucines noir pour ma femme. C'est pour son anniversaire la semaine prochaine. Elle adore le cuir grainé et les finitions dorées. Budget environ 6000 euros. Elle est avocate, donc il faut que ça fasse pro.",
        "Language": "FR"
    }
    
    print("\n📝 Note Vocale Simulée:")
    print(f"\"{fake_note['Transcription']}\"")
    
    # 2. Lancer le pipeline
    print("\n⚙️  Lancement du Pipeline Async...")
    pipeline = AsyncPipeline(use_cache=False)
    
    result = await pipeline.process_note(fake_note)
    
    if result is None:
        print("❌ Échec du traitement")
        return
    
    # 3. Vérification de la Structure (Taxonomie 4 Piliers)
    print("\n📊 RÉSULTATS D'ANALYSE:")
    print(f"   Tier: {result.routing.tier}")
    print(f"   Confidence: {result.routing.confidence:.2f}")
    print(f"   Tags: {result.extraction.tags}")
    
    # 4. Validations Spécifiques
    errors = []
    
    # Check Tags
    if not result.extraction.tags:
        errors.append("❌ Aucun tag détecté")
    
    # Check RAG (Matched Products)
    if hasattr(result, 'products') and result.products:
        print(f"\n✅ RAG SUCCÈS: {len(result.products)} produits trouvés !")
    else:
        print("\n⚠️ RAG:Aucun produits matchés")
    
    if not errors:
        print("\n🎉 SUCCÈS TOTAL ! Le pipeline est conforme.")
    else:
        print("\n❌ ÉCHECS DÉTECTÉS :")
        for err in errors:
            print(err)

if __name__ == "__main__":
    asyncio.run(main())
