"""
Tier 2: Local NLP Tag Extraction.
Uses embeddings + similarity for mid-complexity notes.
Cost: 0€ | Speed: ~1.5s/note | Precision: 82-85%
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

# Lazy imports for performance
_sentence_transformer = None
_spacy_nlp = None


def get_sentence_transformer():
    """Lazy load sentence transformer."""
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
    return _sentence_transformer


def get_spacy():
    """Lazy load spaCy with multilingual model."""
    global _spacy_nlp
    if _spacy_nlp is None:
        import spacy
        try:
            _spacy_nlp = spacy.load('xx_ent_wiki_sm')  # Multilingual
        except OSError:
            print("Installing spaCy model...")
            os.system('python -m spacy download xx_ent_wiki_sm')
            _spacy_nlp = spacy.load('xx_ent_wiki_sm')
    return _spacy_nlp


@dataclass
class Tier2Result:
    """Result from Tier 2 NLP extraction."""
    tags: List[str]
    tag_scores: Dict[str, float]
    budget_range: Optional[str]
    keywords: List[str]
    confidence: float
    extracted_by: str = "tier2_nlp"


class Tier2NLPEngine:
    """
    NLP-based tag extraction using embeddings.
    
    Uses:
    - SentenceTransformer for semantic similarity
    - Pre-computed taxonomy embeddings
    - Cosine similarity matching
    """
    
    SIMILARITY_THRESHOLD = 0.45  # Minimum cosine similarity for tag match
    TOP_K_TAGS = 10  # Maximum tags to return
    
    def __init__(self, taxonomy_path: str = 'config/taxonomy_v2.json'):
        self.taxonomy_path = taxonomy_path
        self.taxonomy = self._load_taxonomy()
        self.tag_embeddings = None
        self.tag_names = []
        self._embeddings_loaded = False
    
    def _load_taxonomy(self) -> Dict:
        """Load taxonomy from JSON."""
        if os.path.exists(self.taxonomy_path):
            with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _get_tag_descriptions(self) -> Dict[str, str]:
        """Extract tag names and descriptions for embedding."""
        descriptions = {}
        
        for category, data in self.taxonomy.items():
            if isinstance(data, dict) and 'subcategories' in data:
                for subcat in data['subcategories']:
                    if isinstance(subcat, dict):
                        tag = subcat.get('tag', '')
                        desc = subcat.get('description', tag)
                        if tag:
                            descriptions[tag] = f"{category}: {desc}"
        
        return descriptions
    
    def load_embeddings(self, force_recompute: bool = False):
        """Load or compute taxonomy embeddings."""
        cache_path = Path('cache/taxonomy_embeddings.npy')
        tags_path = Path('cache/taxonomy_tags.json')
        
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not force_recompute and cache_path.exists() and tags_path.exists():
            # Load cached
            self.tag_embeddings = np.load(cache_path)
            with open(tags_path, 'r') as f:
                self.tag_names = json.load(f)
            self._embeddings_loaded = True
            return
        
        # Compute embeddings
        print("🔄 Computing taxonomy embeddings...")
        model = get_sentence_transformer()
        
        descriptions = self._get_tag_descriptions()
        self.tag_names = list(descriptions.keys())
        texts = list(descriptions.values())
        
        if texts:
            self.tag_embeddings = model.encode(texts, convert_to_numpy=True)
            
            # Cache
            np.save(cache_path, self.tag_embeddings)
            with open(tags_path, 'w') as f:
                json.dump(self.tag_names, f)
        else:
            self.tag_embeddings = np.array([])
        
        self._embeddings_loaded = True
        print(f"✅ Computed embeddings for {len(self.tag_names)} tags")
    
    def extract_keywords_yake(self, text: str, top_k: int = 10) -> List[str]:
        """Extract keywords using YAKE."""
        try:
            import yake
            kw_extractor = yake.KeywordExtractor(
                lan="fr",  # Default French, works OK for multilingual
                n=2,  # Up to bigrams
                top=top_k
            )
            keywords = kw_extractor.extract_keywords(text)
            return [kw[0] for kw in keywords]
        except ImportError:
            # Fallback: simple word extraction
            words = text.lower().split()
            return [w for w in words if len(w) > 4][:top_k]
    
    def compute_text_embedding(self, text: str) -> np.ndarray:
        """Compute embedding for input text."""
        model = get_sentence_transformer()
        return model.encode(text, convert_to_numpy=True)
    
    def match_tags_by_similarity(self, text_embedding: np.ndarray) -> List[Tuple[str, float]]:
        """Find matching tags by cosine similarity."""
        if self.tag_embeddings is None or len(self.tag_embeddings) == 0:
            return []
        
        # Cosine similarity
        text_norm = text_embedding / np.linalg.norm(text_embedding)
        tag_norms = self.tag_embeddings / np.linalg.norm(self.tag_embeddings, axis=1, keepdims=True)
        similarities = np.dot(tag_norms, text_norm)
        
        # Filter by threshold and sort
        matches = []
        for i, score in enumerate(similarities):
            if score >= self.SIMILARITY_THRESHOLD:
                matches.append((self.tag_names[i], float(score)))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:self.TOP_K_TAGS]
    
    def extract_budget_ner(self, text: str) -> Optional[str]:
        """Extract budget using NER."""
        nlp = get_spacy()
        doc = nlp(text)
        
        # Look for money/quantity entities
        for ent in doc.ents:
            if ent.label_ in ['MONEY', 'CARDINAL', 'QUANTITY']:
                text_ent = ent.text.lower()
                # Try to parse as budget
                import re
                match = re.search(r'(\d+)', text_ent)
                if match:
                    amount = int(match.group(1))
                    if 'k' in text_ent or amount > 1000:
                        if 'k' in text_ent:
                            amount *= 1000
                        
                        if amount < 5000:
                            return 'under_5K'
                        elif amount < 10000:
                            return '5K-10K'
                        elif amount < 20000:
                            return '10K-20K'
                        else:
                            return '20K+'
        
        return None
    
    def extract(self, text: str, language: str = 'FR') -> Tier2Result:
        """
        Full Tier 2 extraction.
        
        Returns:
            Tier2Result with extracted tags and metadata
        """
        # Ensure embeddings are loaded
        if not self._embeddings_loaded:
            self.load_embeddings()
        
        # 1. Extract keywords
        keywords = self.extract_keywords_yake(text)
        
        # 2. Compute text embedding
        text_embedding = self.compute_text_embedding(text)
        
        # 3. Match tags by similarity
        tag_matches = self.match_tags_by_similarity(text_embedding)
        
        # 4. Extract budget via NER
        budget_range = self.extract_budget_ner(text)
        
        # Build result
        tags = [tag for tag, _ in tag_matches]
        tag_scores = {tag: score for tag, score in tag_matches}
        
        # Confidence based on best match score
        if tag_matches:
            confidence = min(tag_matches[0][1] + 0.15, 0.95)
        else:
            confidence = 0.50
        
        return Tier2Result(
            tags=tags,
            tag_scores=tag_scores,
            budget_range=budget_range,
            keywords=keywords,
            confidence=confidence
        )


if __name__ == "__main__":
    import pandas as pd
    
    print("🧠 Testing Tier 2 NLP Engine\n")
    
    engine = Tier2NLPEngine()
    engine.load_embeddings()
    
    # Test texts
    test_texts = [
        "Cliente avocate d'affaires, passionnée par l'art contemporain, voyage fréquemment.",
        "Médecin cardiologue, collectionne les montres, pratique le golf régulièrement.",
        "Entrepreneur tech startup, végane, intéressé par le développement durable.",
    ]
    
    for text in test_texts:
        result = engine.extract(text)
        print(f"Text: {text[:60]}...")
        print(f"Tags: {result.tags[:5]}")
        print(f"Keywords: {result.keywords[:5]}")
        print(f"Confidence: {result.confidence:.0%}")
        print()
    
    # Test on sample of Wave 2 data
    df = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
    
    print(f"\n📊 Testing on 5 notes from Wave 2...\n")
    
    for _, row in df.head(5).iterrows():
        result = engine.extract(row['Transcription'], row['Language'])
        print(f"{row['ID']}: {len(result.tags)} tags")
        print(f"  Top 3: {result.tags[:3]}")
        print(f"  Scores: {list(result.tag_scores.items())[:3]}")
        print()
