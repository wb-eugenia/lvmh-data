"""
LLM-based tag extractor for LVMH Voice to Tag.
Powered by Mistral AI with structured JSON output.
"""

import json
import os
import time
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

from mistralai import Mistral
from dotenv import load_dotenv

from .taxonomy import Taxonomy
from .prompts import SYSTEM_PROMPT, get_extraction_prompt


# Load environment variables
load_dotenv()


class TagExtractor:
    """
    Extracts structured tags from transcriptions using Mistral AI.
    """
    
    def __init__(
        self,
        taxonomy_path: str = "config/taxonomy_v1.json",
        model: str = "mistral-small-latest",
        temperature: float = 0.0,
        max_retries: int = 3,
        cache_dir: Optional[str] = "cache",
        api_key: Optional[str] = None
    ):
        """
        Initialize the tag extractor.
        
        Args:
            taxonomy_path: Path to taxonomy JSON file
            model: Mistral model to use
            temperature: Sampling temperature (0 for deterministic)
            max_retries: Max retries on API failure
            cache_dir: Directory for caching results
            api_key: Mistral API key
        """
        self.taxonomy = Taxonomy(taxonomy_path)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        # Initialize Mistral client
        api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment variables")
        
        self.client = Mistral(api_key=api_key)
        
        # Create cache directory if needed
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Get taxonomy summary for prompts
        self._taxonomy_summary = self.taxonomy.get_tags_summary()
    
    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from text that might contain markdown or other content.
        Handles responses like ```json {...} ``` or plain text with JSON.
        """
        if not text:
            return "{}"
        
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Try to find raw JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        # Return original text and hope for the best
        return text.strip()
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call Mistral LLM.
        Returns the response content as string (JSON).
        """
        enhanced_prompt = f"""{user_prompt}

IMPORTANT: Tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans markdown, sans explication.
Format attendu: {{"tags": ["tag1", "tag2"]}}"""
        
        response = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt + "\nTu réponds toujours en JSON valide uniquement."},
                {"role": "user", "content": enhanced_prompt}
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )
        
        # Extract JSON from potential markdown/text response
        raw_content = response.choices[0].message.content
        return self._extract_json_from_text(raw_content)
    
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
    
    def extract_tags_simple(self, transcription: str) -> List[str]:
        """
        Extract tags from transcription using the Smart Tags prompt.
        Simplified method for the hybrid pipeline - returns only a list of strings.
        
        Args:
            transcription: The transcribed text
            
        Returns:
            List of extracted tag strings
        """
        # Simplified user prompt for Smart Tags extraction
        user_prompt = f"""Analyse cette transcription et génère des tags pertinents.

TRANSCRIPTION :
"{transcription}"

Réponds avec un JSON contenant une clé "tags" avec la liste des tags extraits."""

        # Call LLM with retries
        result = None
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Use the abstracted LLM call method
                content = self._call_llm(SYSTEM_PROMPT, user_prompt)
                result = json.loads(content)
                break
                
            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
                time.sleep(1)
            except Exception as e:
                last_error = str(e)
                time.sleep(2 ** attempt)
        
        if result is None:
            print(f"⚠️ Extraction failed: {last_error}")
            return []
        
        # Return clean list of tags
        tags = result.get('tags', [])
        
        # Ensure all tags are strings and properly formatted
        clean_tags = []
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                clean_tags.append(tag.strip())
        
        return clean_tags
    
    def extract(
        self,
        transcription: str,
        language: str,
        client_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract tags and metadata from a transcription.
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
                # Use the abstracted LLM call method
                content = self._call_llm(SYSTEM_PROMPT, user_prompt)
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
            "confidence": result.get('confidence', 0.0),
            "reasoning": result.get('reasoning'),
            "from_cache": False
        }
        
        # Cache the result
        if client_id:
            self._save_to_cache(client_id, final_result)
        
        return final_result

def create_extractor(**kwargs) -> TagExtractor:
    """Factory function to create a TagExtractor instance."""
    return TagExtractor(**kwargs)

if __name__ == "__main__":
    # Quick test
    try:
        extractor = TagExtractor()
        print(f"✅ Mistral Extractor initialized with model: {extractor.model}")
    except Exception as e:
        print(f"❌ Error initializing extractor: {e}")
