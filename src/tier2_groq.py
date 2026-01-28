"""
Async Wrapper for Tier 2 Groq Engine (Fast Inference).
Uses OpenAI Async Client with Groq Base URL.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Optional, List

from openai import AsyncOpenAI
from dotenv import load_dotenv

from config.production import settings
from src.models import ExtractionResult
from src.resilience import safe_execution, retry_with_backoff
from src.taxonomy import TaxonomyManager

load_dotenv(override=True)

logger = logging.getLogger(__name__)

class Tier2Groq:
    """
    Tier 2 implementation using Groq API (Speed-optimized).
    Replaces local Ollama for significantly faster inference.
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

RÉPONDS UNIQUEMENT EN JSON VALIDE."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not found. Tier 2 might fail.")
        
        self.client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key
        )
        self.model = "llama-3.1-8b-instant" 
        self.taxonomy = TaxonomyManager()

    @safe_execution(default_return=ExtractionResult(extracted_by="tier2_groq", processing_tier="tier2", confidence=0.0))
    @retry_with_backoff(retries=2)
    async def extract(self, text: str, language: str = 'FR') -> ExtractionResult:
        """
        Async extraction using Groq API.
        """
        prompt = f"""Langue: {language}

NOTE CLIENT:
"{text}"

Extrais les informations et réponds en JSON."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result_dict = json.loads(content)
            
            return self._format_result(result_dict)

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise e

    def _format_result(self, result_dict: Dict) -> ExtractionResult:
        """Convert raw dict to ExtractionResult and validate tags."""
        
        # Build relationship tags
        rel_tags = []
        rel_context = result_dict.get('relationship_context', {})
        if isinstance(rel_context, dict):
            for r in rel_context.get('shopping_with') or []:
                rel_tags.append(f'shopping_with_{r}')
            for r in rel_context.get('gift_for') or []:
                rel_tags.append(f'gift_for_{r}')
        
        raw_tags = result_dict.get('tags', []) + rel_tags
        
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
        
        # Normalize allergy severity
        sev = result_dict.get('allergy_severity')
        if sev not in ['low', 'medium', 'high']:
            sev = 'low'

        # Normalize relationship_context
        clean_rel_context = {}
        if isinstance(rel_context, dict):
            # Ensure values are lists
            shopping_with = rel_context.get('shopping_with')
            clean_rel_context['shopping_with'] = shopping_with if isinstance(shopping_with, list) else []
            
            gift_for = rel_context.get('gift_for')
            clean_rel_context['gift_for'] = gift_for if isinstance(gift_for, list) else []

        # Normalize allergies
        allergies = result_dict.get('allergies', [])
        clean_allergies = []
        if isinstance(allergies, list):
            for item in allergies:
                if isinstance(item, str):
                    clean_allergies.append(item)
                elif isinstance(item, dict):
                    # Handle {'allergy': 'name', 'severity': 'high'}
                    val = item.get('allergy') or item.get('value') or item.get('name')
                    if val and isinstance(val, str):
                        clean_allergies.append(val)
        
        # Normalize dietary
        dietary = result_dict.get('dietary', [])
        clean_dietary = []
        if isinstance(dietary, list):
            clean_dietary = [d for d in dietary if isinstance(d, str)]
        elif isinstance(dietary, dict):
            # Handle {'daughter': ['vegetarian'], ...}
            for val in dietary.values():
                if isinstance(val, list):
                    clean_dietary.extend([v for v in val if isinstance(v, str)])
                elif isinstance(val, str):
                    clean_dietary.append(val)

        return ExtractionResult(
            tags=valid_tags,
            budget_range=result_dict.get('budget_range'),
            client_status=result_dict.get('client_status'),
            profession=result_dict.get('profession'),
            allergies=clean_allergies,
            allergy_severity=sev,
            dietary=clean_dietary,
            relationship_context=clean_rel_context,
            confidence=result_dict.get('confidence', 0.85),
            reasoning=result_dict.get('reasoning'),
            processing_tier="tier2",
            extracted_by="tier2_groq",
            model_name=self.model,
            cost=0.0 # Groq is extremely cheap/free for now
        )
