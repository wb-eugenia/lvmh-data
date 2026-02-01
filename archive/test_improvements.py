"""
Test des améliorations du text cleaner
- Nettoyage de caractères répétés
- Détection de similarité sémantique
"""

from src.text_cleaner import MultilingualTextCleaner

cleaner = MultilingualTextCleaner()

print("="*70)
print(" TESTS DES AMELIORATIONS")
print("="*70)

# Test 1: Nettoyage de caractères répétés
print("\n📝 TEST 1: Caractères répétés")
print("-"*70)
text1 = "C'est beauuuuuu!!!! Vraiment géniaaal!!!"
result1 = cleaner.clean_text(text1, 'FR')
print(f"AVANT: {result1['original']}")
print(f"APRES: {result1['cleaned']}")

# Test 2: Détection de similarité (phrases presque identiques)
print("\n📝 TEST 2: Similarité sémantique")
print("-"*70)
text2 = "Je cherche un sac en cuir noir. Je cherche un sac en cuir noir pour le travail."
result2 = cleaner.clean_text(text2, 'FR')
print(f"AVANT: {result2['original']}")
print(f"APRES: {result2['cleaned']}")
print(f"Doublons détectés: {result2.get('duplicates_removed', 0)}")

# Test 3: Combiné (caractères + fillers + doublons)
print("\n📝 TEST 3: Combiné (tout)")
print("-"*70)
text3 = "Euhhh!!! Bon, je veux un sac en cuir. Beuuuh, euh, je veux un sac en cuir!!!!"
result3 = cleaner.clean_text(text3, 'FR')
print(f"AVANT: {result3['original']}")
print(f"APRES: {result3['cleaned']}")
print(f"Fillers: {result3['fillers_removed']}")
print(f"Doublons: {result3.get('duplicates_removed', 0)}")
print(f"Compression: {result3['compression_ratio']:.1%}")

print("\n" + "="*70)
print("✅ Tests terminés")
print("="*70)
