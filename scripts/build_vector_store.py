"""
Script de Construction du Vector Store (RAG) avec des vraies données LV.
Source Data: hf://datasets/DBQ/Louis.Vuitton.Product.prices.France
Model: paraphrase-multilingual-MiniLM-L12-v2 (Supporte FR/EN/IT...)
"""

import os
import time
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer

def load_real_dataset():
    """Télécharge le dataset LV depuis HuggingFace (via Pandas directement)"""
    print("📥 Téléchargement du dataset LV...")
    url = "hf://datasets/DBQ/Louis.Vuitton.Product.prices.France/data/train-00000-of-00001-7dd58d9660ecce43.parquet"
    df = pd.read_parquet(url)
    print(f"✅ Dataset chargé: {len(df)} produits trouvés.")
    
    # Nettoyage basique
    # On crée une colonne 'full_description' pour l'embedding
    # On ne sait pas exactement quelles sont les colonnes, on va supposer 'name', 'description', 'price'
    # Mais par sécurité on concatène tout ce qui est texte.
    
    # Inspection rapide des colonnes (pour le log)
    print(f"Colonnes disponibles: {df.columns.tolist()}")
    
    # Afficher les 3 premières lignes pour voir la structure
    print("\n🧐 Aperçu des données brutes (3 premiers):")
    print(df.head(3).to_string())
    
    return df

def build_embeddings(df):
    """Génère les embeddings vectoriels"""
    print("\n🧠 Chargement du modèle SentenceTransformer (Multilingue)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # Préparation du corpus
    # On combine Titre + Description si possible
    print("⚙️ Préparation du corpus...")
    
    # Adaptation dynamique aux colonnes du vrai dataset
    # On cherche les colonnes qui semblent contenir du texte utile
    potential_text_cols = ['name', 'title', 'description', 'product_name', 'model', 'category', 'details']
    text_columns = [col for col in df.columns if col.lower() in potential_text_cols or df[col].dtype == 'object']
    
    print(f"   Utilisation des colonnes texte pour l'embedding: {text_columns}")
    
    # Création d'une description riche pour l'embedding
    corpus = df[text_columns].apply(lambda x: ' '.join(x.dropna().astype(str)), axis=1).tolist()
    
    print(f"🚀 Génération des embeddings pour {len(corpus)} produits (ça peut prendre 1-2 min)...")
    start = time.time()
    embeddings = model.encode(corpus, show_progress_bar=True)
    elapsed = time.time() - start
    
    print(f"✅ Embeddings générés en {elapsed:.1f}s. Shape: {embeddings.shape}")
    
    return model, corpus, embeddings

def semantic_search(query, model, embeddings, df, top_k=5):
    """Recherche sémantique par Cosine Similarity"""
    query_vec = model.encode([query])
    
    # Cosine Similarity manuel (rapide et simple)
    # A . B / (|A| * |B|)
    # Les embeddings de SentenceTransformer sont souvent déjà normalisés, mais on assure.
    
    # Normalisation
    norm_embed = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    norm_query = query_vec / np.linalg.norm(query_vec, axis=1, keepdims=True)
    
    # Produit scalaire
    similarities = np.dot(norm_query, norm_embed.T).flatten()
    
    # Top K
    top_indices = similarities.argsort()[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        results.append({
            'score': similarities[idx],
            'product': df.iloc[idx].to_dict()
        })
    return results

def main():
    # 1. Load Data
    try:
        df = load_real_dataset()
    except Exception as e:
        print(f"❌ Erreur chargement dataset: {e}")
        return

    # 2. Vectorize
    model, corpus, embeddings = build_embeddings(df)
    
    # 3. Save Index (Optionnel mais recommandé pour la prod)
    os.makedirs('data/vector_store', exist_ok=True)
    with open('data/vector_store/lv_index.pkl', 'wb') as f:
        pickle.dump({'embeddings': embeddings, 'df': df}, f)
    print("💾 Index sauvegardé dans data/vector_store/lv_index.pkl")
    
    # 4. Test Interactif
    test_queries = [
        "J'ai besoin d'un sac noir élégant pour le travail, assez grand",
        "Une montre connectée pour le sport",
        "Un parfum floral léger",
        "Le sac iconique avec le damier",
        "Un petit accessoire pas cher pour un cadeau"
    ]
    
    print("\n🔎 DÉBUT DES TESTS RAG (Sémantique) :\n")
    
    for query in test_queries:
        print(f"🗣️  Clients dit: '{query}'")
        results = semantic_search(query, model, embeddings, df)
        
        for i, res in enumerate(results):
            score = res['score']
            prod = res['product']
            
            # On essaye de trouver le nom le plus pertinent
            # Inspection des clés disponibles dans le produit
            keys = prod.keys()
            name_candidates = ['title', 'name', 'product_name', 'model', 'description']
            
            product_name = "Inconnu"
            for key in name_candidates:
                # On cherche une clé qui matche (insensible à la casse)
                match = next((k for k in keys if k.lower() == key), None)
                if match and prod[match]:
                    product_name = prod[match]
                    break
            
            # Si toujours "Louis Vuitton", on prend la description courte ou on coupe le titre
            if product_name == "Louis Vuitton" and 'description' in keys:
                 product_name = prod['description'][:50] + "..."
            
            price = prod.get('price', prod.get('Price', 'N/A'))
            
            print(f"   [{score:.2f}] {product_name} ({price})")
        print("-" * 50)

if __name__ == "__main__":
    main()
