"""
LangExtract Service for LVMH

Uses Mistral API via OpenAI-compatible endpoint with key rotation.
"""

import os
import logging
from typing import Optional

import langextract as lx
from langextract import factory

from src.schemas.langextract_lvmh import get_lvmh_prompt, get_lvmh_examples
from src.mistral_rotator import MistralKeyRotator

logger = logging.getLogger(__name__)


class LVMHLangExtractService:
    """LangExtract service with Mistral API and key rotation."""
    
    MODEL_ID = "mistral-small-latest"
    MISTRAL_ENDPOINT = "https://api.mistral.ai/v1"
    
    def __init__(self):
        self._rotator = MistralKeyRotator()
        self._model = None
        self._prompt = get_lvmh_prompt()
        self._examples = get_lvmh_examples()
    
    def _get_model(self, api_key: str):
        """Get or create LangExtract model with Mistral."""
        if self._model is None:
            config = factory.ModelConfig(
                model_id=self.MODEL_ID,
                provider="OpenAILanguageModel",
                provider_kwargs={
                    "api_key": api_key,
                    "base_url": self.MISTRAL_ENDPOINT
                }
            )
            self._model = factory.create_model(config)
            logger.info(f"Created LangExtract model with Mistral: {self.MODEL_ID}")
        return self._model
    
    def extract(self, text: str, language: str = "fr") -> dict:
        """
        Extract LVMH 4-pillar data from text.
        
        Args:
            text: Input transcription
            language: Language code (fr, en, it, etc.)
        
        Returns:
            Dict with:
                - success: bool
                - tags: list of extractions
                - offsets: source mapping for audit
                - error: error message if failed
        """
        api_key = self._rotator.get_key()
        
        if not api_key:
            logger.error("No Mistral API key available")
            return {
                "success": False,
                "tags": [],
                "offsets": [],
                "error": "No API key available"
            }
        
        try:
            model = self._get_model(api_key)
            
            result = lx.extract(
                text_or_documents=text,
                prompt_description=self._prompt,
                examples=self._examples,
                model=model,
            )
            
            # Parse extractions
            tags = []
            offsets = []
            
            if hasattr(result, 'extractions') and result.extractions:
                for ext in result.extractions:
                    tag = {
                        "class": ext.extraction_class,
                        "text": ext.extraction_text,
                        "attributes": ext.attributes or {}
                    }
                    tags.append(tag)
                    
                    # Extract offsets if available
                    if hasattr(ext, 'char_start') and hasattr(ext, 'char_end'):
                        offsets.append({
                            "class": ext.extraction_class,
                            "text": ext.extraction_text,
                            "char_start": ext.char_start,
                            "char_end": ext.char_end
                        })
            
            logger.info(f"LangExtract success: {len(tags)} tags extracted")
            
            return {
                "success": True,
                "tags": tags,
                "offsets": offsets,
                "language": language
            }
            
        except Exception as e:
            logger.error(f"LangExtract extraction failed: {e}")
            
            # Try rotating key and retry once
            new_key = self._rotator.rotate()
            if new_key:
                logger.info("Retrying with rotated key...")
                try:
                    self._model = None  # Reset model
                    model = self._get_model(new_key)
                    
                    result = lx.extract(
                        text_or_documents=text,
                        prompt_description=self._prompt,
                        examples=self._examples,
                        model=model,
                    )
                    
                    tags = []
                    offsets = []
                    
                    if hasattr(result, 'extractions') and result.extractions:
                        for ext in result.extractions:
                            tags.append({
                                "class": ext.extraction_class,
                                "text": ext.extraction_text,
                                "attributes": ext.attributes or {}
                            })
                            
                            if hasattr(ext, 'char_start') and hasattr(ext, 'char_end'):
                                offsets.append({
                                    "class": ext.extraction_class,
                                    "text": ext.extraction_text,
                                    "char_start": ext.char_start,
                                    "char_end": ext.char_end
                                })
                    
                    return {
                        "success": True,
                        "tags": tags,
                        "offsets": offsets,
                        "language": language,
                        "key_rotated": True
                    }
                    
                except Exception as retry_error:
                    logger.error(f"Retry with rotated key also failed: {retry_error}")
            
            return {
                "success": False,
                "tags": [],
                "offsets": [],
                "error": str(e)
            }
    
    def extract_simple(self, text: str) -> list:
        """Simple extraction returning just tags."""
        result = self.extract(text)
        return result.get("tags", [])


# Singleton instance
_service_instance: Optional[LVMHLangExtractService] = None


def get_langextract_service() -> LVMHLangExtractService:
    """Get singleton LangExtract service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = LVMHLangExtractService()
    return _service_instance
