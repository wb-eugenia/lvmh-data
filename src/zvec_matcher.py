"""
Zvec-Compliant Product Matcher
================================
This module provides a Zvec-compatible API for product matching.
Currently uses numpy-based implementation (compatible with Python 3.13).
Can be swapped to real Zvec when deployed to production with Python 3.10-3.12.

Zvec Features Emulated:
- Hybrid search (vector + scalar filters)
- Auto-persistence to disk (JSON)
- CRUD operations on vectors
- Schema-based collection

When ready for production:
1. pip install zvec
2. Replace numpy implementation with zvec.Collection
"""

import os
import json
import pickle
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class SearchFilter:
    """Zvec-style filter for hybrid search."""
    field: str
    operator: str  # $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
    value: Any


class ZvecCollection:
    """
    Zvec-compatible Collection class.
    Handles vector storage, indexing, and hybrid search.
    
    Currently uses numpy for vectors + pandas for metadata.
    Auto-persists to JSON file.
    """
    
    def __init__(
        self,
        name: str,
        vector_dim: int = 384,
        path: str = "data/vector_store/zvec_products",
        metric: str = "cosine"
    ):
        self.name = name
        self.vector_dim = vector_dim
        self.path = Path(path)
        self.metric = metric
        
        self.vectors: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []
        self.id_to_idx: Dict[str, int] = {}
        
        self.path.mkdir(parents=True, exist_ok=True)
        self._index_file = self.path / f"{name}_vectors.npy"
        self._meta_file = self.path / f"{name}_meta.json"
        
        self._load()
        
    def _load(self):
        """Load existing collection from disk."""
        if self._index_file.exists() and self._meta_file.exists():
            try:
                self.vectors = list(np.load(self._index_file, allow_pickle=True))
                with open(self._meta_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                self.id_to_idx = {m['id']: i for i, m in enumerate(self.metadata)}
                logger.info(f"Loaded ZvecCollection '{self.name}': {len(self.vectors)} vectors")
            except Exception as e:
                logger.warning(f"Failed to load collection: {e}, starting fresh")
                self.vectors = []
                self.metadata = []
                self.id_to_idx = {}
        else:
            logger.info(f"Creating new ZvecCollection '{self.name}'")
            
    def _save(self):
        """Persist collection to disk."""
        try:
            np.save(self._index_file, np.array(self.vectors, dtype=object))
            with open(self._meta_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save collection: {e}")
            
    def insert(self, documents: List[Dict[str, Any]]) -> int:
        """
        Insert documents with vectors.
        
        Expected format:
        [
            {
                "id": "prod_123",
                "vector": [...],  # embedding array
                "name": "Sac Kelly",
                "price": 8500,
                "category": "bags",
                "maison": "Hermès",
                "stock": 5,
                ...
            },
            ...
        ]
        """
        count = 0
        for doc in documents:
            vec = doc.get('vector')
            if vec is None:
                continue
                
            if isinstance(vec, list):
                vec = np.array(vec, dtype=np.float32)
                
            doc_id = doc.get('id', f"doc_{len(self.metadata)}")
            
            meta = {k: v for k, v in doc.items() if k != 'vector'}
            meta['id'] = doc_id
            
            self.vectors.append(vec)
            self.metadata.append(meta)
            self.id_to_idx[doc_id] = len(self.metadata) - 1
            count += 1
            
        if count > 0:
            self._save()
            logger.info(f"Inserted {count} documents into '{self.name}'")
            
        return count
    
    def upsert(self, doc_id: str, document: Dict[str, Any]) -> bool:
        """Insert or update a document by ID."""
        if doc_id in self.id_to_idx:
            idx = self.id_to_idx[doc_id]
            vec = document.get('vector')
            if vec is not None:
                if isinstance(vec, list):
                    vec = np.array(vec, dtype=np.float32)
                self.vectors[idx] = vec
            
            for k, v in document.items():
                if k != 'vector':
                    self.metadata[idx][k] = v
                    
            self._save()
            logger.info(f"Updated document '{doc_id}' in '{self.name}'")
            return True
        else:
            return self.insert([document]) > 0
    
    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if doc_id not in self.id_to_idx:
            return False
            
        idx = self.id_to_idx[doc_id]
        
        last_idx = len(self.vectors) - 1
        last_id = self.metadata[last_idx]['id']
        
        self.vectors[idx] = self.vectors[last_idx]
        self.metadata[idx] = self.metadata[last_idx]
        self.id_to_idx[last_id] = idx
        
        self.vectors.pop()
        self.metadata.pop()
        del self.id_to_idx[doc_id]
        
        self._save()
        logger.info(f"Deleted document '{doc_id}' from '{self.name}'")
        return True
    
    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        if doc_id not in self.id_to_idx:
            return None
        idx = self.id_to_idx[doc_id]
        result = dict(self.metadata[idx])
        result['vector'] = self.vectors[idx].tolist()
        return result
    
    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[List[SearchFilter]] = None,
        include_vector: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: vector similarity + scalar filters.
        
        This is the Zvec-style search that combines:
        - Vector similarity search
        - Filter conditions (price, category, stock, etc.)
        
        Args:
            query_vector: The query embedding
            top_k: Number of results to return
            filters: List of filter conditions
            include_vector: Whether to include vector in results
            
        Returns:
            List of results sorted by score (descending)
        """
        if not self.vectors:
            return []
            
        query_vec = np.array(query_vector, dtype=np.float32)
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        
        query_norm = np.linalg.norm(query_vec, axis=1, keepdims=True)
        query_norm = np.where(query_norm == 0, 1, query_norm)
        query_vec = query_vec / query_norm
        
        all_vectors = np.vstack([np.array(v, dtype=np.float32).reshape(1, -1) for v in self.vectors])
        vec_norms = np.linalg.norm(all_vectors, axis=1, keepdims=True)
        vec_norms = np.where(vec_norms == 0, 1, vec_norms)
        all_vectors = all_vectors / vec_norms
        
        similarities = np.dot(query_vec, all_vectors.T).flatten()
        
        candidates = list(range(len(similarities)))
        
        if filters:
            candidates = self._apply_filters(candidates, filters)
            
        scored = []
        for idx in candidates:
            score = float(similarities[idx])
            result = {
                'id': self.metadata[idx]['id'],
                'score': round(score, 4),
                'distance': round(1 - score, 4),
            }
            
            for k, v in self.metadata[idx].items():
                if k != 'id':
                    result[k] = v
                    
            if include_vector:
                result['vector'] = self.vectors[idx].tolist()
                
            scored.append(result)
            
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:top_k]
    
    def _apply_filters(self, indices: List[int], filters: List[SearchFilter]) -> List[int]:
        """Apply filter conditions to candidate indices."""
        filtered = []
        
        for idx in indices:
            meta = self.metadata[idx]
            match = True
            
            for f in filters:
                field_val = meta.get(f.field)
                
                if f.operator == '$eq':
                    if field_val != f.value:
                        match = False
                        break
                elif f.operator == '$ne':
                    if field_val == f.value:
                        match = False
                        break
                elif f.operator == '$gt':
                    if field_val is None or field_val <= f.value:
                        match = False
                        break
                elif f.operator == '$gte':
                    if field_val is None or field_val < f.value:
                        match = False
                        break
                elif f.operator == '$lt':
                    if field_val is None or field_val >= f.value:
                        match = False
                        break
                elif f.operator == '$lte':
                    if field_val is None or field_val > f.value:
                        match = False
                        break
                elif f.operator == '$in':
                    if field_val not in f.value:
                        match = False
                        break
                elif f.operator == '$nin':
                    if field_val in f.value:
                        match = False
                        break
                        
            if match:
                filtered.append(idx)
                
        return filtered
    
    def count(self) -> int:
        """Return number of documents in collection."""
        return len(self.vectors)


class ZvecProductMatcher:
    """
    Product Matcher with Zvec-style API.
    
    Features:
    - Hybrid search (vector + business filters)
    - Auto-persistence
    - CRUD operations
    - Business reranking
    """
    
    COLOR_ALIASES: Dict[str, List[str]] = {
        "black": ["black", "noir", "nero", "schwarz", "negro"],
        "navy": ["navy", "marine"],
        "blue": ["blue", "bleu", "azul", "blau"],
        "red": ["red", "rouge", "rojo", "rot", "bordeaux", "burgundy", "wine"],
        "brown": ["brown", "marron", "marrón", "braun", "cognac"],
        "beige": ["beige", "neutral"],
        "white": ["white", "blanc", "bianco", "weiss", "weiß"],
        "green": ["green", "vert", "verde", "grün"],
    }
    
    def __init__(self, collection_path: str = "data/vector_store/zvec_products"):
        self.enabled = False
        self.model = None
        self.collection: Optional[ZvecCollection] = None
        self._stock_info: Dict[str, int] = {}
        
        if not self._check_ml_available():
            logger.warning("SentenceTransformers not installed. ZvecProductMatcher disabled.")
            return
            
        try:
            logger.info("Initializing ZvecProductMatcher...")
            self.model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            
            self.collection = ZvecCollection(
                name="lvmh_products",
                vector_dim=384,
                path=collection_path
            )
            
            if self.collection.count() == 0:
                logger.warning("Zvec collection is empty. Run migration script first.")
                
            self.enabled = True
            logger.info(f"ZvecProductMatcher ready: {self.collection.count()} products indexed")
            
        except Exception as e:
            logger.error(f"Failed to initialize ZvecProductMatcher: {e}")
            self.enabled = False
    
    def _check_ml_available(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer
            return True
        except ImportError:
            return False
    
    def load_stock_from_db(self, db_session):
        """Load stock info from database."""
        try:
            from api.models_sql import Product as ProductModel
            products = db_session.query(ProductModel.sku, ProductModel.stock).all()
            self._stock_info = {p.sku: p.stock for p in products}
            logger.info("Loaded stock info for %d products from database", len(self._stock_info))
        except Exception as e:
            logger.warning(f"Could not load stock from DB: {e}")
            self._stock_info = {}
    
    def match(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.35,
        extraction: Optional[Any] = None,
        stock_info: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Match products using Zvec hybrid search.
        
        This is the main entry point - compatible with ProductMatcher API.
        """
        if not self.enabled or not query or not self.collection:
            return []
            
        effective_stock = stock_info if stock_info is not None else self._stock_info
        
        try:
            query_struct = self._build_query_struct(query, extraction)
            search_query = query_struct.get("primary_query") or query
            category_filter = query_struct.get("category_filter")
            color_filter = set(query_struct.get("color_filter") or [])
            price_range = query_struct.get("price_range")
            
            logger.info(f"Zvec RAG query: {search_query[:100]}")
            
            query_vec = self.model.encode([search_query])[0].tolist()
            
            filters = self._build_zvec_filters(
                category=category_filter,
                price_range=price_range,
                colors=color_filter,
                stock_info=effective_stock
            )
            
            shortlist_k = min(max(top_k * 6, 12), self.collection.count())
            
            zvec_results = self.collection.search(
                query_vector=query_vec,
                top_k=shortlist_k,
                filters=filters,
                include_vector=False
            )
            
            intents = self._infer_query_intents(search_query, extraction)
            
            results = []
            for res in zvec_results:
                base_score = res['score']
                
                product_text = self._build_product_text(res)
                
                adjusted_score = self._apply_business_rerank(
                    base_score=base_score,
                    product_text=product_text,
                    intents=intents,
                    color_hints=color_filter,
                    boost_keywords=set(query_struct.get("boost_keywords", [])),
                    category_filter=category_filter,
                )
                
                if adjusted_score < threshold:
                    continue
                    
                in_stock = True
                sku = str(res.get('product_code') or res.get('sku', 'N/A'))
                if effective_stock:
                    stock = effective_stock.get(sku, -1)
                    if stock == 0:
                        in_stock = False
                
                results.append({
                    "sku": sku,
                    "name": res.get('name', res.get('title', 'Unknown')),
                    "category": res.get('category', res.get('category1_code', 'unknown')),
                    "price": res.get('price', res.get('price_eur')),
                    "url": res.get('itemurl', res.get('url', '')),
                    "image_url": res.get('imageurl', res.get('image_url', '')),
                    "in_stock": in_stock,
                    "match_score": round(adjusted_score, 2),
                    "similarity": round(adjusted_score, 2),
                    "base_score": round(base_score, 2),
                    "rerank_delta": round(adjusted_score - base_score, 3),
                    "query_used": search_query,
                })
                
            results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            final_results = results[:top_k]
            
            logger.info(
                "Zvec RAG results: %s",
                [f"{r.get('name', 'N/A')} ({r.get('match_score', 0):.2f})" for r in final_results]
            )
            
            return final_results
            
        except Exception as e:
            logger.error(f"Zvec search failed: {e}")
            return []
    
    def _build_zvec_filters(
        self,
        category: Optional[str],
        price_range: Optional[List[float]],
        colors: Set[str],
        stock_info: Dict[str, int]
    ) -> List[SearchFilter]:
        """Build Zvec-style filter list."""
        filters = []
        
        # Note: Category filter disabled - actual category codes (ART DE VIVRE, etc.)
        # don't match the semantic category (bags, slg, etc.)
        # Business reranking handles category matching instead
        
        if price_range and len(price_range) == 2:
            filters.append(SearchFilter(field="price_eur", operator="$gte", value=price_range[0]))
            filters.append(SearchFilter(field="price_eur", operator="$lte", value=price_range[1]))
            
        if colors:
            filters.append(SearchFilter(field="color", operator="$in", value=list(colors)))
            
        return filters
    
    def _build_query_struct(self, query: str, extraction: Optional[Any]) -> Dict[str, Any]:
        """Build query structure from extraction (reuse from ProductMatcher)."""
        from src.product_matcher import ProductMatcher
        
        pm = ProductMatcher.__new__(ProductMatcher)
        pm.COLOR_ALIASES = self.COLOR_ALIASES
        pm.rag_query_client = None
        
        return pm._build_query_struct(query, extraction)
    
    def _infer_query_intents(self, query: str, extraction: Optional[Any]) -> Set[str]:
        """Infer query intents (bags, SLG, etc.)."""
        text = (query or "").lower()
        intents: Set[str] = set()
        
        bag_tokens = ("sac", "bag", "handbag", "capucines", "alma", "tote", "clutch")
        slg_tokens = ("wallet", "portefeuille", "small leather", "card holder", "slg")
        apparel_tokens = ("shoe", "chaussure", "sneaker", "boots", "pantalon", "cargo", "shirt")
        
        if any(token in text for token in bag_tokens):
            intents.add("bags")
        if any(token in text for token in slg_tokens):
            intents.add("small_leather")
        if any(token in text for token in apparel_tokens):
            intents.add("apparel")
            
        return intents
    
    def _build_product_text(self, prod: Dict[str, Any]) -> str:
        """Build searchable text from product."""
        parts = [
            prod.get('name', ''),
            prod.get('title', ''),
            prod.get('category', ''),
            prod.get('category1_code', ''),
            prod.get('description', ''),
        ]
        return ' '.join(str(p) for p in parts if p).lower()
    
    def _apply_business_rerank(
        self,
        base_score: float,
        product_text: str,
        intents: Set[str],
        color_hints: Set[str],
        boost_keywords: Set[str],
        category_filter: Optional[str],
    ) -> float:
        """Apply business rules to rerank results."""
        score = base_score
        
        bag_terms = ("bag", "sac", "handbag", "capucines", "alma", "neverfull", "speedy", "twist")
        slg_terms = ("wallet", "portefeuille", "card holder", "small leather", "pochette")
        apparel_terms = ("pant", "pantalon", "cargo", "shirt", "jacket", "jean", "sweater", "dress")
        
        if "bags" in intents:
            if any(term in product_text for term in bag_terms):
                score += 0.12
            if any(term in product_text for term in apparel_terms):
                score -= 0.30
        if "small_leather" in intents:
            if any(term in product_text for term in slg_terms):
                score += 0.10
            if any(term in product_text for term in apparel_terms):
                score -= 0.20
        if "apparel" in intents:
            if any(term in product_text for term in apparel_terms):
                score += 0.08
                
        if color_hints and any(color in product_text for color in color_hints):
            score += 0.06
            
        if category_filter:
            category_signals = {
                "bags": bag_terms,
                "small_leather_goods": slg_terms,
                "ready_to_wear": apparel_terms,
            }
            if any(term in product_text for term in category_signals.get(category_filter, ())):
                score += 0.06
                
        if boost_keywords and any(kw in product_text for kw in boost_keywords):
            score += 0.06
            
        return max(0.0, min(1.0, score))
    
    def add_product(self, product_data: Dict[str, Any], embedding: Optional[np.ndarray] = None) -> bool:
        """
        Add a new product to the collection (CRUD operation).
        
        This is the Zvec-style CRUD - no index rebuild needed!
        """
        if not self.enabled or not self.collection:
            return False
            
        try:
            if embedding is None:
                text = f"{product_data.get('name', '')} {product_data.get('description', '')}"
                embedding = self.model.encode([text])[0]
                
            doc = {
                "id": product_data.get("sku") or product_data.get("product_code"),
                "vector": embedding.tolist(),
                **product_data
            }
            
            return self.collection.upsert(doc["id"], doc)
            
        except Exception as e:
            logger.error(f"Failed to add product: {e}")
            return False
    
    def update_product(self, sku: str, updates: Dict[str, Any]) -> bool:
        """Update product metadata (CRUD operation)."""
        if not self.enabled or not self.collection:
            return False
            
        try:
            existing = self.collection.get(sku)
            if not existing:
                logger.warning(f"Product {sku} not found")
                return False
                
            existing.update(updates)
            return self.collection.upsert(sku, existing)
            
        except Exception as e:
            logger.error(f"Failed to update product: {e}")
            return False
    
    def delete_product(self, sku: str) -> bool:
        """Delete a product (CRUD operation)."""
        if not self.enabled or not self.collection:
            return False
            
        return self.collection.delete(sku)


def create_collection_from_pickle(
    pickle_path: str = "data/vector_store/lv_index.pkl",
    output_path: str = "data/vector_store/zvec_products"
) -> int:
    """
    Migration script: Convert pickle index to Zvec collection.
    
    Run this once to migrate from old FAISS-style index to Zvec.
    """
    import pickle
    
    logger.info(f"Migrating {pickle_path} to Zvec format...")
    
    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
        
    embeddings = data['embeddings']
    
    if 'df' in data and data['df'] is not None:
        df = data['df']
    else:
        df = None
        
    collection = ZvecCollection(
        name="lvmh_products",
        vector_dim=embeddings.shape[1],
        path=output_path
    )
    
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
    else:
        product_skus = data.get("product_skus", [])
        product_names = data.get("product_names", [])
        product_prices = data.get("product_prices", [])
        
        for idx in range(len(embeddings)):
            doc = {
                "id": str(product_skus[idx]) if idx < len(product_skus) else f"prod_{idx}",
                "vector": embeddings[idx].tolist(),
                "name": product_names[idx] if idx < len(product_names) else "Unknown",
                "price_eur": product_prices[idx] if idx < len(product_prices) else 0,
            }
            documents.append(doc)
    
    count = collection.insert(documents)
    logger.info(f"Migration complete: {count} products added to Zvec collection")
    
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    matcher = ZvecProductMatcher()
    if matcher.enabled:
        print(f"Ready: {matcher.collection.count()} products")
        
        results = matcher.match("Sac noir elegant pour le travail")
        print("\nTest search results:")
        for r in results:
            print(f"  - {r['name']} ({r['match_score']})")
