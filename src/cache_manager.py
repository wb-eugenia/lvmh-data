"""
Smart Cache Manager for Pipeline.
Features:
- Normalization (lowercase, strip, punctuation removal)
- TTL (Time To Live) support
- JSON persistence
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config.production import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages caching for pipeline operations.
    """
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {'hits': 0, 'misses': 0}
        self.ttl = settings.cache_ttl_seconds
        # Salt cache keys by pipeline/taxonomy version to prevent stale-cache drift in production.
        self.key_salt = settings.cache_key_salt
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent hashing."""
        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def get_cache_key(self, text: str, step: str) -> str:
        """Generate MD5 hash of normalized text + step name."""
        normalized = self._normalize_text(text)
        content = f"{self.key_salt}:{step}:{normalized}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_path(self, cache_key: str, step: str) -> Path:
        """Get file path for a cache key."""
        step_dir = self.cache_dir / step
        step_dir.mkdir(parents=True, exist_ok=True)
        return step_dir / f"{cache_key}.json"
    
    def load(self, cache_key: str, step: str) -> Optional[Dict]:
        """Load from cache if exists and not expired."""
        path = self._get_path(cache_key, step)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Check TTL
                cached_time = data.get('_cached_at', 0)
                if time.time() - cached_time > self.ttl:
                    return None
                
                self.stats['hits'] += 1
                return data['payload']
                
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")
                return None
        
        self.stats['misses'] += 1
        return None
    
    def save(self, cache_key: str, step: str, result: Dict) -> None:
        """Save to cache with timestamp."""
        path = self._get_path(cache_key, step)
        
        # Wrap payload with metadata
        data = {
            '_cached_at': time.time(),
            'payload': result
        }
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"Cache write error for {cache_key}: {e}")
    
    def get_or_compute(self, text: str, step: str, compute_fn) -> Dict:
        """Get from cache or compute and cache."""
        cache_key = self.get_cache_key(text, step)
        cached = self.load(cache_key, step)
        
        if cached is not None:
            cached['from_cache'] = True
            return cached
        
        result = compute_fn()
        # Ensure result is dict (if Pydantic model, convert)
        if hasattr(result, 'model_dump'):
            payload = result.model_dump(mode='json')
        elif hasattr(result, 'dict'):
            payload = result.dict()
        else:
            payload = result
            
        payload['from_cache'] = False
        self.save(cache_key, step, payload)
        return payload
    
    def report(self) -> str:
        """Generate cache stats report."""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total * 100 if total > 0 else 0
        return f"Hits: {self.stats['hits']} | Misses: {self.stats['misses']} | Rate: {hit_rate:.1f}%"
