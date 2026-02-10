import pytest
import pandas as pd
import numpy as np
import os
import shutil
from src.embedding_viz import EmbeddingVisualizer
from src.embedding_cache import EmbeddingCache

# Simple dummy encoder to avoid downloading models during tests
class DummyModel:
    def encode(self, texts, show_progress_bar=False, batch_size=32):
        return np.random.rand(len(texts), 384)

# Setup fixture for temporary cache
@pytest.fixture
def temp_cache_dir():
    cache_dir = "tests/temp_cache"
    os.makedirs(cache_dir, exist_ok=True)
    yield cache_dir
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

def test_embeddings_generation(temp_cache_dir):
    """Test génération embeddings sur mini dataset"""
    df = pd.DataFrame({
        'ID': ['CA_001', 'CA_002'],
        'Transcription': ['Client passionné golf', 'Cliente végane cherche sac'],
        'Language': ['FR', 'FR']
    })
    
    # Use a small model for testing speed if possible, or mock
    # Here we use the default but it might be slow on first run. 
    # For CI/CD we would mock SentenceTransformer.
    viz = EmbeddingVisualizer()
    viz._model = DummyModel()
    viz.cache = EmbeddingCache(cache_dir=temp_cache_dir)
    
    embeddings = viz.generate_embeddings(df)
    
    assert embeddings.shape[0] == 2
    assert embeddings.shape[1] == 384  # MiniLM dimension
    
    # Test caching
    # Second call should be instant/cached
    embeddings_2 = viz.generate_embeddings(df)
    np.testing.assert_array_equal(embeddings, embeddings_2)

def test_umap_reduction():
    """Test réduction UMAP"""
    if os.getenv("RUN_SLOW_TESTS") != "1":
        pytest.skip("UMAP is slow to initialize. Set RUN_SLOW_TESTS=1 to run.")
    # Create random embeddings
    embeddings = np.random.rand(10, 384)
    
    viz = EmbeddingVisualizer()
    coords = viz.reduce_dimensions(embeddings, n_components=3)
    
    assert coords.shape == (10, 3)

def test_clustering():
    """Test clustering KMeans"""
    embeddings = np.random.rand(20, 384)
    
    viz = EmbeddingVisualizer()
    clusters = viz.discover_profiles(embeddings, n_clusters=3)
    
    assert len(clusters) == 20
    assert len(set(clusters)) <= 3 # Might be less if data is weird, but usually 3
    assert max(clusters) < 3

def test_small_dataset_handling():
    """Test handling of datasets smaller than n_clusters"""
    embeddings = np.random.rand(4, 384)
    
    viz = EmbeddingVisualizer()
    # Request 6 clusters for 4 points -> should reduce n_clusters
    clusters = viz.discover_profiles(embeddings, n_clusters=6)
    
    assert len(clusters) == 4
    # Should have at most 2 clusters (max(2, 4//2))
    assert len(set(clusters)) <= 2
