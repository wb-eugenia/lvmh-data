"""
Script de Migration: FAISS pickle → Zvec Collection
=====================================================
Convertit l'index pickle existant en format Zvec.

Usage:
    python scripts/migrate_to_zvec.py

"""

import os
import sys
import json
import pickle
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PICKLE_PATH = "data/vector_store/lv_index.pkl"
OUTPUT_DIR = "data/vector_store/zvec_products"


def migrate():
    """Migrate pickle index to Zvec format."""
    
    logger.info(f"Loading pickle from {PICKLE_PATH}...")
    
    if not os.path.exists(PICKLE_PATH):
        logger.error(f"Pickle file not found: {PICKLE_PATH}")
        logger.info("Run scripts/build_vector_store.py first to create the index")
        return 0
    
    with open(PICKLE_PATH, 'rb') as f:
        data = pickle.load(f)
    
    embeddings = data['embeddings']
    logger.info(f"Loaded {len(embeddings)} embeddings, shape: {embeddings.shape}")
    
    if 'df' in data and data['df'] is not None:
        df = data['df']
        logger.info(f"Loaded DataFrame with {len(df)} products")
    else:
        df = None
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    vectors_file = os.path.join(OUTPUT_DIR, "lvmh_products_vectors.npy")
    meta_file = os.path.join(OUTPUT_DIR, "lvmh_products_meta.json")
    
    documents = []
    
    if df is not None:
        for idx, row in df.iterrows():
            doc = {
                "id": str(row.get("product_code", f"prod_{idx}")),
                "vector": embeddings[idx].tolist(),
                "name": str(row.get("title", row.get("name", "Unknown"))),
                "title": str(row.get("title", "")),
                "price_eur": float(row.get("price_eur", row.get("price", 0))),
                "itemurl": str(row.get("itemurl", "")),
                "imageurl": str(row.get("imageurl", "")),
                "category1_code": str(row.get("category1_code", "")),
                "description": str(row.get("description", "")),
            }
            documents.append(doc)
            
            if (idx + 1) % 100 == 0:
                logger.info(f"Processed {idx + 1}/{len(df)} products...")
    else:
        product_skus = data.get("product_skus", [])
        product_names = data.get("product_names", [])
        
        for idx in range(len(embeddings)):
            doc = {
                "id": str(product_skus[idx]) if idx < len(product_skus) else f"prod_{idx}",
                "vector": embeddings[idx].tolist(),
                "name": product_names[idx] if idx < len(product_names) else "Unknown",
            }
            documents.append(doc)
    
    vectors = [np.array(doc.pop("vector"), dtype=np.float32) for doc in documents]
    
    logger.info(f"Saving {len(vectors)} vectors to {vectors_file}...")
    np.save(vectors_file, np.array(vectors, dtype=object))
    
    logger.info(f"Saving metadata to {meta_file}...")
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Migration complete! {len(documents)} products migrated to Zvec format")
    logger.info(f"Zvec collection location: {OUTPUT_DIR}")
    
    return len(documents)


if __name__ == "__main__":
    count = migrate()
    print(f"\n✓ Migration complete: {count} products")
