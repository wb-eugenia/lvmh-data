"""
LLM-based tag extractor for LVMH Voice to Tag.
Supports OpenAI GPT-4o-mini with structured JSON output.
"""

import json
import os
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

from .taxonomy import Taxonomy
from .prompts import SYSTEM_PROMPT, get_extraction_prompt


# Load environment variables
load_dotenv()


class TagExtractor:
    """
    Extracts structured tags from transcriptions using LLM.
    """
    
    def __init__(
        self,
        taxonomy_path: str = "config/taxonomy_v1.json",
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_retries: int = 3,
        cache_dir: Optional[str] = "cache"
    ):
        """
        Initialize the tag extractor.
        
        Args:
            taxonomy_path: Path to taxonomy JSON file
            model: OpenAI model to use
            temperature: Sampling temperature (0 for deterministic)
            max_retries: Max retries on API failure
            cache_dir: Directory for caching results (None to disable)
        """
        self.taxonomy = Taxonomy(taxonomy_path)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        
        # Create cache directory if needed
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Get taxonomy summary for prompts
        self._taxonomy_summary = self.taxonomy.get_tags_summary()
    
    def _get_cache_path(self, client_id: str) -> Path:
        """Get cache file path for a client ID."""
        return self.cache_dir / f"{client_id}.json" if self.cache_dir else None
    
    def _load_from_cache(self, client_id: str) -> Optional[Dict]:
        """Load cached result if available."""
        cache_path = self._get_cache_path(client_id)
        if cache_path and cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def _save_to_cache(self, client_id: str, result: Dict) -> None:
        """Save result to cache."""
        cache_path = self._get_cache_path(client_id)
        if cache_path:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
    
    def extract(
        self,
        transcription: str,
        language: str,
        client_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract tags and metadata from a transcription.
        
        Args:
            transcription: The transcribed text
            language: Language code (FR, EN, IT, ES, DE)
            client_id: Optional client identifier
            use_cache: Whether to use cached results
            
        Returns:
            Dict with extracted tags and metadata
        """
        # Check cache first
        if use_cache and client_id:
            cached = self._load_from_cache(client_id)
            if cached:
                cached['from_cache'] = True
                return cached
        
        # Build prompt
        user_prompt = get_extraction_prompt(
            transcription=transcription,
            language=language,
            taxonomy_summary=self._taxonomy_summary,
            client_id=client_id
        )
        
        # Call LLM with retries
        result = None
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )
                
                # Parse response
                content = response.choices[0].message.content
                result = json.loads(content)
                break
                
            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
                time.sleep(1)
            except Exception as e:
                last_error = str(e)
                time.sleep(2 ** attempt)  # Exponential backoff
        
        if result is None:
            return {
                "error": last_error,
                "tags": [],
                "confidence": 0.0,
                "client_id": client_id
            }
        
        # Validate tags against taxonomy
        extracted_tags = result.get('tags', [])
        validation = self.taxonomy.validate_tags(extracted_tags)
        
        # Build final result
        final_result = {
            "client_id": client_id,
            "language": language,
            "tags": validation['valid'],
            "invalid_tags": validation['invalid'],
            "num_tags": len(validation['valid']),
            "confidence": result.get('confidence', 0.0),
            "budget_range": result.get('budget_range'),
            "client_status": result.get('client_status'),
            "key_dates": result.get('key_dates', []),
            "dietary": result.get('dietary', []),
            "allergies": result.get('allergies', []),
            "referral_potential": result.get('referral_potential'),
            "profession": result.get('profession'),
            "mentioned_persons": result.get('mentioned_persons', []),
            "follow_up_action": result.get('follow_up_action'),
            "reasoning": result.get('reasoning'),
            "from_cache": False
        }
        
        # Cache the result
        if client_id:
            self._save_to_cache(client_id, final_result)
        
        return final_result
    
    def extract_batch(
        self,
        data: List[Dict],
        id_col: str = "ID",
        text_col: str = "Transcription",
        lang_col: str = "Language",
        use_cache: bool = True,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        Extract tags from multiple transcriptions.
        
        Args:
            data: List of dicts with transcription data
            id_col: Column name for client ID
            text_col: Column name for transcription text
            lang_col: Column name for language
            use_cache: Whether to use cached results
            progress_callback: Optional callback(current, total)
            
        Returns:
            List of extraction results
        """
        results = []
        total = len(data)
        
        for i, row in enumerate(data):
            client_id = row.get(id_col)
            transcription = row.get(text_col)
            language = row.get(lang_col, 'EN')
            
            result = self.extract(
                transcription=transcription,
                language=language,
                client_id=client_id,
                use_cache=use_cache
            )
            
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def get_stats(self, results: List[Dict]) -> Dict:
        """
        Calculate statistics from extraction results.
        
        Args:
            results: List of extraction results
            
        Returns:
            Dict with statistics
        """
        total = len(results)
        if total == 0:
            return {}
        
        # Tag statistics
        all_tags = []
        for r in results:
            all_tags.extend(r.get('tags', []))
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Category statistics
        category_counts = {}
        for tag in all_tags:
            category = self.taxonomy.get_category_for_tag(tag)
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Confidence stats
        confidences = [r.get('confidence', 0) for r in results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Cache stats
        from_cache = sum(1 for r in results if r.get('from_cache', False))
        
        return {
            "total_processed": total,
            "total_tags_extracted": len(all_tags),
            "unique_tags_used": len(tag_counts),
            "avg_tags_per_note": len(all_tags) / total,
            "avg_confidence": round(avg_confidence, 3),
            "from_cache": from_cache,
            "top_10_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "tags_by_category": category_counts
        }


def create_extractor(**kwargs) -> TagExtractor:
    """Factory function to create a TagExtractor instance."""
    return TagExtractor(**kwargs)


if __name__ == "__main__":
    # Quick test
    extractor = TagExtractor()
    print(f"Extractor initialized with model: {extractor.model}")
    print(f"Taxonomy: {extractor.taxonomy.num_tags} tags in {extractor.taxonomy.num_categories} categories")
