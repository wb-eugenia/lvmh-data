import pickle
import hashlib
import os
from pathlib import Path
from typing import Optional, Any

class EmbeddingCache:
    """Cache embeddings pour éviter re-calculs coûteux."""
    
    def __init__(self, cache_dir: str = 'cache/embeddings'):
        """
        Initialize the embedding cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_key(self, df: Any, model_name: str) -> str:
        """
        Generate a unique cache key based on dataframe content and model name.
        
        Args:
            df: Pandas DataFrame containing transcriptions
            model_name: Name of the model used for embeddings
            
        Returns:
            MD5 hash string
        """
        # Create a signature based on the content of transcriptions and the model
        # We use the concatenation of all transcriptions + model name
        if 'Transcription' not in df.columns:
            raise KeyError("DataFrame must contain 'Transcription' column")
            
        content = ''.join(df['Transcription'].astype(str).tolist()) + model_name
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def load(self, cache_key: str) -> Optional[Any]:
        """
        Load embeddings from cache if they exist.
        
        Args:
            cache_key: The unique cache key
            
        Returns:
            Cached embeddings or None if not found
        """
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                return None
        return None
    
    def save(self, cache_key: str, embeddings: Any) -> None:
        """
        Save embeddings to cache.
        
        Args:
            cache_key: The unique cache key
            embeddings: The embeddings object to save
        """
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(embeddings, f)
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")
