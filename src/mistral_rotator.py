"""
Mistral API Key Rotator
Handles multiple Mistral student accounts for higher quotas.
"""

import os
import random
import logging
from typing import List, Optional
from functools import lru_cache
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

logger = logging.getLogger(__name__)


class MistralKeyRotator:
    """Rotates between multiple Mistral API keys."""
    
    def __init__(self):
        self._keys: List[str] = []
        self._current_index = 0
        self._load_keys()
    
    def _load_keys(self):
        """Load all available Mistral keys from environment."""
        key1 = os.getenv("MISTRAL_API_KEY", "").strip()
        key2 = os.getenv("MISTRAL_API_KEY_2", "").strip()
        key3 = os.getenv("MISTRAL_API_KEY_3", "").strip()
        
        self._keys = [k for k in [key1, key2, key3] if k]
        
        if len(self._keys) == 0:
            logger.warning("No Mistral API keys configured")
        elif len(self._keys) == 1:
            logger.info(f"Using 1 Mistral API key")
        else:
            logger.info(f"Using {len(self._keys)} Mistral API keys (rotation enabled)")
    
    def get_key(self) -> Optional[str]:
        """Get current key."""
        if not self._keys:
            return None
        return self._keys[self._current_index]
    
    def rotate(self) -> Optional[str]:
        """Rotate to next key and return it."""
        if not self._keys:
            return None
        
        self._current_index = (self._current_index + 1) % len(self._keys)
        key = self._keys[self._current_index]
        logger.debug(f"Rotated to Mistral key {self._current_index + 1}/{len(self._keys)}")
        return key
    
    def get_random_key(self) -> Optional[str]:
        """Get a random key (for parallel requests)."""
        if not self._keys:
            return None
        return random.choice(self._keys)
    
    @property
    def key_count(self) -> int:
        return len(self._keys)


@lru_cache()
def get_mistral_rotator() -> MistralKeyRotator:
    """Get singleton rotator instance."""
    return MistralKeyRotator()


def get_mistral_key() -> Optional[str]:
    """Convenience function to get current Mistral key."""
    return get_mistral_rotator().get_key()
