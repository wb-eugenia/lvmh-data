"""
RAG Product Matching Test Script
Tests the FAISS-based product matcher with real queries.

Usage:
    python scripts/test_rag.py                           # Run tests
    python scripts/test_rag.py --rebuild                  # Rebuild index
    python scripts/test_rag.py -q "black leather bag"    # Custom query
"""

import argparse
import sys
import os
import json
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.product_matcher import ProductMatcher


def run_tests():
    """Run sample queries against the RAG system."""
    print("🛍️  RAG PRODUCT MATCHING TEST\n")
    
    matcher = ProductMatcher()
    
    if not matcher.is_ready():
        print("❌ RAG index not ready. Run with --rebuild first.")
        return
    
    test_queries = [
        "Elle cherche un sac noir classique en cuir grainé avec un rabat",
        "Un grand cabas pour la plage en toile marron",
        "Une montre de plongée sportive",
        "Le parfum qui sent l'iris et la rose",
        "Un petit sac vert chaîne or",
        "Je voudrais une robe noire pour le mariage",
        "Des baskets homme en cuir blanc",
        "Ceinture cuir noir avec boucle dorée",
    ]
    
    results_summary = []
    
    for query in test_queries:
        print(f"\n🗣️  Query: '{query}'")
        results = matcher.match(query, top_k=3)
        
        if not results:
            print("   ❌ No matches found")
        else:
            for i, r in enumerate(results):
                score = r.get('score', 0)
                name = r.get('name', 'Unknown')
                sku = r.get('sku', '')
                price = r.get('price_eur', 0)
                
                match_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                print(f"   {match_icon} [{score:.2f}] {name}")
                print(f"       SKU: {sku} | Price: {price:.2f}€")
        
        results_summary.append({'query': query, 'results': results})
    
    return results_summary


def rebuild_index():
    """Rebuild the FAISS vector index."""
    print("🔨 Rebuilding RAG index...")
    
    matcher = ProductMatcher()
    
    try:
        success = matcher.rebuild_index()
        if success:
            print("✅ RAG index rebuilt successfully")
        else:
            print("❌ Failed to rebuild index")
    except Exception as e:
        print(f"❌ Error rebuilding index: {e}")


def custom_query(query: str):
    """Run a custom query."""
    print(f"\n🗣️  Custom Query: '{query}'")
    
    matcher = ProductMatcher()
    
    if not matcher.is_ready():
        print("❌ RAG index not ready. Run with --rebuild first.")
        return
    
    results = matcher.match(query, top_k=5)
    
    if not results:
        print("   ❌ No matches found")
        return
    
    print(f"\n📦 Top {len(results)} Results:\n")
    for i, r in enumerate(results):
        score = r.get('score', 0)
        name = r.get('name', 'Unknown')
        sku = r.get('sku', '')
        price = r.get('price_eur', 0)
        cat1 = r.get('category1', '')
        
        print(f"  {i+1}. {name}")
        print(f"     SKU: {sku} | Category: {cat1} | Price: {price:.2f}€")
        print(f"     Score: {score:.2f}\n")


def main():
    parser = argparse.ArgumentParser(description='Test RAG product matching')
    parser.add_argument('-q', '--query', type=str, help='Run custom query')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild FAISS index')
    parser.add_argument('-o', '--output', default='outputs/rag_test_results.json',
                       help='Output file for test results')
    
    args = parser.parse_args()
    
    if args.rebuild:
        rebuild_index()
        return
    
    if args.query:
        custom_query(args.query)
        return
    
    results = run_tests()
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()
