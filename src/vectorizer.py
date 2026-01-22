"""
Tag Classifier based on Mistral AI Embeddings.
Maps simple tags to taxonomy categories using cosine similarity.
"""

import json
import os
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path

from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

class TagClassifier:
    """Classifies free-text tags into taxonomy using embeddings."""
    
    def __init__(
        self, 
        taxonomy_path: str = "config/taxonomy_v2.json",
        model: str = "mistral-embed",
        similarity_threshold: float = 0.35, # Slightly lower for Mistral
        api_key: str = None
    ):
        self.model = model
        self.similarity_threshold = similarity_threshold
        
        # Initialize Mistral client
        api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY needed for embeddings")
            
        self.client = Mistral(api_key=api_key)
        
        # Load taxonomy
        with open(taxonomy_path, 'r', encoding='utf-8') as f:
            tax_content = json.load(f)
            
        # Handle if tax_content is dict (expected) or something else
        if isinstance(tax_content, dict):
            self.categories = tax_content.get('categories', {})
        else:
            raise ValueError(f"Invalid taxonomy format in {taxonomy_path}")
        
        # Precompute embeddings only once
        self._flatten_taxonomy()
        self._compute_taxonomy_embeddings()
        
    def _flatten_taxonomy(self):
        """Flatten taxonomy into a list of (category, subcategory, description/example) items."""
        self.flat_items = []
        
        for cat_name, cat_data in self.categories.items():
            subcategories = cat_data.get('subcategories', {})
            
            for sub_name, sub_data in subcategories.items():
                description = sub_data.get('description', '')
                examples = sub_data.get('examples', [])
                
                # Combine info for rich embedding
                # "Category > Subcategory: Description. Examples: A, B, C."
                text = f"{cat_name} > {sub_name}: {description}. Examples: {', '.join(examples)}"
                
                self.flat_items.append({
                    "category": cat_name,
                    "sub_category": sub_name,
                    "text": text,
                    "examples": examples
                })
                
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text using Mistral."""
        embeddings_batch_response = self.client.embeddings.create(
            model=self.model,
            inputs=[text],
        )
        return embeddings_batch_response.data[0].embedding
        
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts."""
        embeddings_batch_response = self.client.embeddings.create(
            model=self.model,
            inputs=texts,
        )
        return [d.embedding for d in embeddings_batch_response.data]

    def _compute_taxonomy_embeddings(self):
        """Compute embeddings for all taxonomy items."""
        texts = [item['text'] for item in self.flat_items]
        
        # Compute in one batch for efficiency
        self.reference_embeddings = self._get_embeddings_batch(texts)
        self.reference_embeddings = np.array(self.reference_embeddings)

    def classify_tag(self, tag: str) -> Dict:
        """
        Classify a single tag into the best matching taxonomy concept.
        """
        # Get tag embedding
        tag_embedding = np.array(self._get_embedding(tag))
        
        # Compute cosine similarities
        # similarity = (A . B) / (||A|| * ||B||)
        # Since sklearn defaults to normalized vectors if desired, but here let's do manual dot product
        # Assuming Mistral embeddings are NOT normalized by default, we should normalize.
        
        norm_tag = np.linalg.norm(tag_embedding)
        norm_refs = np.linalg.norm(self.reference_embeddings, axis=1)
        
        similarities = np.dot(self.reference_embeddings, tag_embedding) / (norm_refs * norm_tag)
        
        # Find best match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        
        if best_score >= self.similarity_threshold:
            match = self.flat_items[best_idx]
            return {
                "tag": tag,
                "category": match["category"],
                "sub_category": match["sub_category"],
                "score": float(best_score),
                "status": "classified"
            }
        else:
            return {
                "tag": tag,
                "category": "Uncategorized",
                "sub_category": "Other",
                "score": float(best_score),
                "status": "below_threshold"
            }

if __name__ == "__main__":
    # Test
    try:
        classifier = TagClassifier()
        print("✅ Classifier loaded successfully")
        
        test_tag = "Budget 5000 euros"
        result = classifier.classify_tag(test_tag)
        print(f"Test '{test_tag}': {result['category']} > {result['sub_category']} ({result['score']:.2f})")
    except Exception as e:
        print(f"❌ Error: {e}")
