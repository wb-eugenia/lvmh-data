"""
Tier 3 Enhanced: Premium Adaptive LLM Extractor.
Uses OpenAI Adaptive Models (GPT-4o, Turbo, O1) with deep 4-layer analysis.
Features: Async, Caching, Robust Validation, and Adaptive Routing.
"""

import os
import json
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta

from mistralai import Mistral
from dotenv import load_dotenv
from pydantic import ValidationError

from src.taxonomy import TaxonomyManager
from src.models import ExtractionResult
from src.resilience import safe_execution, retry_with_backoff
from config.production import settings

load_dotenv()

logger = logging.getLogger(__name__)

class Tier3Enhanced:
    """
    Tier 3 Premium Extractor.
    Designed for complex/critical cases requiring deep reasoning.
    """
    
    # Model tiers
    # Model tiers (Mistral Native)
    MODELS = {
        'economy': 'mistral-small-latest',       # Efficient for fallback
        'standard': 'mistral-large-latest',      # Flagship (GPT-4 equivalent)
        'premium': 'mistral-large-latest',       # Use Large for premium too
        'reasoning': 'mistral-large-latest',     # Large handles reasoning well
    }
    
    COSTS_PER_1M_TOKENS = {
        'mistral-small-latest': 0.2,   # Approx
        'mistral-large-latest': 2.0,   # Approx
    }
    
    SYSTEM_PROMPT = """Tu es l'Expert LVMH PREMIUM pour l'analyse de notes vocales CA.

Tu es sollicité uniquement pour les cas COMPLEXES/CRITIQUES qui nécessitent:
- Raisonnement nuancé (ambiguïtés contextuelles)
- Précision absolue (clients VIC/Ultimate, allergies graves)
- Extraction multi-couches (entités + relations + intentions implicites)

═══════════════════════════════════════════════════════════════
🎯 MISSION: EXTRACTION EXHAUSTIVE MULTI-LAYERS
═══════════════════════════════════════════════════════════════

LAYER 1 - TAXONOMIE CORE (98 tags standards)
LAYER 2 - ENTITÉS DYNAMIQUES (noms propres, lieux, événements)
LAYER 3 - INTENTIONS IMPLICITES (non-dit, contexte émotionnel)
LAYER 4 - RISQUES & ALERTES (allergies, compliance, urgences)

═══════════════════════════════════════════════════════════════
📋 LAYER 1: TAXONOMIE STANDARD
═══════════════════════════════════════════════════════════════

{taxonomy_summary}

═══════════════════════════════════════════════════════════════
🏷️ LAYER 2: ENTITÉS DYNAMIQUES (CRITIQUE TIER 3!)
═══════════════════════════════════════════════════════════════

Extrais SYSTÉMATIQUEMENT:

1. PRODUITS MENTIONNÉS (exact wording):
   - Modèles: "Birkin 25", "Kelly Sellier 32", "Capucines MM"
   - Matières: "cuir taurillon", "python mat", "alligator mississippiensis"
   - Couleurs: "noir ébène", "rouge H", "bleu de Prusse"
   
2. MARQUES CITÉES (même concurrents):
   - LVMH: Louis Vuitton, Dior, Fendi, Givenchy, Bulgari...
   - Concurrents: Hermès, Chanel, Gucci, Prada...

3. LIEUX GÉOGRAPHIQUES:
   - Villes, Boutiques, Pays

4. ÉVÉNEMENTS SPÉCIFIQUES:
   - "Gala Opéra de Paris", "Mariage Château de Versailles"
   
5. PERSONNES MENTIONNÉES:
   - CA référents, Influenceurs, Relations

═══════════════════════════════════════════════════════════════
🧠 LAYER 3: INTENTIONS IMPLICITES (GPT-4 ADVANTAGE!)
═══════════════════════════════════════════════════════════════

Analyse le SOUS-TEXTE et détecte:

1. SIGNAUX ÉMOTIONNELS:
   - Excitation, Hésitation, Pression (urgency_implicit)
   
2. OBJECTIONS CACHÉES (Prix, Qualité, Style)

3. OPPORTUNITÉS UPSELL (Cross-sell, Outfit coordination)

4. SENTIMENT CLIENT (satisfait, neutre, insatisfait, enthousiasmé)

═══════════════════════════════════════════════════════════════
🚨 LAYER 4: RISQUES & ALERTES (COMPLIANCE CRITICAL!)
═══════════════════════════════════════════════════════════════

DÉTECTION PRIORITAIRE:

1. ALLERGIES (SÉVÉRITÉ ABSOLUE):
   - SEVERE (emergency_flag: true): "choc anaphylactique", "EpiPen", "urgence vitale"
   - MODERATE / MILD
   → Alerte CA automatique

2. RGPD SENSITIVE DATA (Santé, Religion, Politique, Judiciaire)

3. FRAUDE / RED FLAGS (Cash only, Pas de facture)

4. COMPLIANCE EXPORT (Pays sanctionnés, Produits sensibles)

═══════════════════════════════════════════════════════════════
💰 BUDGET INFERENCE AVANCÉE (GPT-4 REASONING)
═══════════════════════════════════════════════════════════════

CONTEXTE MULTI-FACTEURS:
1. STATUT CLIENT (VIC, VIP, Ultimate)
2. MODIFIERS LINGUISTIQUES ("flexible", "ouvert", "serré")
3. SIGNAUX IMPLICITES (Produits >20K, "Collection privée")
4. CONTEXTE PROFESSIONNEL

RÈGLE OR: Combine TOUS les signaux pour inférer range précis

═══════════════════════════════════════════════════════════════
📤 FORMAT OUTPUT JSON (COMPREHENSIVE)
═══════════════════════════════════════════════════════════════

{{
  "tags": ["tag1", "tag2", ...],
  
  "budget_range": "10K-20K",
  "budget_min": 10000,
  "budget_max": 20000,
  "budget_confidence": "explicit|inferred_strong|inferred_weak",
  "budget_reasoning": "...",
  
  "client_status": "vic",
  "profession": "...",
  
  "allergies": [
    {{
      "allergen": "nickel_allergy",
      "severity": "high",
      "emergency_flag": true,
      "notes": "..."
    }}
  ],
  
  "dietary": ["vegan", "gluten_free"],
  
  "relationship_context": {{
    "gift_for": ["spouse"],
    "shopping_with": ["alone"]
  }},
  
  "occasions": ["wedding_anniversary"],
  "urgency": "this_week",
  "event_date": "2026-04-15",
  "days_until_event": 77,
  
  "entities": {{
    "products_mentioned": [],
    "brands_mentioned": [],
    "locations": [],
    "events": []
  }},
  
  "implicit_signals": {{
    "purchase_intent": "high|medium|low",
    "urgency_implicit": true,
    "sentiment": "enthusiastic",
    "objections": []
  }},
  
  "risk_flags": {{
    "allergy_emergency": true,
    "rgpd_sensitive": false,
    "manual_review_required": false
  }},
  
  "confidence": 0.96,
  "reasoning": "...",
  "processing_notes": ["..."]
}}

RÉPONDS UNIQUEMENT EN JSON VALIDE.
"""

    def __init__(self, cache_dir: str = "cache/tier3"):
        self.taxonomy = TaxonomyManager()
        self.client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
        
        # Concurrency limits
        self.semaphore = asyncio.Semaphore(10)
        
        # Cache setup
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl_hours = 24
        
        self.default_model = self.MODELS['standard']
    
    def _select_model(self, text: str, client_status: Optional[str], escalation_reason: Optional[str]) -> str:
        """Select optimal model based on context."""
        if client_status in ['ultimate', 'platinum']:
            return self.MODELS['premium']
        
        if escalation_reason and 'allergy' in escalation_reason.lower():
            return self.MODELS['standard']
        
        if escalation_reason and 'ambiguous' in escalation_reason.lower():
            return self.MODELS['reasoning']
        
        if client_status in ['vic', 'vip']:
            return self.MODELS['standard']
            
        if len(text.split()) > 2000:
            return self.MODELS['premium']
            
        return self.default_model

    def _generate_cache_key(self, text: str, language: str, model: str) -> str:
        """Generate unique cache key."""
        content = f"{text}_{language}_{model}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        subdir = cache_key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{cache_key}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[ExtractionResult]:
        """Load from cache if valid."""
        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None
            
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            cached_at = datetime.fromisoformat(cached_data['cached_at'])
            age_hours = (datetime.now() - cached_at).total_seconds() / 3600
            
            if age_hours > self.cache_ttl_hours:
                cache_path.unlink(missing_ok=True)
                return None
                
            result = ExtractionResult(**cached_data['result'])
            result.from_cache = True
            return result
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    def _save_to_cache(self, cache_key: str, result: ExtractionResult) -> None:
        """Save result to cache."""
        try:
            cache_path = self._get_cache_path(cache_key)
            data = {
                'cached_at': datetime.now().isoformat(),
                'cache_key': cache_key,
                'result': result.model_dump()
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def _calculate_cost(self, model: str, tokens_used: int) -> float:
        cost_per_1m = self.COSTS_PER_1M_TOKENS.get(model, 2.50)
        return (tokens_used / 1_000_000) * cost_per_1m

    def _validate_extraction(self, result_dict: Dict, model: str, cost: float) -> ExtractionResult:
        """Validate and sanitize dictionary into ExtractionResult."""
        
        # Helpers
        def safe_list(val): return [str(v) for v in val] if isinstance(val, list) else []
        def safe_str(val): return str(val).strip() if val else None
        
        # Core fields
        tags = safe_list(result_dict.get('tags', []))
        
        # Reconstruct result
        try:
            return ExtractionResult(
                tags=tags,
                budget_range=safe_str(result_dict.get('budget_range')),
                budget_min=result_dict.get('budget_min'),
                budget_max=result_dict.get('budget_max'),
                budget_confidence=safe_str(result_dict.get('budget_confidence')),
                
                client_status=safe_str(result_dict.get('client_status')),
                profession=safe_str(result_dict.get('profession')),
                
                allergies=[a.get('allergen') for a in result_dict.get('allergies', []) if isinstance(a, dict) and 'allergen' in a],
                allergy_severity='high' if any(a.get('severity') == 'high' for a in result_dict.get('allergies', []) if isinstance(a, dict)) else 'low',
                dietary=safe_list(result_dict.get('dietary', [])),
                
                relationship_context=result_dict.get('relationship_context', {}),
                occasions=safe_list(result_dict.get('occasions', [])),
                urgency=safe_str(result_dict.get('urgency')),
                event_date=safe_str(result_dict.get('event_date')),
                days_until_event=result_dict.get('days_until_event'),
                
                # New fields
                entities=result_dict.get('entities', {}),
                implicit_signals=result_dict.get('implicit_signals', {}),
                risk_flags=result_dict.get('risk_flags', {}),
                processing_notes=safe_list(result_dict.get('processing_notes', [])),
                
                confidence=float(result_dict.get('confidence', 0.85)),
                reasoning=safe_str(result_dict.get('reasoning')),
                
                processing_tier="tier3",
                extracted_by="tier3_gpt4",
                model_name=model,
                cost=cost
            )
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            # Fallback
            return ExtractionResult(
                tags=tags,
                confidence=0.5,
                reasoning=f"Validation failed: {e}",
                processing_tier="tier3",
                extracted_by="tier3_fallback",
                error=str(e)
            )

    @safe_execution(default_return=ExtractionResult(extracted_by="tier3_failed", processing_tier="tier3", confidence=0.0))
    @retry_with_backoff(retries=3)
    async def extract(
        self,
        text: str,
        language: str = 'FR',
        client_status: Optional[str] = None,
        escalation_reason: Optional[str] = None,
        use_cache: bool = True
    ) -> ExtractionResult:
        """Async extraction main method."""
        
        model = self._select_model(text, client_status, escalation_reason)
        cache_key = self._generate_cache_key(text, language, model)
        
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached: return cached
            
        async with self.semaphore:
            taxonomy_summary = self.taxonomy.get_tags_summary()
            
            # Simple user prompt
            user_prompt = f"""LANGUE: {language}
NOTE VOCALE:
{text}

Mission: Extraction 4-Layer complète selon le System Prompt."""

            try:
                response = await self.client.chat.complete_async(
                    model=model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT.format(taxonomy_summary=taxonomy_summary)},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                result_dict = json.loads(content)
                tokens = response.usage.total_tokens
                cost = self._calculate_cost(model, tokens)
                
                result = self._validate_extraction(result_dict, model, cost)
                
                if use_cache:
                    self._save_to_cache(cache_key, result)
                    
                return result
                
            except Exception as e:
                logger.error(f"Tier 3 Mistral extraction error: {e}")
                raise e

# Alias for compatibility
TagExtractor = Tier3Enhanced
