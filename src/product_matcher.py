"""
Product Matcher (RAG Component)
Encapsulates Vector Search logic for LVMH Products.
"""

import os
import pickle
import logging
import numpy as np
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from sentence_transformers import SentenceTransformer
    HAS_ML = True
except ImportError:
    HAS_ML = False

logger = logging.getLogger(__name__)

class ProductMatcher:
    """
    Moteur de recherche sémantique pour les produits LVMH.
    Charge un index pré-calculé (pickle) et utilise SentenceTransformers.
    """
    
    def __init__(self, index_path: str = "data/vector_store/lv_index.pkl"):
        self.enabled = False
        self.model = None
        self.index = None
        self.df = None
        
        if not HAS_ML:
             logger.warning("🚫 SentenceTransformers not installed. RAG disabled.")
             return

        if not os.path.exists(index_path):
            logger.warning(f"🚫 Vector Index not found at {index_path}. Run `scripts/build_vector_store.py` first.")
            return
            
        try:
            logger.info("🧠 Loading RAG Index & Model...")
            
            # Load Index
            with open(index_path, 'rb') as f:
                data = pickle.load(f)
                self.embeddings = data['embeddings']
                self.df = data['df']
            
            # Load Model (Cached)
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self.enabled = True
            
            # Pre-normalize database embeddings for fast cosine sim
            self.norm_embeddings = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            
            logger.info(f"✅ ProductMatcher Ready: {len(self.df)} products indexed.")
            
        except Exception as e:
            logger.error(f"❌ Failed to init ProductMatcher: {e}")
            self.enabled = False

    def match(self, query: str, top_k: int = 3, threshold: float = 0.35) -> List[Dict[str, Any]]:
        """
        Trouve les produits les plus proches sémantiquement.
        """
        if not self.enabled or not query:
            return []
            
        try:
            # Vectorize Query
            query_vec = self.model.encode([query])
            
            # Normalize Query
            norm_query = query_vec / np.linalg.norm(query_vec, axis=1, keepdims=True)
            
            # Cosine Similarity (Vectorized)
            # (1, 384) @ (384, N) -> (1, N)
            similarities = np.dot(norm_query, self.norm_embeddings.T).flatten()
            
            # Top K filtering
            # On ne garde que ceux au dessus du threshold
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score < threshold:
                    continue
                    
                prod = self.df.iloc[idx].to_dict()
                
                # Cleanup for JSON output (handle NaN, Timestamp, etc)
                clean_prod = {
                    "sku": str(prod.get('product_code', 'N/A')),
                    "name": self._get_best_name(prod),
                    "price": float(prod.get('price', 0)) if pd.notnull(prod.get('price')) else None,
                    "url": str(prod.get('itemurl', '')),
                    "match_score": round(score, 2)
                }
                results.append(clean_prod)
                
            return results
            
        except Exception as e:
            logger.error(f"⚠️ RAG Search failed: {e}")
            return []

    def _get_best_name(self, prod: Dict) -> str:
        """Helper to extract best display name."""
        candidates = ['title', 'name', 'product_name', 'model', 'description']
        for key in candidates:
            # Case insensitive lookup
            found_key = next((k for k in prod.keys() if k.lower() == key), None)
            if found_key and prod[found_key] and str(prod[found_key]).strip() != "nan":
                val = str(prod[found_key])
                if val.lower() != "louis vuitton": # Filter generic brand name
                    return val
        return "Unknown Product"

if __name__ == "__main__":
    # Self-test
    import pandas as pd # Need pandas for isna check in helper
    matcher = ProductMatcher()
    if matcher.enabled:
        hits = matcher.match("Sac noir élégant")
        print(f"Test Hits: {hits}")
