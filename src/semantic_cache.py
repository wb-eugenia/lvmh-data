"""
Semantic Cache - Caching par similarité sémantique
Réduction des coûts API par réutilisation intelligente des résultats similaires
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

# DON'T import at module level - causes Cloud Run startup timeout
# Lazy imports when needed
HAS_FAISS = None
HAS_EMBEDDINGS = None

def _check_faiss_available():
    global HAS_FAISS
    if HAS_FAISS is not None:
        return HAS_FAISS
    try:
        import faiss
        HAS_FAISS = True
    except ImportError:
        HAS_FAISS = False
        logger.warning("FAISS not available, falling back to simple cache")
    return HAS_FAISS

def _check_embeddings_available():
    global HAS_EMBEDDINGS
    if HAS_EMBEDDINGS is not None:
        return HAS_EMBEDDINGS
    try:
        from sentence_transformers import SentenceTransformer
        HAS_EMBEDDINGS = True
    except ImportError:
        HAS_EMBEDDINGS = False
        logger.warning("Sentence transformers not available")
    return HAS_EMBEDDINGS


@dataclass
class CacheEntry:
    """Entry in semantic cache"""
    text: str
    text_hash: str
    embedding: Optional[List[float]] = None
    result: Optional[Dict] = None
    tier_used: int = 0
    timestamp: str = ""
    hit_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'text': self.text,
            'text_hash': self.text_hash,
            'embedding': self.embedding,
            'result': self.result,
            'tier_used': self.tier_used,
            'timestamp': self.timestamp,
            'hit_count': self.hit_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CacheEntry':
        return cls(**data)


class SemanticCache:
    """
    Cache sémantique avec FAISS pour recherche par similarité
    
    Usage:
        cache = SemanticCache(similarity_threshold=0.92)
        
        # Check cache
        cached_result = cache.get("sac noir pour femme")
        if cached_result:
            return cached_result
            
        # Store result
        cache.store("sac noir pour femme", result, tier=2)
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.92,
        max_entries: int = 10000,
        ttl_hours: int = 168,  # 1 week
        cache_dir: str = "cache/semantic",
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir = cache_dir
        
        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize embedding model (lazy)
        self.model = None
        if _check_embeddings_available():
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"✅ Semantic cache initialized with {model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
        
        # Initialize FAISS index
        self.index = None
        self.entries: List[CacheEntry] = []
        self.dimension = 384  # Default for MiniLM-L12
        
        if _check_faiss_available() and self.model:
            self._init_faiss_index()
        
        # Load existing cache
        self._load_cache()
        
        self.stats = {
            'hits': 0,
            'misses': 0,
            'stores': 0,
            'similarity_checks': 0
        }
    
    def _init_faiss_index(self):
        """Initialize FAISS index for similarity search"""
        if not _check_faiss_available():
            return
            
        # Use IndexFlatIP (Inner Product) for cosine similarity with normalized vectors
        self.index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"✅ FAISS index initialized (dim={self.dimension})")
    
    def _load_cache(self):
        """Load cache from disk"""
        cache_file = os.path.join(self.cache_dir, "semantic_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for entry_data in data.get('entries', []):
                    entry = CacheEntry.from_dict(entry_data)
                    
                    # Check TTL
                    entry_time = datetime.fromisoformat(entry.timestamp)
                    if datetime.now() - entry_time < self.ttl:
                        self.entries.append(entry)
                        
                        # Add to FAISS index if embedding available
                        if self.index and entry.embedding:
                            vector = np.array([entry.embedding], dtype=np.float32)
                            self.index.add(vector)
                
                logger.info(f"✅ Loaded {len(self.entries)} entries from semantic cache")
                
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save cache to disk"""
        cache_file = os.path.join(self.cache_dir, "semantic_cache.json")
        try:
            data = {
                'entries': [e.to_dict() for e in self.entries],
                'stats': self.stats,
                'saved_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, default=str)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding vector for text"""
        if not self.model:
            return None
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts"""
        if not self.model:
            return 0.0
        
        emb1 = self._get_embedding(text1)
        emb2 = self._get_embedding(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        # Cosine similarity (vectors are normalized)
        return float(np.dot(emb1, emb2))
    
    def get(self, text: str, language: str = "FR") -> Optional[Dict]:
        """
        Check if similar text exists in cache
        Returns cached result if similarity >= threshold
        """
        if not text or not self.model or not self.index:
            self.stats['misses'] += 1
            return None
        
        # Get query embedding
        query_embedding = self._get_embedding(text)
        if query_embedding is None:
            self.stats['misses'] += 1
            return None
        
        self.stats['similarity_checks'] += 1
        
        # Search in FAISS index
        query_vector = np.array([query_embedding], dtype=np.float32)
        k = min(3, len(self.entries))  # Top 3 matches
        
        if k == 0:
            self.stats['misses'] += 1
            return None
        
        distances, indices = self.index.search(query_vector, k)
        
        # Check if best match is above threshold
        if distances[0][0] >= self.similarity_threshold:
            best_idx = indices[0][0]
            if 0 <= best_idx < len(self.entries):
                entry = self.entries[best_idx]
                entry.hit_count += 1
                self.stats['hits'] += 1
                
                logger.info(f"🎯 Semantic cache HIT (sim={distances[0][0]:.3f}): '{text[:50]}...' → '{entry.text[:50]}...'")
                
                # Return cached result with metadata
                result = entry.result.copy() if entry.result else {}
                result['_cache_metadata'] = {
                    'cached': True,
                    'similarity': float(distances[0][0]),
                    'original_text': entry.text,
                    'tier_used': entry.tier_used
                }
                return result
        
        self.stats['misses'] += 1
        return None
    
    def store(
        self,
        text: str,
        result: Dict,
        tier_used: int = 0,
        language: str = "FR"
    ) -> bool:
        """
        Store result in semantic cache
        """
        if not text or not self.model:
            return False
        
        # Check if cache is full
        if len(self.entries) >= self.max_entries:
            # Remove oldest entries (20%)
            self._cleanup_old_entries()
        
        # Get embedding
        embedding = self._get_embedding(text)
        if embedding is None:
            return False
        
        # Create cache entry
        entry = CacheEntry(
            text=text,
            text_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
            embedding=embedding.tolist(),
            result=result,
            tier_used=tier_used,
            timestamp=datetime.now().isoformat(),
            hit_count=0
        )
        
        self.entries.append(entry)
        
        # Add to FAISS index
        if self.index:
            vector = np.array([embedding], dtype=np.float32)
            self.index.add(vector)
        
        self.stats['stores'] += 1
        
        # Periodically save cache
        if self.stats['stores'] % 10 == 0:
            self._save_cache()
        
        return True
    
    def _cleanup_old_entries(self):
        """Remove oldest 20% of entries"""
        if not self.entries:
            return
        
        # Sort by hit count (keep popular entries) and timestamp
        self.entries.sort(key=lambda e: (e.hit_count, e.timestamp), reverse=True)
        
        # Keep 80%
        keep_count = int(self.max_entries * 0.8)
        removed = self.entries[keep_count:]
        self.entries = self.entries[:keep_count]
        
        # Rebuild FAISS index
        if self.index and _check_faiss_available():
            self._init_faiss_index()
            for entry in self.entries:
                if entry.embedding:
                    vector = np.array([entry.embedding], dtype=np.float32)
                    self.index.add(vector)
        
        logger.info(f"🧹 Cleaned up {len(removed)} old cache entries")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0.0
        
        return {
            'enabled': self.model is not None,
            'entries_count': len(self.entries),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': f"{hit_rate:.1%}",
            'similarity_threshold': self.similarity_threshold,
            'estimated_cost_saved': self.stats['hits'] * 0.002  # €0.002 per API call
        }
    
    def clear(self):
        """Clear all cache entries"""
        self.entries = []
        if self.index:
            self._init_faiss_index()
        self.stats = {'hits': 0, 'misses': 0, 'stores': 0, 'similarity_checks': 0}
        logger.info("🗑️ Semantic cache cleared")


# Singleton instance
_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Get or create semantic cache singleton"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
