#!/usr/bin/env python3
"""
Data Cleaning CLI - Nettoie un fichier CSV avec la pipeline LVMH officielle
Usage: python scripts/data_cleaning_cli.py <fichier.csv> [--column NOM_COLONNE]
"""

import sys
import os
import argparse
import re
import pandas as pd
from pathlib import Path
from typing import Dict, List

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.text_cleaner import MultilingualTextCleaner, PIIEnforcer


def normalize_metadata(df):
    """Normalise Date et Duration pour LVMH"""
    # Date: tous formats → YYYY-MM-DD
    if 'Date' in df.columns:
        # Fallback pour dates manquantes
        df['Date'] = df['Date'].fillna('2026-02-04')
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.strftime('%Y-%m-%d')
        # Si toujours NaT apres conversion, mettre fallback
        df['Date'] = df['Date'].fillna('2026-02-04')
    
    # Duration: vers secondes
    if 'Duration' in df.columns:
        def parse_duration(dur):
            if pd.isna(dur): 
                return 0
            dur = str(dur).lower()
            # Format 00:01:12 ou 01:12
            if ':' in dur:
                parts = dur.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:  # MM:SS
                    return int(parts[0]) * 60 + int(parts[1])
            # Format avec min/m
            if 'min' in dur or ('m' in dur and 's' in dur):
                match = re.search(r'(\d+)\s*min', dur)
                mins = int(match.group(1)) if match else 0
                match = re.search(r'(\d+)\s*s', dur)
                secs = int(match.group(1)) if match else 0
                return mins * 60 + secs
            # Format nombre seul
            match = re.search(r'(\d+)', dur)
            return int(match.group(1)) if match else 0
        
        df['Duration_seconds'] = df['Duration'].apply(parse_duration)
    
    return df


def clean_csv(filepath: str, text_column: str = None, output_path: str = None):
    """Nettoie un fichier CSV avec la pipeline LVMH officielle."""
    
    # Lecture du fichier
    print(f"[INFO] Lecture de: {filepath}")
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
    
    original_count = len(df)
    original_columns = list(df.columns)
    
    print(f"[INFO] {original_count} lignes, {len(original_columns)} colonnes")
    
    # Detection automatique de la colonne texte
    if text_column is None:
        common_names = ['Transcription', 'transcription', 'text', 'Text', 'Note', 'note', 
                       'Content', 'content', 'transcript', 'Transcript']
        for col in df.columns:
            if col in common_names:
                text_column = col
                break
    
    if text_column is None:
        print("[ERREUR] Colonne de texte non trouvee. Colonnes disponibles:")
        for i, col in enumerate(df.columns):
            print(f"   {i+1}. {col}")
        choice = input("\nEntrez le numero ou le nom de la colonne: ").strip()
        try:
            idx = int(choice) - 1
            text_column = df.columns[idx]
        except:
            text_column = choice if choice in df.columns else None
    
    if text_column not in df.columns:
        print(f"[ERREUR] Colonne '{text_column}' introuvable!")
        return
    
    print(f"\n[INFO] Colonne selectionnee: {text_column}")
    
    # Initialisation du cleaner LVMH officiel
    print("\n[INFO] Initialisation du nettoyeur LVMH...")
    cleaner = MultilingualTextCleaner()
    
    # Rapport
    report = {
        "original_rows": original_count,
        "empty_rows_removed": 0,
        "duplicates_removed": 0,
        "texts_cleaned": 0,
        "fillers_removed": 0,
        "pii_removed": 0,
        "details": []
    }
    
    # 1. Suppression des lignes vides
    empty_mask = df.isna().all(axis=1)
    empty_rows = empty_mask.sum()
    if empty_rows > 0:
        df = df[~empty_mask]
        report["empty_rows_removed"] = int(empty_rows)
        report["details"].append(f"Supprime {empty_rows} lignes vides")
    
    # 2. Suppression des lignes avec texte vide
    before_count = len(df)
    df = df.dropna(subset=[text_column])
    df = df[df[text_column].astype(str).str.strip() != '']
    dropped = before_count - len(df)
    if dropped > 0:
        report["empty_rows_removed"] += dropped
        report["details"].append(f"Supprime {dropped} lignes avec {text_column} vide")
    
    # 3. Nettoyage avec la pipeline LVMH officielle (inclut RGPD)
    print(f"\n[INFO] Nettoyage de {len(df)} transcriptions avec pipeline LVMH...")
    print("[RGPD] Anonymisation PII integree...")
    
    lang_col = 'Language' if 'Language' in df.columns else None
    cleaned_texts = []
    
    for idx, row in df.iterrows():
        text = str(row[text_column])
        lang = str(row[lang_col]).upper() if lang_col and pd.notna(row[lang_col]) else 'FR'
        
        # Utilise le vrai clean_text du text_cleaner.py
        result = cleaner.clean_text(text, language=lang)
        cleaned = result.get('cleaned', text)
        
        # Couche PII supplementaire (cartes, RIB, etc.)
        cleaned = PIIEnforcer.clean(cleaned)
        
        # Post-processing: correction des artefacts
        # 1. Supprimer espaces avant ponctuation
        cleaned = re.sub(r'\s+([,;:.!?])', r'\1', cleaned)
        # 2. Corriger multiples virgules
        cleaned = re.sub(r',{2,}', ',', cleaned)
        # 3. Corriger espaces dans les nombres (4 200 -> 4200)
        cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)
        # 4. Corriger points dans les nombres (3. 000 -> 3000, 9. 500 -> 9500)
        cleaned = re.sub(r'(\d)\.\s+(\d)', r'\1\2', cleaned)
        # 5. Nettoyer espaces multiples
        cleaned = re.sub(r'\s+', ' ', cleaned)
        # 6. Corriger emails fragmentes (claire. boulangervipexample. com)
        cleaned = re.sub(r'([a-z])\.\s+([a-z])', r'\1.\2', cleaned, flags=re.IGNORECASE)
        
        # Post-processing agressif (fixes RGPD critiques)
        # 7. Fix collages [TOKEN]suivant -> [TOKEN] suivant
        cleaned = re.sub(r'\[([A-Z_]+)\]\s*([A-Z])', r'[\1] \2', cleaned)
        # 8. Fix espaces manquants après virgules/points (minuscule MAJUSCULE)
        cleaned = re.sub(r'([a-zéèàùâêîôûç])([A-ZÀ-ÚÂÊÎÔÛÇ])', r'\1 \2', cleaned)
        # 9. Fix points parasites dans les adresses (506721. Stock -> 506721 Stock)
        cleaned = re.sub(r'(\d+)\.\s+([A-Z])', r'\1 \2', cleaned)
        # 10. Fix textes colles (Pay Pal -> PayPal, pasaporte [NIF] -> [PASSPORT])
        cleaned = re.sub(r'Pay\s*Pal', 'PayPal', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'pasaporte\s+\[NIF\]', '[PASSPORT]', cleaned, flags=re.IGNORECASE)
        
        cleaned_texts.append(cleaned)
        
        if result.get('fillers_removed', 0) > 0:
            report["fillers_removed"] += result['fillers_removed']
        if result.get('duplicates_removed', 0) > 0:
            report["duplicates_removed"] += result['duplicates_removed']
        if cleaned != text:
            report["texts_cleaned"] += 1
    
    df[text_column] = cleaned_texts
    
    # Estimation PII supprimees (basique - le text_cleaner a deja anonymise)
    # On compte les patterns type [EMAIL], [PHONE] etc. qui auraient ete crees
    pii_patterns = ['[EMAIL]', '[PHONE]', '[CARTE_BANCAIRE]', '[RIB_IBAN]', 
                   '[NUM_SECU]', '[SSN]', '[DNI]', '[PASSEPORT]', '[ADRESSE]']
    pii_count = 0
    for text in df[text_column]:
        for pattern in pii_patterns:
            if pattern in str(text):
                pii_count += 1
                break  # Une seule par ligne
    report["pii_removed"] = pii_count
    
    if report["texts_cleaned"] > 0:
        report["details"].append(f"Nettoye {report['texts_cleaned']} transcriptions avec pipeline LVMH")
    if report["fillers_removed"] > 0:
        report["details"].append(f"Supprime {report['fillers_removed']} mots de remplissage (euh, bah, etc.)")
    if report["duplicates_removed"] > 0:
        report["details"].append(f"Supprime {report['duplicates_removed']} phrases dupliquees")
    if report["pii_removed"] > 0:
        report["details"].append(f"[RGPD] Anonymise donnees sensibles dans {report['pii_removed']} lignes")
    
    # Rapport final
    final_count = len(df)
    removed = original_count - final_count
    reduction = round((removed / original_count) * 100, 2) if original_count > 0 else 0
    
    print("\n" + "="*60)
    print("[OK] NETTOYAGE TERMINE")
    print("="*60)
    print(f"[STATS] {original_count} -> {final_count} lignes ({reduction}% de reduction)")
    print(f"   - {report['empty_rows_removed']} lignes vides supprimees")
    print(f"   - {report['duplicates_removed']} doublons supprimes")
    print(f"   - {report['texts_cleaned']} transcriptions nettoyees")
    print(f"   - {report['fillers_removed']} fillers supprimes (euh, bah, etc.)")
    if report['pii_removed'] > 0:
        print(f"   - {report['pii_removed']} lignes avec donnees sensibles anonymisees [RGPD]")
    print()
    print("Details:")
    for detail in report['details']:
        print(f"   [OK] {detail}")
    
    # Normalisation des metadonnees (Date, Duration)
    df = normalize_metadata(df)
    
    # Rapport PII detaille (RGPD audit)
    pii_types = {}
    for text in df[text_column]:
        for token in re.findall(r'\[(.*?)\]', str(text)):
            pii_types[token] = pii_types.get(token, 0) + 1
    
    if pii_types:
        print("\n[RGPD AUDIT] PII detectes:")
        for pii, count in sorted(pii_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   [{pii}] -> {count} occurrences")
    
    # Sauvegarde
    if output_path is None:
        input_path = Path(filepath)
        output_path = input_path.parent / f"cleaned_{input_path.name}"
    
    df.to_csv(output_path, index=False)
    print(f"\n[SAVE] Fichier sauvegarde: {output_path}")
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description='Nettoie un fichier CSV avec la pipeline LVMH officielle (RGPD compliant)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/data_cleaning_cli.py data/notes.csv
  python scripts/data_cleaning_cli.py data/notes.csv --column Transcription
  python scripts/data_cleaning_cli.py data/notes.xlsx -o output/cleaned.csv

Pipeline LVMH:
  1. Anonymisation PII (RGPD) - emails, telephones, cartes, etc.
  2. Suppression fillers - euh, bah, tu sais, etc.
  3. Dedoublonnage semantique
  4. Normalisation texte
        """
    )
    
    parser.add_argument('file', help='Fichier CSV ou Excel a nettoyer')
    parser.add_argument('--column', '-c', help='Nom de la colonne contenant le texte')
    parser.add_argument('--output', '-o', help='Chemin du fichier de sortie')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"[ERREUR] Fichier introuvable: {args.file}")
        sys.exit(1)
    
    clean_csv(args.file, args.column, args.output)


if __name__ == '__main__':
    main()
