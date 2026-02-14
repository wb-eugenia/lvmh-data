"""
Semantic cache for LLM responses using sentence embeddings.
"""

import os
import json
import logging
import hashlib
from typing import Optional, Any, List
from datetime import datetime

import numpy as np

logger = logging.getLogger("lvmh-api.semantic_cache")

USE_EMBEDDINGS = os.getenv("USE_SEMANTIC_CACHE", "0") == "1"

_embedding_model = None
_embeddings_cache: List[np.ndarray] = []
_cache_data: List[dict] = []
_cache_embeddings_key = "lvmh:semantic:embeddings"
_cache_key_prefix = "lvmh:semantic:data:"
_similarity_threshold = 0.92


def _get_embedding_model():
    """Lazy load the embedding model."""
    global _embedding_model
    if _embedding_model is None and USE_EMBEDDINGS:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Semantic cache embedding model loaded")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
    return _embedding_model


def _get_text_embedding(text: str) -> Optional[np.ndarray]:
    """Get embedding for text."""
    model = _get_embedding_model()
    if model is None:
        return None
    
    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding
    except Exception as e:
        logger.warning(f"Embedding error: {e}")
        return None


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def _hash_text(text: str) -> str:
    """Create a hash of the text for exact matching."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def semantic_get(key: str, text: str) -> Optional[Any]:
    """
    Get cached response using semantic similarity.
    First tries exact match, then falls back to similarity search.
    """
    if not USE_EMBEDDINGS:
        return None
    
    from api.redis_client import get_redis
    
    try:
        r = await get_redis()
        
        # Try exact match first
        exact_key = f"{_cache_key_prefix}exact:{_hash_text(text)}"
        exact_result = await r.get(exact_key)
        if exact_result:
            logger.debug(f"Semantic cache exact hit for key {key}")
            return json.loads(exact_result)
        
        # Try semantic similarity search
        embedding = _get_text_embedding(text)
        if embedding is None:
            return None
        
        # Get all cached embeddings
        emb_key = f"{_cache_embeddings_key}:{key}"
        cached_emb_json = await r.get(emb_key)
        
        if not cached_emb_json:
            return None
        
        cached_embeddings = json.loads(cached_emb_json)
        
        best_match_idx = -1
        best_similarity = 0.0
        
        for idx, cached_emb in enumerate(cached_embeddings):
            sim = _cosine_similarity(embedding, np.array(cached_emb))
            if sim > best_similarity:
                best_similarity = sim
                best_match_idx = idx
        
        if best_match_idx >= 0 and best_similarity >= _similarity_threshold:
            data_key = f"{_cache_key_prefix}{key}:{best_match_idx}"
            result = await r.get(data_key)
            if result:
                logger.info(f"Semantic cache hit (similarity={best_similarity:.3f}) for key {key}")
                return json.loads(result)
        
    except Exception as e:
        logger.warning(f"Semantic cache get error: {e}")
    
    return None


async def semantic_set(key: str, text: str, value: Any, ttl: int = 86400) -> bool:
    """
    Cache response with semantic embedding for future similarity searches.
    """
    if not USE_EMBEDDINGS:
        return False
    
    from api.redis_client import get_redis
    
    try:
        r = await get_redis()
        
        # Store exact match
        exact_key = f"{_cache_key_prefix}exact:{_hash_text(text)}"
        await r.setex(exact_key, ttl, json.dumps(value, default=str))
        
        # Store with embedding
        embedding = _get_text_embedding(text)
        if embedding is None:
            return True  # Exact match already stored
        
        emb_key = f"{_cache_embeddings_key}:{key}"
        
        # Get existing embeddings
        cached_emb_json = await r.get(emb_key)
        cached_embeddings = json.loads(cached_emb_json) if cached_emb_json else []
        
        # Add new embedding
        cached_embeddings.append(embedding.tolist())
        
        # Limit cache size to 100 entries per key
        if len(cached_embeddings) > 100:
            cached_embeddings = cached_embeddings[-100:]
        
        # Save embeddings
        await r.setex(emb_key, ttl, json.dumps(cached_embeddings))
        
        # Store the value
        data_key = f"{_cache_key_prefix}{key}:{len(cached_embeddings) - 1}"
        await r.setex(data_key, ttl, json.dumps(value, default=str))
        
        logger.debug(f"Stored in semantic cache: {key}")
        return True
        
    except Exception as e:
        logger.warning(f"Semantic cache set error: {e}")
        return False


async def semantic_delete(key: str) -> bool:
    """Delete all cached entries for a key."""
    if not USE_EMBEDDINGS:
        return False
    
    from api.redis_client import get_redis
    
    try:
        r = await get_redis()
        emb_key = f"{_cache_embeddings_key}:{key}"
        await r.delete(emb_key)
        
        # Also delete exact matches for this key pattern
        pattern = f"{_cache_key_prefix}{key}:*"
        keys = await r.keys(pattern)
        for k in keys:
            await r.delete(k)
        
        return True
    except Exception as e:
        logger.warning(f"Semantic cache delete error: {e}")
        return False
