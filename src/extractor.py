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

from src.taxonomy import TaxonomyManager
from .prompts import SYSTEM_PROMPT, get_extraction_prompt
from src.models import ExtractionResult
from src.resilience import safe_execution, retry_with_backoff
from config.production import settings


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
        """
        self.taxonomy = TaxonomyManager()
        self.model = model or settings.openai_model
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
    
    @safe_execution(default_return=ExtractionResult(extracted_by="tier3_llm", processing_tier="tier3", confidence=0.0))
    @retry_with_backoff(retries=3)
    def extract(
        self,
        transcription: str,
        language: str,
        client_id: Optional[str] = None,
        use_cache: bool = True
    ) -> ExtractionResult:
        """
        Extract tags and metadata from a transcription.
        Returns ExtractionResult Pydantic model.
        """
        # Cache handling should be done by pipeline, skipping internal cache for now
        
        prompt = get_extraction_prompt(transcription, language, self._taxonomy_summary)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
                timeout=settings.openai_timeout
            )
            
            result_json = json.loads(response.choices[0].message.content)
            
            # Build relationship tags
            rel_tags = []
            rel_context = result_json.get('relationship_context', {})
            if isinstance(rel_context, dict):
                for r in rel_context.get('shopping_with') or []:
                    rel_tags.append(f'shopping_with_{r}')
                for r in rel_context.get('gift_for') or []:
                    rel_tags.append(f'gift_for_{r}')
            
            raw_tags = result_json.get('tags', []) + rel_tags
            
            # Filter/Normalize tags using Taxonomy
            valid_tags = []
            for tag in raw_tags:
                # Try to normalize/validate
                normalized = self.taxonomy.normalize_tag(tag)
                if normalized:
                    valid_tags.append(normalized)
                else:
                    # If relationship tag, keep it if it looks valid
                    if tag.startswith('shopping_with_') or tag.startswith('gift_for_'):
                        valid_tags.append(tag)
                    # Else ignore invalid tag to avoid pydantic error
            
            return ExtractionResult(
                tags=valid_tags,
                budget_range=result_json.get('budget_range'),
                client_status=result_json.get('client_status'),
                profession=result_json.get('profession'),
                allergies=result_json.get('allergies', []),
                allergy_severity=result_json.get('allergy_severity') if result_json.get('allergy_severity') in ['low', 'medium', 'high'] else 'low',
                dietary=result_json.get('dietary', []),
                relationship_context=rel_context,
                confidence=result_json.get('confidence', 0.9),
                reasoning=result_json.get('reasoning'),
                processing_tier="tier3",
                extracted_by="tier3_llm",
                model_name=self.model,
                cost=0.0001
            )
            
        except Exception as e:
            raise e

    def get_stats(self, results: List[Dict]) -> Dict:
        """Calculate statistics from extraction results."""
        # Simplified for now as we move to centralized monitoring
        return {"total_processed": len(results)}


def create_extractor(**kwargs) -> TagExtractor:
    """Factory function to create a TagExtractor instance."""
    return TagExtractor(**kwargs)
