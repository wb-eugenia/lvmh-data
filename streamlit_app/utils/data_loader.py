"""
Data Loader for Streamlit Dashboard.
Loads pipeline results from JSON/CSV files.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import streamlit as st

OUTPUT_DIR = Path("outputs")

@st.cache_data
def load_latest_results(dataset_name: str = "Wave 2 (300 notes)") -> pd.DataFrame:
    """
    Load the latest pipeline results based on selection.
    """
    if dataset_name == "Wave 2 (300 notes)":
        # Look for the largest/latest json file
        files = list(OUTPUT_DIR.glob("pipeline_v2_*.json"))
        if not files:
            return pd.DataFrame()
        
        # Sort by modification time
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return _load_json_to_df(latest_file)
        
    elif dataset_name == "Wave 1 (100 notes)":
        # Placeholder for Wave 1
        return pd.DataFrame()
        
    return pd.DataFrame()

def _load_json_to_df(filepath: Path) -> pd.DataFrame:
    """Helper to load JSON results into a flat DataFrame."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # If list of dicts
        if isinstance(data, list):
            df = pd.json_normalize(data)
        elif isinstance(data, dict) and 'results' in data:
            df = pd.json_normalize(data['results'])
        else:
            return pd.DataFrame()
            
        # Normalize column names (Old Schema -> New Schema)
        col_map = {
            'ID': 'id',
            'Transcription': 'original_text',
            'Language': 'language',
            'tags': 'extraction.tags',
            'tier': 'routing.tier',
            'confidence': 'routing.confidence'
        }
        df = df.rename(columns=col_map)
        
        # Ensure key columns exist
        required_cols = ['id', 'processing_time_ms', 'routing.tier', 'routing.confidence', 'original_text', 'extraction.tags']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # Fill missing values for visualization safety
        df['processing_time_ms'] = pd.to_numeric(df['processing_time_ms'], errors='coerce').fillna(100)
        df['routing.confidence'] = pd.to_numeric(df['routing.confidence'], errors='coerce').fillna(0.0)
        df['routing.tier'] = pd.to_numeric(df['routing.tier'], errors='coerce').fillna(1)
        
        # Ensure extraction.tags is a list
        if 'extraction.tags' in df.columns:
             df['extraction.tags'] = df['extraction.tags'].apply(lambda x: x if isinstance(x, list) else [])
                
        # Calculate cost if missing (approx)
        if 'cost_eur' not in df.columns:
            def calc_cost(row):
                tier = row.get('routing.tier')
                if tier == 3: return 0.0001
                return 0.0
            df['cost_eur'] = df.apply(calc_cost, axis=1)
            
        return df
        
    except Exception as e:
        st.error(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def get_rgpd_stats(df: pd.DataFrame) -> Dict:
    """Calculate RGPD statistics from dataframe."""
    if df.empty:
        return {}
        
    total = len(df)
    # Check for rgpd columns
    if 'rgpd.contains_sensitive' in df.columns:
        sensitive = df[df['rgpd.contains_sensitive'] == True]
        count = len(sensitive)
        rate = count / total * 100
        
        categories = []
        for cats in sensitive['rgpd.categories_detected']:
            if isinstance(cats, list):
                categories.extend(cats)
                
        return {
            'total': total,
            'sensitive_count': count,
            'sensitive_rate': rate,
            'categories': pd.Series(categories).value_counts().to_dict()
        }
    return {}
