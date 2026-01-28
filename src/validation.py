import pandas as pd
import os
from typing import Dict, List, Optional
import ast

class QualityValidator:
    """Valide qualité extraction via échantillonnage manuel"""
    
    def __init__(self, df: pd.DataFrame, sample_size: int = 20):
        self.df = df
        self.sample_size = sample_size
        
    def sample_stratified(self) -> pd.DataFrame:
        """Échantillon stratifié par langue"""
        samples = []
        
        # Check for language column
        lang_col = 'language' if 'language' in self.df.columns else ('Language' if 'Language' in self.df.columns else None)
        
        if lang_col:
            unique_langs = self.df[lang_col].unique()
            n_per_lang = max(1, self.sample_size // len(unique_langs))
            
            for lang in unique_langs:
                lang_df = self.df[self.df[lang_col] == lang]
                n = min(n_per_lang, len(lang_df))
                if n > 0:
                    samples.append(lang_df.sample(n=n, random_state=42))
        else:
            # Fallback random sample
            n = min(self.sample_size, len(self.df))
            samples.append(self.df.sample(n=n, random_state=42))
            
        if not samples:
            return pd.DataFrame()
            
        return pd.concat(samples)
    
    def export_validation_template(self, sample_df: pd.DataFrame, output_path: str = 'validation/sample_to_validate.csv') -> str:
        """Exporte échantillon pour validation manuelle offline"""
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Select relevant columns
        cols = ['client_id', 'ID', 'language', 'Language', 'Transcription', 'tags', 'tags_extracted']
        available_cols = [c for c in cols if c in sample_df.columns]
        
        validation_template = sample_df[available_cols].copy()
        
        # Normalize tags column for display
        if 'tags' in validation_template.columns:
            validation_template['llm_tags'] = validation_template['tags']
        elif 'tags_extracted' in validation_template.columns:
            validation_template['llm_tags'] = validation_template['tags_extracted']
        else:
            validation_template['llm_tags'] = ''
            
        validation_template['manual_tags'] = ''  # Colonne vide à remplir
        validation_template['notes'] = ''
        
        # Keep only essential columns for the validator
        final_cols = []
        if 'client_id' in validation_template.columns: final_cols.append('client_id')
        elif 'ID' in validation_template.columns: final_cols.append('ID')
        
        if 'language' in validation_template.columns: final_cols.append('language')
        elif 'Language' in validation_template.columns: final_cols.append('Language')
        
        final_cols.extend(['Transcription', 'llm_tags', 'manual_tags', 'notes'])
        
        validation_template[final_cols].to_csv(output_path, index=False)
        print(f"✅ Template exporté: {output_path}")
        print("📝 Remplis la colonne 'manual_tags' (séparés par virgules) puis utilise compute_metrics_from_csv()")
        return output_path

    def compute_metrics(self, validation_df: pd.DataFrame) -> Dict[str, float]:
        """Calcule précision, recall, F1"""
        tp = validation_df['tp'].sum()
        fp = validation_df['fp'].sum()
        fn = validation_df['fn'].sum()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'sample_size': len(validation_df)
        }
        
    def compute_metrics_from_csv(self, validation_csv_path: str) -> Dict[str, float]:
        """Calcule métriques depuis CSV validé"""
        if not os.path.exists(validation_csv_path):
            raise FileNotFoundError(f"Fichier non trouvé: {validation_csv_path}")
            
        df = pd.read_csv(validation_csv_path)
        
        results = []
        for _, row in df.iterrows():
            # Parse LLM tags
            llm_raw = row.get('llm_tags', '')
            llm_tags = set()
            
            if isinstance(llm_raw, str):
                # Try to parse list string or comma separated
                llm_raw = llm_raw.strip()
                if llm_raw.startswith('[') and llm_raw.endswith(']'):
                    try:
                        parsed = ast.literal_eval(llm_raw)
                        if isinstance(parsed, list):
                            llm_tags = set(str(t).strip() for t in parsed)
                    except:
                        pass
                else:
                    llm_tags = set(t.strip() for t in llm_raw.split(',') if t.strip())
            elif isinstance(llm_raw, list):
                llm_tags = set(str(t).strip() for t in llm_raw)
                
            # Parse Manual tags
            manual_raw = row.get('manual_tags', '')
            manual_tags = set()
            
            if pd.isna(manual_raw) or str(manual_raw).strip() == '':
                # If manual tags empty, assume LLM was wrong? Or skip? 
                # Usually empty manual tags means "no tags should be there"
                pass
            else:
                manual_tags = set(t.strip() for t in str(manual_raw).split(',') if t.strip())
            
            tp = len(llm_tags & manual_tags)
            fp = len(llm_tags - manual_tags)
            fn = len(manual_tags - llm_tags)
            
            results.append({'tp': tp, 'fp': fp, 'fn': fn})
        
        if not results:
            return {'precision': 0, 'recall': 0, 'f1_score': 0, 'sample_size': 0}
            
        return self.compute_metrics(pd.DataFrame(results))
