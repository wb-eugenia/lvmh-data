import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sentence_transformers import SentenceTransformer
import umap
from sklearn.cluster import KMeans
from typing import Dict, List, Optional, Tuple, Any
import os

from .embedding_cache import EmbeddingCache

class EmbeddingVisualizer:
    """Crée visualisation 3D de l'espace clients via embeddings"""
    
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """
        Initialize the visualizer.
        
        Args:
            model_name: SentenceTransformer model name
        """
        self.model_name = model_name
        # Lazy loading of model to avoid overhead if not used
        self._model = None
        self.cache = EmbeddingCache()
        
    @property
    def model(self):
        if self._model is None:
            print(f"🔄 Loading model {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
        return self._model
        
    def generate_embeddings(self, df: pd.DataFrame) -> np.ndarray:
        """
        Encode transcriptions en vecteurs with caching.
        
        Args:
            df: DataFrame with 'Transcription' column
            
        Returns:
            Numpy array of embeddings
        """
        # Validation input
        if df.empty:
            raise ValueError("DataFrame vide, impossible de générer embeddings")
        
        if 'Transcription' not in df.columns:
            raise KeyError("Colonne 'Transcription' manquante dans le dataset")
        
        # Filtre notes vides but keep index alignment? 
        # For simplicity in this version, we assume df is clean or we handle alignment later.
        # Ideally we should return embeddings for the exact rows in df.
        
        # Check cache first
        cache_key = self.cache.get_cache_key(df, self.model_name)
        cached = self.cache.load(cache_key)
        
        if cached is not None:
            print("✅ Embeddings chargés du cache")
            return cached
        
        print("🔄 Génération embeddings (première fois)...")
        transcriptions = df['Transcription'].astype(str).tolist()
        embeddings = self.model.encode(
            transcriptions, 
            show_progress_bar=True,
            batch_size=32
        )
        
        # Sauvegarde cache
        self.cache.save(cache_key, embeddings)
        return embeddings
    
    def reduce_dimensions(self, embeddings: np.ndarray, n_components: int = 3) -> np.ndarray:
        """
        Réduit à 3D avec UMAP.
        
        Args:
            embeddings: High-dimensional embeddings
            n_components: Number of dimensions to reduce to
            
        Returns:
            Reduced embeddings
        """
        print("🔄 Réduction dimensionnelle UMAP...")
        
        # Handle small datasets
        n_samples = embeddings.shape[0]
        n_neighbors = min(15, n_samples - 1) if n_samples > 1 else 1
        
        if n_samples < 3:
             # Fallback for very small datasets (just for code to run, though 3D viz needs >3 points usually)
             return embeddings[:, :n_components] if embeddings.shape[1] >= n_components else np.pad(embeddings, ((0,0), (0, n_components-embeddings.shape[1])))

        reducer = umap.UMAP(
            n_components=n_components,
            random_state=42,
            n_neighbors=n_neighbors,
            min_dist=0.1
        )
        coords = reducer.fit_transform(embeddings)
        return coords
    
    def discover_profiles(self, embeddings: np.ndarray, n_clusters: int = 6) -> np.ndarray:
        """
        Clustering automatique pour découvrir profils.
        
        Args:
            embeddings: Embeddings array
            n_clusters: Number of clusters
            
        Returns:
            Cluster labels
        """
        # Adjust clusters for small datasets
        n_samples = embeddings.shape[0]
        if n_samples < n_clusters:
            n_clusters = max(2, n_samples // 2)
            print(f"⚠️ Dataset too small, reducing to {n_clusters} clusters")
            
        if n_clusters < 2:
            return np.zeros(n_samples, dtype=int)
            
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(embeddings)
        return clusters

    def analyze_cluster_characteristics(self, df: pd.DataFrame, clusters: np.ndarray) -> Dict[str, Any]:
        """
        Analyse tags dominants par cluster.
        
        Args:
            df: Original DataFrame
            clusters: Cluster labels
            
        Returns:
            Dictionary of cluster insights
        """
        # Create a copy to avoid modifying original
        work_df = df.copy()
        work_df['Cluster'] = clusters
        
        profile_insights = {}
        unique_clusters = sorted(list(set(clusters)))
        
        for cluster_id in unique_clusters:
            cluster_df = work_df[work_df['Cluster'] == cluster_id]
            
            # Tags les plus fréquents dans ce cluster
            all_tags = []
            if 'tags' in cluster_df.columns:
                 for tags_list in cluster_df['tags']:
                     if isinstance(tags_list, list):
                         all_tags.extend(tags_list)
                     elif isinstance(tags_list, str):
                         # Handle string representation if necessary
                         try:
                             import ast
                             if tags_list.startswith('['):
                                 all_tags.extend(ast.literal_eval(tags_list))
                             else:
                                 all_tags.append(tags_list)
                         except:
                             pass

            tag_freq = pd.Series(all_tags).value_counts()
            
            # Budget moyen (heuristic)
            dominant_budget = "N/A"
            if 'budget_range' in cluster_df.columns:
                budgets = cluster_df['budget_range'].value_counts()
                if not budgets.empty:
                    dominant_budget = budgets.index[0]
            
            # Avg confidence
            avg_conf = 0.0
            if 'confidence' in cluster_df.columns:
                avg_conf = cluster_df['confidence'].mean()
            
            profile_insights[f"Profil {cluster_id + 1}"] = {
                'size': len(cluster_df),
                'top_tags': tag_freq.head(5).to_dict(),
                'dominant_budget': dominant_budget,
                'avg_confidence': avg_conf
            }
        
        return profile_insights
    
    def create_interactive_viz(
        self, 
        df: pd.DataFrame, 
        coords_3d: np.ndarray, 
        clusters: Optional[np.ndarray] = None,
        output_path: str = 'outputs/client_space_3d.html'
    ) -> go.Figure:
        """
        Crée viz Plotly interactive.
        
        Args:
            df: DataFrame containing metadata
            coords_3d: 3D coordinates from UMAP
            clusters: Optional cluster labels
            output_path: Path to save HTML
            
        Returns:
            Plotly Figure
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Prepare color data
        if clusters is not None:
            color_data = clusters
            color_label = "Cluster"
            colorscale = 'Turbo'
        else:
            color_data = df.get('confidence', np.zeros(len(df)))
            color_label = "Confiance"
            colorscale = 'Viridis'
            
        # Format tags for display
        display_tags = []
        if 'tags' in df.columns:
            for t in df['tags']:
                if isinstance(t, list):
                    display_tags.append(", ".join(t[:5]) + ("..." if len(t)>5 else ""))
                else:
                    display_tags.append(str(t)[:50])
        else:
            display_tags = [""] * len(df)

        # Prépare données pour viz
        viz_df = pd.DataFrame({
            'x': coords_3d[:, 0],
            'y': coords_3d[:, 1],
            'z': coords_3d[:, 2],
            'ID': df.get('client_id', df.index), # Fallback to index if no ID
            'Language': df.get('language', df.get('Language', 'N/A')),
            'Tags': display_tags,
            'Confidence': df.get('confidence', 0.0),
            'Budget': df.get('budget_range', 'N/A'),
            'Status': df.get('client_status', 'N/A'),
            'Color': color_data
        })
        
        # Viz 3D interactive
        fig = go.Figure(data=[go.Scatter3d(
            x=viz_df['x'],
            y=viz_df['y'],
            z=viz_df['z'],
            mode='markers',
            marker=dict(
                size=5,
                color=viz_df['Color'],
                colorscale=colorscale,
                showscale=True,
                colorbar=dict(title=color_label),
                line=dict(width=0.5, color='white'),
                opacity=0.8
            ),
            text=[
                f"<b>{row['ID']}</b><br>" +
                f"Langue: {row['Language']}<br>" +
                f"Tags: {row['Tags']}<br>" +
                f"Budget: {row['Budget']}<br>" +
                f"Status: {row['Status']}"
                for _, row in viz_df.iterrows()
            ],
            hoverinfo='text'
        )])
        
        fig.update_layout(
            title={
                'text': "Espace Clients LVMH - Voice to Tag<br><sub>Visualisation 3D via Embeddings Multilingues</sub>",
                'x': 0.5,
                'xanchor': 'center'
            },
            scene=dict(
                xaxis_title='Dimension 1',
                yaxis_title='Dimension 2',
                zaxis_title='Dimension 3',
                bgcolor='rgba(0,0,0,0)'
            ),
            width=1200,
            height=800,
            hovermode='closest',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Helvetica Neue', color='#333333')
        )
        
        # Sauvegarde
        fig.write_html(output_path)
        print(f"✅ Visualisation sauvegardée: {output_path}")
        return fig
