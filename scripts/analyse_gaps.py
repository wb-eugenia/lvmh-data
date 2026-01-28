import pandas as pd
import os
import ast

def analyze_gaps(input_file='outputs/wave1_tagged_dataset.xlsx'):
    if not os.path.exists(input_file):
        print(f"❌ Fichier non trouvé: {input_file}")
        return

    print(f"🔍 Analyse des gaps sur {input_file}...")
    try:
        df = pd.read_excel(input_file)
    except Exception as e:
        print(f"❌ Erreur lecture fichier: {e}")
        return

    # 1. Analyse professions dans transcriptions
    print("\n=== 👔 PROFESSIONS MENTIONNÉES (non taggées) ===")
    professions_keywords = [
        'avocat', 'lawyer', 'cardiologue', 'surgeon', 'chirurgien',
        'banquier', 'banker', 'architecte', 'architect', 'entrepreneur',
        'influencer', 'galeriste', 'gallerist', 'DJ', 'producteur',
        'medico', 'doctor', 'médecin', 'dentiste', 'dentist',
        'notaire', 'notary', 'trader', 'investisseur', 'investor'
    ]
    
    prof_count = 0
    for idx, row in df.iterrows():
        text = str(row['Transcription']).lower()
        tags = str(row.get('tags_extracted', '')).lower()
        
        found_keywords = [kw for kw in professions_keywords if kw in text]
        
        if found_keywords:
            # Check if a professional tag exists (heuristic)
            if 'professional' not in tags and 'entrepreneur' not in tags and 'medical' not in tags:
                print(f"[{row['ID']}] Mots-clés: {found_keywords} -> Pas de tag pro détecté")
                prof_count += 1
    
    print(f"👉 Total notes avec professions potentielles manquées: {prof_count}")

    # 2. Analyse relations/cadeaux
    print("\n=== 🎁 RELATIONS & CADEAUX (non taggés) ===")
    relations_keywords = [
        'mari', 'spouse', 'husband', 'wife', 'époux', 'figlia', 'daughter',
        'madre', 'mother', 'père', 'father', 'famiglia', 'family',
        'cadeau', 'gift', 'regalo', 'anniversaire', 'birthday', 'compleanno'
    ]
    
    rel_count = 0
    for idx, row in df.iterrows():
        text = str(row['Transcription']).lower()
        tags = str(row.get('tags_extracted', '')).lower()
        
        if any(kw in text for kw in relations_keywords):
            # Check if relationship/gift tags exist
            if 'gift' not in tags and 'shopping_with' not in tags and 'family' not in tags:
                print(f"[{row['ID']}] Relation/Cadeau détecté dans texte -> Tags manquants")
                rel_count += 1
                
    print(f"👉 Total notes avec relations/cadeaux potentiels manqués: {rel_count}")

    # 3. Analyse severity allergies
    print("\n=== 🤧 ALLERGIES AVEC SÉVÉRITÉ ===")
    severity_keywords = ['sévère', 'severe', 'grave', 'forte', 'leggera', 'mild', 'mortelle', 'life threatening']
    
    allergy_count = 0
    severity_missed = 0
    
    for idx, row in df.iterrows():
        text = str(row['Transcription']).lower()
        if 'allerg' in text or 'intoléran' in text or 'intoleran' in text:
            allergy_count += 1
            has_severity = any(kw in text for kw in severity_keywords)
            if has_severity:
                print(f"[{row['ID']}] Allergie avec sévérité détectée ('{has_severity}')")
                severity_missed += 1
                
    print(f"👉 Total notes avec allergies: {allergy_count}")
    print(f"👉 Dont avec indicateur de sévérité explicite: {severity_missed}")

if __name__ == "__main__":
    analyze_gaps()
