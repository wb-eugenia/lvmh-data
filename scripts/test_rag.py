"""
Script de test RAG (Retrieval Augmented Generation) simplifié.
Objectif : Tester la capacité à retrouver le bon produit LVMH à partir d'une description floue.

Méthode : TF-IDF + Cosine Similarity (Suffisant pour < 1000 produits)
"""

import json
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def load_catalog(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_search_engine(products):
    """Crée un index vectoriel simple (TF-IDF)"""
    # On combine les champs pertinents pour la recherche
    corpus = [
        f"{p['name']} {p['category']} {p['color']} {p['material']} {p['description']}" 
        for p in products
    ]
    
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(corpus)
    
    return vectorizer, tfidf_matrix

def search_product(query, vectorizer, matrix, products, top_k=3):
    """Recherche les top_k produits les plus proches"""
    query_vec = vectorizer.transform([query])
    
    # Calcul similitude cosinus
    similarities = cosine_similarity(query_vec, matrix).flatten()
    
    # Récupérer les top indices
    top_indices = similarities.argsort()[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        score = similarities[idx]
        if score > 0.1:  # Seuil minimal de pertinence
            results.append((products[idx], score))
            
    return results

def main():
    print("🛍️  INITIALISATION DU MOTEUR RAG...\n")
    
    # 1. Charger le catalogue
    catalog_path = "data/raw/catalog_sample.json"
    if not Path(catalog_path).exists():
        print(f"❌ Erreur: {catalog_path} introuvable.")
        return

    products = load_catalog(catalog_path)
    print(f"✅ Catalogue chargé : {len(products)} produits.")
    
    # 2. Indexation
    vectorizer, matrix = create_search_engine(products)
    print("✅ Indexation vectorielle terminée.\n")
    
    # 3. Test de requêtes (Cas réels de notes vocales)
    test_queries = [
        "Elle cherche un sac noir classique en cuir grainé avec un rabat",  # Cible: Capucines ou Twist
        "Un grand cabas pour la plage en toile marron",                    # Cible: Neverfull ou Onthego
        "Une montre de plongée sportive",                                  # Cible: Tambour Street Diver
        "Le parfum qui sent l'iris et la rose",                            # Cible: Spell On You
        "Un petit sac vert chaine or"                                      # Cible: Coussin (ou Twist)
    ]
    
    print("🔎 TEST DE RECHERCHE :\n")
    
    for query in test_queries:
        print(f"🗣️  Query : '{query}'")
        results = search_product(query, vectorizer, matrix, products)
        
        if not results:
            print("   ❌ Pas de résultats pertinents found.")
        else:
            for i, (prod, score) in enumerate(results):
                match_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                print(f"   {match_icon} [{score:.2f}] {prod['name']} ({prod['sku']}) - {prod['color']}")
        print("-" * 50)

if __name__ == "__main__":
    main()
