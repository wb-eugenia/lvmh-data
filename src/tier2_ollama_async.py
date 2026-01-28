"""
Async Wrapper for Tier 2 Ollama Engine.
Uses ThreadPoolExecutor to handle synchronous Ollama calls without blocking the event loop.
Includes Pydantic validation and Resilience patterns.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import requests
from config.production import settings
from src.models import ExtractionResult
from src.resilience import safe_execution, retry_with_backoff, CircuitBreaker

logger = logging.getLogger(__name__)

class Tier2OllamaAsync:
    """
    Async wrapper for Ollama extraction.
    """
    
    SYSTEM_PROMPT = """Tu es un expert LVMH pour l'extraction de données clients.
Analyse la note vocale et extrais les informations structurées.

TAXONOMIE DES TAGS (utilise uniquement ces catégories):
- Produits: leather_goods, small_leather, watches, jewelry, fragrance, ready_to_wear, shoes, travel_luggage
- Modèles LV: capucines, alma, neverfull, speedy, keepall, dauphine, twist, onthego
- Professions: medical_*, legal_*, finance_*, entrepreneur*, tech_*, creative_*, media_*, academic*
- Lifestyle: art_collector, wine_enthusiast, travel_frequent, sports_*, philanthropist
- Régime: vegan, vegetarian, gluten_free, halal, kosher
- Allergies: nickel_allergy, latex_allergy, nut_allergy, perfume_sensitivity
- Occasions: birthday_gift, wedding_gift, christmas_gift, self_reward
- Relations: shopping_with_spouse, gift_for_child, gift_for_parent

RÈGLES:
1. Extrais les tags pertinents de la taxonomie
2. Détecte le budget (range: under_5K, 5K-10K, 10K-20K, 20K-50K, 50K+)
3. Identifie le statut client (vic, vip, regular, first_visit, occasional)
4. Note les allergies et LEUR SÉVÉRITÉ (low, medium, high)
5. Extrais les relations (avec qui, cadeau pour qui)

EXEMPLES (FEW-SHOT):

Input: "Mme Martin, avocate, cherche un sac Capucines noir. Budget 6000€. Elle est végétarienne."
Output:
{
    "tags": ["capucines", "leather_goods", "legal_professional"],
    "budget_range": "5K-10K",
    "client_status": "regular",
    "profession": "avocate",
    "allergies": [],
    "allergy_severity": "low",
    "dietary": ["vegetarian"],
    "relationship_context": {},
    "confidence": 0.9,
    "reasoning": "Mention explicite de profession, produit et régime."
}

Input: "Client VIC, M. Dupont. Cadeau pour sa femme. Attention allergie grave aux noix (choc)."
Output:
{
    "tags": ["gift_for_spouse", "nut_allergy"],
    "budget_range": null,
    "client_status": "vic",
    "profession": null,
    "allergies": ["nut_allergy"],
    "allergy_severity": "high",
    "dietary": [],
    "relationship_context": {"gift_for": ["spouse"]},
    "confidence": 0.95,
    "reasoning": "VIC identifié, allergie grave détectée."
}

RÉPONDS UNIQUEMENT EN JSON VALIDE (pas de markdown):
"""

    def __init__(self):
        self.ollama_url = f"{settings.ollama_host}/api/generate"
        self.model = settings.ollama_model
        self.executor = ThreadPoolExecutor(max_workers=settings.ollama_max_parallel)
        self.circuit_breaker = CircuitBreaker(failure_threshold=settings.circuit_breaker_threshold)
        
    def _extract_sync(self, text: str, language: str) -> Dict:
        """Synchronous extraction logic (to be run in thread)."""
        if not self.circuit_breaker.allow_request():
            logger.warning("Circuit breaker OPEN for Ollama")
            return None

        prompt = f"""Langue: {language}

NOTE CLIENT:
"{text}"

Extrais les informations et réponds en JSON:"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": self.SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500,
                "top_p": 0.9
            }
        }
        
        try:
            response = requests.post(
                self.ollama_url,
                json=payload,
                timeout=settings.ollama_timeout
            )
            
            if response.status_code == 200:
                self.circuit_breaker.record_success()
                result = response.json()
                text_resp = result.get('response', '')
                return self._parse_json(text_resp)
            else:
                self.circuit_breaker.record_failure()
                logger.error(f"Ollama error: {response.status_code}")
                return None
                
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Ollama connection error: {e}")
            raise e

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        try:
            return json.loads(text)
        except:
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
        return None

    @safe_execution(default_return=ExtractionResult(extracted_by="tier2_ollama_async", processing_tier="tier2", confidence=0.0))
    @retry_with_backoff(retries=2)
    async def extract(self, text: str, language: str = 'FR') -> ExtractionResult:
        """
        Async extraction method.
        Runs sync request in thread pool.
        """
        loop = asyncio.get_event_loop()
        
        result_dict = await loop.run_in_executor(
            self.executor,
            self._extract_sync,
            text,
            language
        )
        
        if not result_dict:
            return ExtractionResult(extracted_by="tier2_ollama_async", processing_tier="tier2", confidence=0.0)
            
        # Build relationship tags
        rel_tags = []
        rel_context = result_dict.get('relationship_context', {})
        for r in rel_context.get('shopping_with', []):
            rel_tags.append(f'shopping_with_{r}')
        for r in rel_context.get('gift_for', []):
            rel_tags.append(f'gift_for_{r}')
        
        all_tags = result_dict.get('tags', []) + rel_tags
        
        return ExtractionResult(
            tags=all_tags,
            budget_range=result_dict.get('budget_range'),
            client_status=result_dict.get('client_status'),
            profession=result_dict.get('profession'),
            allergies=result_dict.get('allergies', []),
            allergy_severity=result_dict.get('allergy_severity') if result_dict.get('allergy_severity') in ['low', 'medium', 'high'] else 'low',
            dietary=result_dict.get('dietary', []),
            relationship_context=rel_context,
            confidence=result_dict.get('confidence', 0.75),
            reasoning=result_dict.get('reasoning'),
            processing_tier="tier2",
            extracted_by="tier2_ollama_async",
            model_name=self.model,
            cost=0.0
        )
