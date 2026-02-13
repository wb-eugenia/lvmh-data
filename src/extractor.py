"""
Tier 3 Enhanced: Premium Adaptive LLM Extractor.
Uses Mistral adaptive model selection with deep 4-layer analysis.
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
from src.models import (
    ExtractionResult, Pilier1Product, Pilier2Client, Pilier3Care, Pilier4Business,
    MetaAnalysis, ProductPreferences, PurchaseContext, Profession, Lifestyle, Allergies
)
from src.resilience import safe_execution, retry_with_backoff
from config.production import settings

load_dotenv()

logger = logging.getLogger(__name__)

def safe_list(val):
    """Helper to ensure list of strings."""
    return [str(v) for v in val] if isinstance(val, list) else []

class Tier3Enhanced:
    """
    Tier 3 Premium Extractor.
    Designed for complex/critical cases requiring deep reasoning.
    """
    
    # Model tiers
    # Model tiers (Mistral Native)
    MODELS = {
        'economy': 'mistral-small-latest',       # Efficient for fallback
        'standard': 'mistral-large-latest',      # Flagship
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
🧠 LAYER 3: INTENTIONS IMPLICITES (LLM ADVANTAGE)
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
💰 BUDGET INFERENCE AVANCÉE (LLM REASONING)
═══════════════════════════════════════════════════════════════

CONTEXTE MULTI-FACTEURS:
1. STATUT CLIENT (VIC, VIP, Ultimate)
2. MODIFIERS LINGUISTIQUES ("flexible", "ouvert", "serré")
3. SIGNAUX IMPLICITES (Produits >20K, "Collection privée")
4. CONTEXTE PROFESSIONNEL

RÈGLE OR: Combine TOUS les signaux pour inférer range précis

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

    def _validate_extraction(self, data: Dict, model: str, cost: float) -> ExtractionResult:
        """
        Validate and sanitize dictionary into ExtractionResult (Taxonomy V2).
        Handles mapping from LLM JSON output to Pydantic Models.
        """
        try:
            # Helper safely get nested dict
            def get_d(d, k): return d.get(k, {}) if isinstance(d, dict) else {}
            
            # --- Pilier 1 ---
            p1_data = get_d(data, 'pilier_1_univers_produit')
            pref_data = get_d(p1_data, 'preferences')
            
            raw_cats = safe_list(p1_data.get('categories', []))
            norm_cats = []
            for t in raw_cats:
                norm = self.taxonomy.normalize_tag(t)
                if norm: norm_cats.append(norm)

            p1 = Pilier1Product(
                categories=norm_cats,
                usage=safe_list(p1_data.get('usage', [])),
                preferences=ProductPreferences(
                    colors=safe_list(pref_data.get('colors', [])),
                    styles=safe_list(pref_data.get('styles', [])),
                    hardware=safe_list(pref_data.get('hardware', [])),
                    materials=safe_list(pref_data.get('materials', []))
                )
            )
            
            # --- Pilier 2 ---
            p2_data = get_d(data, 'pilier_2_profil_client')
            pc_data = get_d(p2_data, 'purchase_context')
            prof_data = get_d(p2_data, 'profession')
            life_data = get_d(p2_data, 'lifestyle')
            
            p2 = Pilier2Client(
                purchase_context=PurchaseContext(
                    type=pc_data.get('type'),
                    behavior=pc_data.get('behavior')
                ),
                profession=Profession(
                    sector=prof_data.get('sector'),
                    status=prof_data.get('status')
                ),
                lifestyle=Lifestyle(
                    passions=safe_list(life_data.get('passions', [])),
                    family=life_data.get('family', 'Unknown')
                )
            )
            
            # --- Pilier 3 ---
            p3_data = get_d(data, 'pilier_3_hospitalite_care')
            alg_data = get_d(p3_data, 'allergies')
            
            p3 = Pilier3Care(
                diet=safe_list(p3_data.get('diet', [])),
                allergies=Allergies(
                    food=safe_list(alg_data.get('food', [])),
                    contact=safe_list(alg_data.get('contact', []))
                ),
                values=safe_list(p3_data.get('values', [])),
                occasion=p3_data.get('occasion')
            )
            
            # --- Pilier 4 ---
            p4_data = get_d(data, 'pilier_4_action_business')
            
            p4 = Pilier4Business(
                lead_temperature=p4_data.get('lead_temperature', 'Warm'),
                next_best_action=p4_data.get('next_best_action'),
                budget_potential=p4_data.get('budget_potential'),
                urgency=p4_data.get('urgency')
            )
            
            # --- Meta ---
            meta_data = get_d(data, 'meta_analysis')
            meta = MetaAnalysis(
                confidence_score=float(meta_data.get('confidence_score', 0.8)),
                missing_info=safe_list(meta_data.get('missing_info', [])),
                risk_flags=safe_list(meta_data.get('risk_flags', []))
            )

            # Construct Final Result
            return ExtractionResult(
                pilier_1_univers_produit=p1,
                pilier_2_profil_client=p2,
                pilier_3_hospitalite_care=p3,
                pilier_4_action_business=p4,
                meta_analysis=meta,
                
                # Metadata
                processing_tier="tier3",
                confidence=meta.confidence_score,
                rgpd_flag=len(meta.risk_flags) > 0,
                from_cache=False
            )
            
        except ValidationError as e:
            logger.error(f"Validation error Pydantic: {e}")
            raise e
        except Exception as e:
            logger.error(f"General validation error: {e}")
            raise e

    @safe_execution(default_return=ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(confidence_score=0.0),
        processing_tier="tier3",
        extracted_by="tier3_failed",
        confidence=0.0,
        rgpd_flag=False,
        from_cache=False
    ))
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
            
            user_payload = {
                "language": language,
                "note_vocale": text,
                "mission": "Extraction 4-Layer complète selon le System Prompt",
                "output_format": "json_object",
            }
            user_prompt = json.dumps(user_payload, ensure_ascii=False)

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
