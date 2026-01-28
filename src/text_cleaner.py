"""
Multilingual Text Cleaner for LVMH Voice Notes.
Removes filler words and verbal hesitations to improve LLM extraction quality.
"""

import re
from typing import Dict, List
import pandas as pd
from tqdm import tqdm


class MultilingualTextCleaner:
    """Supprime fillers verbaux multilingues des transcriptions"""
    
    # Dictionnaires fillers par langue
    FILLERS = {
        'FR': [
            # Hésitations
            r'\b(euh|hum|bah|ben|bon|hein|quoi|voilà|alors|donc)\b',
            # Expressions redondantes
            r'\b(tu sais|vous savez|tu vois|vous voyez)\b',
            r'\b(en fait|du coup|en gros|grosso modo)\b',
            r'\b(disons|disons que|on va dire)\b',
            r'\b(en quelque sorte|en quelque manière|pour ainsi dire|en quelque façon)\b',
            r'\b(c\'est-à-dire|à peu près|plus ou moins)\b',
            r'\b(eh bien|enfin|bref|là|machin|chose|truc|style|genre)\b',
            r'\b(un petit peu|un tantinet|un peu|plutôt)\b',
            r'\b(si tu veux|si vous voulez|je veux dire)\b',
        ],
        
        'EN': [
            r'\b(uh|um|er|ah|hmm|well|okay|ok|yeah|yep|right)\b',
            r'\b(you know|you see|I mean|I guess|I suppose)\b',
            r'\b(you know what I mean)\b',
            r'\b(sort of|kind of|like|basically|actually|literally)\b',
            r'\b(sort of like|kind of like)\b',
            r'\b(let me see|let\'s see)\b',
            r'\b(more or less|or so|roughly|approximately|about)\b',
            r'\b(in a way|in a manner of speaking|as it were|if you will)\b',
            r'\b(in some way|something like|to some extent|pretty much)\b',
        ],
        
        'IT': [
            r'\b(eh|ehm|beh|boh|va bene|ok|allora|quindi|cioè|insomma)\b',
            r'\b(tipo|tipo così|diciamo|diciamo che|praticamente|capito|sai|capisci|capite)\b',
            r'\b(se vuoi|se capite|se capisci)\b',
            r'\b(un po\'|un tantino|un pochino)\b',
            r'\b(in qualche modo|in qualche maniera|per così dire)\b',
            r'\b(più o meno|all\'incirca|circa|pressappoco)\b',
            r'\b(in pratica|in un certo senso|piuttosto|bene)\b',
        ],
        
        'ES': [
            r'\b(eh|em|pues|bueno|vale|ok|entonces|ya)\b',
            r'\b(ya sabes|ya ves|ya veis|sabes)\b',
            r'\b(pues sí)\b',
            r'\b(digamos|digamos que|vamos a ver)\b',
            r'\b(o sea|es decir|tipo|como)\b',
            r'\b(un poco|un poquito|un tantito)\b',
            r'\b(más o menos|alrededor de|aproximadamente|por ahí)\b',
            r'\b(de alguna manera|en alguna forma|en cierto modo|por así decirlo)\b',
            r'\b(si quieres|si queréis|en plan|en realidad)\b',
        ],
        
        'DE': [
            r'\b(äh|ähm|eh|halt|naja|genau|ja|okay|ok)\b',
            r'\b(sozusagen|gewissermaßen|irgendwie|quasi|eigentlich)\b',
            r'\b(weißt du|sag mal)\b',
            r'\b(ein bisschen|ein wenig|ein Tick|ziemlich)\b',
            r'\b(mehr oder weniger|ungefähr|etwa|so|circa)\b',
            r'\b(auf eine Art|in gewisser Weise|so gesehen)\b',
            r'\b(wenn du willst|sagen wir|zum Beispiel)\b',
        ]
    }
    
    def clean_text(self, text: str, language: str) -> Dict:
        """Nettoie une transcription"""
        
        if not text or not isinstance(text, str):
            return {
                'original': text or '',
                'cleaned': text or '',
                'fillers_removed': 0,
                'compression_ratio': 1.0,
                'tokens_saved_estimate': 0
            }
        
        if language not in self.FILLERS:
            return {
                'original': text,
                'cleaned': text,
                'fillers_removed': 0,
                'compression_ratio': 1.0,
                'tokens_saved_estimate': 0
            }
        
        cleaned = text
        fillers_count = 0
        
        # Applique chaque pattern de fillers
        for pattern in self.FILLERS[language]:
            matches = re.findall(pattern, cleaned, flags=re.IGNORECASE)
            fillers_count += len(matches)
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Nettoie espaces multiples
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Nettoie ponctuation isolée
        cleaned = re.sub(r'\s+([.,;:!?])', r'\1', cleaned)
        cleaned = re.sub(r'([.,;:!?])\s*\1+', r'\1', cleaned)  # Déduplique ponctuation
        
        # Nettoie début/fin
        cleaned = cleaned.strip()
        
        # Compression ratio
        compression = len(cleaned) / len(text) if len(text) > 0 else 1.0
        
        return {
            'original': text,
            'cleaned': cleaned,
            'fillers_removed': fillers_count,
            'compression_ratio': compression,
            'tokens_saved_estimate': int((len(text) - len(cleaned)) / 4)  # ~4 chars/token
        }
    
    def clean_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie dataset complet"""
        results = []
        total_tokens_saved = 0
        total_fillers = 0
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="🧹 Cleaning"):
            result = self.clean_text(row['Transcription'], row['Language'])
            
            results.append({
                'ID': row['ID'],
                'Date': row['Date'],
                'Duration': row['Duration'],
                'Language': row['Language'],
                'Length': row['Length'],
                'Transcription_original': result['original'],
                'Transcription': result['cleaned'],
                'fillers_removed': result['fillers_removed'],
                'compression_ratio': result['compression_ratio'],
                'tokens_saved': result['tokens_saved_estimate']
            })
            
            total_tokens_saved += result['tokens_saved_estimate']
            total_fillers += result['fillers_removed']
        
        print(f"""
📊 NETTOYAGE TERMINÉ:
Notes traitées: {len(df)}
Fillers supprimés: {total_fillers:,}
Tokens économisés (estimation): {total_tokens_saved:,}
Économie coût API: ~${total_tokens_saved * 0.00015:.2f}
        """)
        
        return pd.DataFrame(results)


if __name__ == "__main__":
    import os
    
    input_file = 'data/raw/LVMH_Notes_CA101-400.csv'
    output_file = 'data/processed/LVMH_Notes_CA101-400_cleaned.csv'
    
    if not os.path.exists(input_file):
        print(f"❌ Fichier non trouvé: {input_file}")
        exit(1)
    
    # Create output directory
    os.makedirs('data/processed', exist_ok=True)
    
    # Load raw CSV
    print(f"📂 Chargement de {input_file}...")
    df = pd.read_csv(input_file)
    print(f"📊 {len(df)} notes chargées")
    
    # Clean
    cleaner = MultilingualTextCleaner()
    df_cleaned = cleaner.clean_dataset(df)
    
    # Export
    df_cleaned.to_csv(output_file, index=False)
    print(f"✅ Fichier nettoyé exporté: {output_file}")
    
    # Exemples avant/après
    print("\n📝 EXEMPLES AVANT/APRÈS:")
    for i in [0, 1, 2]:
        row = df_cleaned.iloc[i]
        print(f"\n{'='*60}")
        print(f"{row['ID']} ({row['Language']})")
        print(f"{'='*60}")
        print(f"AVANT ({len(row['Transcription_original'])} chars):")
        print(row['Transcription_original'][:300] + "...")
        print(f"\nAPRÈS ({len(row['Transcription'])} chars):")
        print(row['Transcription'][:300] + "...")
        print(f"\nFillers supprimés: {row['fillers_removed']}")
        print(f"Compression: {row['compression_ratio']:.1%}")
