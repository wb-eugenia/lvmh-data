"""
Cache Manager for Wave 2 Pipeline.
Provides caching for expensive operations (cleaning, RGPD, extraction).
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging


logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for pipeline operations."""
    
    def __init__(self, cache_dir: str = 'cache/wave2'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {'hits': 0, 'misses': 0}
    
    def get_cache_key(self, text: str, step: str) -> str:
        """Generate MD5 hash of text + step name."""
        content = f"{step}:{text}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_path(self, cache_key: str, step: str) -> Path:
        """Get file path for a cache key."""
        step_dir = self.cache_dir / step
        step_dir.mkdir(parents=True, exist_ok=True)
        return step_dir / f"{cache_key}.json"
    
    def load(self, cache_key: str, step: str) -> Optional[Dict]:
        """Load from cache if exists."""
        path = self._get_path(cache_key, step)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.stats['hits'] += 1
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Cache read error for {cache_key}: {e}")
                return None
        self.stats['misses'] += 1
        return None
    
    def save(self, cache_key: str, step: str, result: Dict) -> None:
        """Save to cache."""
        path = self._get_path(cache_key, step)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
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
        result['from_cache'] = False
        self.save(cache_key, step, result)
        return result
    
    def clear(self, step: Optional[str] = None) -> int:
        """Clear cache. If step is specified, only clear that step."""
        count = 0
        if step:
            step_dir = self.cache_dir / step
            if step_dir.exists():
                for f in step_dir.glob('*.json'):
                    f.unlink()
                    count += 1
        else:
            for step_dir in self.cache_dir.iterdir():
                if step_dir.is_dir():
                    for f in step_dir.glob('*.json'):
                        f.unlink()
                        count += 1
        return count
    
    def report(self) -> str:
        """Generate cache stats report."""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total * 100 if total > 0 else 0
        return f"""
📦 CACHE STATS:
Hits: {self.stats['hits']:,}
Misses: {self.stats['misses']:,}
Hit Rate: {hit_rate:.1f}%
"""
