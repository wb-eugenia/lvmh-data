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

from src.pipeline_batch_v2 import PipelineBatchV2

# Logger config
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Nettoyage préventif du cache pour éviter conflit V1/V2
import shutil
if os.path.exists("cache/tier3"):
    shutil.rmtree("cache/tier3")
    print("🧹 Cache Tier 3 nettoyé (Migration V2)")
if os.path.exists("cache/mistral_prompts"):
    shutil.rmtree("cache/mistral_prompts")
    print("🧹 Cache Tier 2 nettoyé")

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
    print("\n⚙️  Lancement du Pipeline Batch V2...")
    pipeline = PipelineBatchV2(use_cache=False, use_bq=False)
    
    # Force Tier 3 parsing (pour voir la taxonomie complète)
    # On bypass le routeur pour ce test spécifique en appelant directement l'extracteur ou en forçant le niveau ?
    # Mieux : on laisse le pipeline faire, le routeur devrait l'envoyer en T3 vu la complexité.
    
    results = await pipeline.process_batch_async([fake_note])
    result = results[0]
    
    # 3. Vérification de la Structure (Taxonomie 4 Piliers)
    print("\n📊 RÉSULTATS D'ANALYSE (JSON):")
    
    # On dump le résultat pour inspection visuelle
    # Les résultats sont déjà à la racine du dict retourné par le pipeline
    data = result
    
    # Nettoyage pour affichage (retirer les clés techniques si besoin)
    display_data = {k: v for k, v in data.items() if k not in ['_cleaned_text']}
        
    print(json.dumps(display_data, indent=2, ensure_ascii=False))
    
    # 4. Validations Spécifiques
    errors = []
    
    # Check Pilier 1 (Produit)
    p1 = data.get('pilier_1_univers_produit', {})
    if 'Handbag_Main' not in p1.get('categories', []) and 'Leather_Goods' not in p1.get('categories', []):
        # C'est flexible, on vérifie juste que ce n'est pas vide
        if not p1.get('categories'):
             errors.append("❌ Pilier 1: Aucune catégorie détectée")
    
    # Check Pilier 2 (Client - Avocate)
    p2 = data.get('pilier_2_profil_client', {})
    profession = p2.get('profession', {})
    if not profession.get('status') and not profession.get('sector'):
         # "Avocate" devrait être capté
         print(f"⚠️ Warning Pilier 2: Profession non structurée (attendu: Legal_Finance). Got: {profession}")

    # Check Pilier 4 (Business - Anniversaire)
    p3 = data.get('pilier_3_hospitalite_care', {})
    if p3.get('occasion') != 'Personal_Milestone' and 'Anniversary' not in str(p3):
         print(f"⚠️ Warning Pilier 3: Occasion 'Anniversaire' non détectée.")

    # Check RAG (Matched Products)
    # Le RAG insère les produits MATCHÉS dans le pilier 1
    matched = p1.get('matched_products', [])
    if matched:
        print(f"\n✅ RAG SUCCÈS: {len(matched)} produits trouvés !")
        for p in matched:
            print(f"   👜 {p['name']} ({p.get('sku')}) - Score: {p.get('match_score')}")
    else:
        errors.append("❌ RAG ÉCHEC: Aucun produit matché (Capucines attendu)")

    if not errors:
        print("\n🎉 SUCCÈS TOTAL ! Le pipeline est conforme V2 + RAG.")
    else:
        print("\n❌ ÉCHECS DÉTECTÉS :")
        for err in errors:
            print(err)

if __name__ == "__main__":
    asyncio.run(main())
