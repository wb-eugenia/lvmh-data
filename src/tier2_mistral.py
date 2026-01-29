"""
Async Wrapper for Tier 2 Mistral Engine (Fast Inference - EU Compliant).
Uses Mistral AI SDK for RGPD-native LLM processing.
Includes Enhanced Prompts, Robust Error Handling, and Metrics.

🇫🇷 AVANTAGES MISTRAL:
- Données EU (Paris + Amsterdam)
- RGPD-native (pas de transfert US)
- Entreprise française
- HDS-compliant (Hébergement Données de Santé)
- ISO 27001 certifié
- 1 BILLION tokens/mois en free tier!
"""

import os
import json
import logging
import asyncio
import time
import statistics
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from pathlib import Path

from mistralai import Mistral
from dotenv import load_dotenv

from src.models import ExtractionResult
from src.resilience import safe_execution, retry_with_backoff
from src.taxonomy import TaxonomyManager

load_dotenv(override=True)

logger = logging.getLogger(__name__)

class Tier2Mistral:
    """
    Tier 2 implementation using Mistral API (EU-Compliant, Optimized).
    Features:
    - Enhanced System Prompt (Taxonomy, Rules, Few-shot)
    - Smart Model Selection (Mistral Medium 3)
    - Robustness (Timeout, Circuit Breaker, Defensive Parsing)
    - Metrics Tracking
    - 🇫🇷 RGPD-native (EU data residency)
    """
    
    # Model tiers (speed vs quality trade-off)
    MODELS = {
        'fast': 'mistral-small-latest',        # Speed priority (~8B params)
        'balanced': 'mistral-medium-latest',   # Best balance (~70B params)
        'quality': 'mistral-large-latest',     # Quality priority (flagship)
    }
    
    SYSTEM_PROMPT = """Tu es un expert LVMH d'analyse de notes vocales CA.
Ta mission: Extraire TOUTES les données business-critiques en JSON structuré.

═══════════════════════════════════════════════════════════════
📋 TAXONOMIE CORE (Layer 1 - 98 tags fixes)
═══════════════════════════════════════════════════════════════

PRODUITS:
- leather_goods, small_leather, watches, jewelry, fragrance
- ready_to_wear, shoes, travel_luggage, accessories

MODÈLES ICONIQUES:
- capucines, alma, neverfull, speedy, keepall, dauphine, twist
- onthego, petite_malle, city_steamer

PROFESSIONS:
- medical_physician, medical_surgeon, medical_dentist
- legal_lawyer, legal_notary, legal_corporate
- finance_banker, finance_trader, finance_wealth_manager
- entrepreneur_startup, entrepreneur_established
- tech_engineer, tech_executive, creative_designer

LIFESTYLE:
- art_collector, wine_enthusiast, travel_frequent
- sports_golf, sports_tennis, sports_equestrian, sports_yacht
- philanthropist, eco_conscious, tech_early_adopter

SANTÉ & RESTRICTIONS:
- Allergies: nickel_allergy, latex_allergy, nut_allergy, fragrance_sensitivity
- Régimes: vegan, vegetarian, pescatarian, gluten_free, halal, kosher

STATUT CLIENT:
- vic, vip, ultimate, platinum, regular, first_visit, occasional

═══════════════════════════════════════════════════════════════
🎯 RELATIONS & CONTEXTE
═══════════════════════════════════════════════════════════════

CADEAUX POUR (gift_for):
- spouse, child, parent, friend, colleague, self

SHOPPING AVEC (shopping_with):
- spouse, children, friend, alone

═══════════════════════════════════════════════════════════════
📅 DONNÉES TEMPORELLES (CRITIQUE!)
═══════════════════════════════════════════════════════════════

OCCASIONS:
- birthday, wedding, wedding_anniversary, christmas, valentines
- mothers_day, fathers_day, graduation, new_year

URGENCE:
- urgent, today, tomorrow, this_week, this_weekend, this_month
- Détecte TOUJOURS si date mentionnée!

DATES:
- Extract format: "YYYY-MM-DD" ou "mois YYYY"
- Calcule days_until si date future
- Flag "past" si date passée

═══════════════════════════════════════════════════════════════
💰 BUDGET (Smart Inference!)
═══════════════════════════════════════════════════════════════

EXPLICITE:
- "5000€", "5K", "entre 5 et 10K" → Extract montant exact

IMPLICITE (INFÉRENCE REQUISE):
- "flexible" + VIC → 10K-50K
- "ouvert" + VIP → 20K-100K
- "sans limite" → 50K+
- "budget serré" → under_5K
- Pas de mention budget + first_visit → 2K-5K

RANGES:
- under_2K, 2K-5K, 5K-10K, 10K-20K, 20K-50K, 50K+

═══════════════════════════════════════════════════════════════
🏷️ ENTITÉS DYNAMIQUES (Layer 2 - NOUVEAU!)
═══════════════════════════════════════════════════════════════

EXTRAIS ÉGALEMENT:
- products_mentioned: Liste EXACTE produits cités ["Birkin 25", "Kelly Sellier"]
- brands_mentioned: Marques citées (même non-LVMH) ["Hermès", "Chanel"]
- locations: Lieux mentionnés ["Paris", "Monaco", "New York"]
- events: Événements spécifiques ["Gala Opéra", "Mariage Côte d'Azur"]

═══════════════════════════════════════════════════════════════
⚠️ RÈGLES CRITIQUES
═══════════════════════════════════════════════════════════════

1. ALLERGIES:
   - TOUJOURS extraire severity (low/medium/high)
   - Keywords sévérité: "grave", "sévère" → high
   - "légère", "petite" → low
   - Par défaut → medium

2. BUDGET:
   - Si VIC/VIP SANS budget explicite → INFÉRER range typique
   - "flexible" = multiplier base range × 1.5
   - "ouvert" = multiplier × 2.0
   - "limité"/"serré" = multiplier × 0.6

3. MULTI-PRODUITS:
   - Si "sac + ceinture + portefeuille" → 3 produits séparés
   - Ajoute tous les tags produits correspondants

4. DATES:
   - Format OUTPUT: "2026-04-15" (ISO)
   - Calcule days_until (future) ou flag past
   - Associe à occasion si pertinent

5. CONFIDENCE:
   - 0.95+: Toutes données critiques présentes (VIC + budget + occasion + date)
   - 0.85-0.94: Données principales présentes
   - 0.70-0.84: Données partielles
   - <0.70: Incertain, escalade recommandée Tier 3

═══════════════════════════════════════════════════════════════
📤 FORMAT OUTPUT JSON (STRICT!)
═══════════════════════════════════════════════════════════════

{
  "tags": ["tag1", "tag2", ...],              // Layer 1 core tags
  
  "budget_range": "5K-10K",                    // Range standard
  "budget_min": 5000,                          // Min (si inféré)
  "budget_max": 10000,                         // Max (si inféré)
  "budget_confidence": "explicit|inferred",    // Type extraction
  
  "client_status": "vic",                      // Statut
  "profession": "avocate",                     // Profession exacte
  
  "allergies": ["nickel_allergy"],             // Liste allergies
  "allergy_severity": "high",                  // Sévérité MAX si multiple
  
  "dietary": ["vegan", "gluten_free"],         // Régimes
  
  "relationship_context": {
    "gift_for": ["spouse"],                    // Destinataires
    "shopping_with": ["alone"]                 // Accompagnants
  },
  
  "occasions": ["birthday", "wedding_anniversary"], // Occasions
  "urgency": "this_week",                      // Urgence
  "event_date": "2026-04-15",                  // Date ISO
  "days_until_event": 77,                      // Jours restants
  
  "products_mentioned": ["Birkin 25", "Kelly Sellier"], // Layer 2
  "brands_mentioned": ["Hermès"],              // Layer 2
  "locations": ["Monaco"],                     // Layer 2
  "events": ["Gala Opéra"],                    // Layer 2
  
  "confidence": 0.92,                          // Score 0-1
  "reasoning": "Extraction complète: VIC + budget explicite + date + occasion"
}

═══════════════════════════════════════════════════════════════
📚 EXEMPLES (Few-Shot Learning)
═══════════════════════════════════════════════════════════════

EXEMPLE 1 - Simple:
Input: "Mme Martin cherche sac noir cuir. Budget 3500€."
Output:
{
  "tags": ["leather_goods"],
  "budget_range": "2K-5K",
  "budget_min": 2800,
  "budget_max": 4200,
  "budget_confidence": "explicit",
  "client_status": "regular",
  "profession": null,
  "allergies": [],
  "allergy_severity": "low",
  "dietary": [],
  "relationship_context": {"gift_for": [], "shopping_with": []},
  "occasions": [],
  "urgency": null,
  "event_date": null,
  "products_mentioned": [],
  "confidence": 0.78,
  "reasoning": "Budget explicite, produit clair, pas de contexte complexe"
}

EXEMPLE 2 - VIC Complexe:
Input: "M. Dupont VIC cherche cadeau femme anniversaire 15 avril. 
        Birkin 25 ou Kelly Sellier. Budget très flexible. 
        ATTENTION allergie nickel grave!"
Output:
{
  "tags": ["vic", "gift_for_spouse", "birthday", "nickel_allergy"],
  "budget_range": "20K-50K",
  "budget_min": 20000,
  "budget_max": 60000,
  "budget_confidence": "inferred",
  "client_status": "vic",
  "profession": null,
  "allergies": ["nickel_allergy"],
  "allergy_severity": "high",
  "dietary": [],
  "relationship_context": {
    "gift_for": ["spouse"],
    "shopping_with": []
  },
  "occasions": ["birthday"],
  "urgency": null,
  "event_date": "2026-04-15",
  "days_until_event": 77,
  "products_mentioned": ["Birkin 25", "Kelly Sellier"],
  "brands_mentioned": ["Hermès"],
  "confidence": 0.96,
  "reasoning": "VIC + allergie grave détectée + date précise + budget inféré contexte"
}

EXEMPLE 3 - Multi-produits Urgent:
Input: "Cliente besoin urgent demain: sac work + portefeuille + ceinture matching noir. 
        Budget 8K total."
Output:
{
  "tags": ["leather_goods", "small_leather", "accessories"],
  "budget_range": "5K-10K",
  "budget_min": 6400,
  "budget_max": 9600,
  "budget_confidence": "explicit",
  "client_status": "regular",
  "profession": null,
  "allergies": [],
  "allergy_severity": "low",
  "dietary": [],
  "relationship_context": {"gift_for": [], "shopping_with": []},
  "occasions": [],
  "urgency": "tomorrow",
  "event_date": "2026-01-29",
  "days_until_event": 1,
  "products_mentioned": ["sac work", "portefeuille", "ceinture"],
  "confidence": 0.89,
  "reasoning": "Urgence critique détectée + multi-produits + budget explicite"
}

═══════════════════════════════════════════════════════════════
🎯 INSTRUCTIONS FINALES
═══════════════════════════════════════════════════════════════

- RÉPONDS UNIQUEMENT EN JSON VALIDE (pas de markdown, pas de texte avant/après)
- EXTRAIS TOUTES les données pertinentes (ne laisse RIEN passer)
- INFÈRE budget si VIC/VIP sans mention explicite
- DÉTECTE dates/urgences SYSTÉMATIQUEMENT
- LISTE produits exacts (Layer 2) en PLUS des tags
- CALCULE days_until_event si date future
- JUSTIFIE ton confidence score dans reasoning

Si information manquante/ambiguë: null (pas de guess aléatoire)
Si allergie mentionnée: TOUJOURS extraire severity (analyse contexte)
"""

    def __init__(self, model_tier: str = 'balanced'):
        """
        Initialize Tier 2 Mistral Engine.
        Args:
            model_tier: 'fast', 'balanced', or 'quality'
        """
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            logger.warning("MISTRAL_API_KEY not found. Tier 2 might fail.")
        
        # Mistral native SDK (async-capable)
        self.client = Mistral(api_key=api_key)
        
        self.taxonomy = TaxonomyManager()
        
        # Smart Model Selection
        self.model = self.MODELS.get(model_tier, self.MODELS['balanced'])
        
        # Config per model
        if model_tier == 'fast':
            self.max_tokens = 800
            self.temperature = 0.05
        elif model_tier == 'balanced':
            self.max_tokens = 1200
            self.temperature = 0.07  # Optimized: was 0.1, lower = faster + deterministic
        else:  # quality
            self.max_tokens = 1500
            self.temperature = 0.15
            
        # Robustness Config
        self.timeout_seconds = 15  # Optimized: was 20s, Mistral is fast enough
        self.circuit_breaker = {
            'failures': 0,
            'last_failure': None,
            'threshold': 5,
            'reset_after_seconds': 60
        }
        
        # Metric Tracking
        self.metrics = {
            'total_processed': 0,
            'total_success': 0,
            'total_failures': 0,
            'total_timeouts': 0,
            'total_json_errors': 0,
            'processing_times_ms': [],
            'confidence_scores': [],
            'tags_extracted_total': 0,
            'avg_tags_per_note': 0.0,
            'escalations_to_tier3': 0,
            'model_name': self.model,
            'provider': 'mistral',  # Track provider
            'started_at': datetime.now().isoformat()
        }
        
        # Prompt Cache (économise tokens système)
        self.cache_dir = Path('cache/mistral_prompts')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_cache = {}  # In-memory cache for user prompts
        self.cache_stats = {'hits': 0, 'misses': 0}
        
        logger.info(f"🇫🇷 Tier 2 Mistral initialized with model: {self.model}")

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit is open (too many failures)."""
        if self.circuit_breaker['failures'] < self.circuit_breaker['threshold']:
            return True  # Circuit closed, OK to proceed
        
        # Circuit open, check if reset period elapsed
        if self.circuit_breaker['last_failure']:
            elapsed = (datetime.now() - self.circuit_breaker['last_failure']).seconds
            if elapsed > self.circuit_breaker['reset_after_seconds']:
                logger.info("Circuit breaker reset")
                self.circuit_breaker['failures'] = 0
                return True
        
        logger.warning("Circuit breaker OPEN - too many Mistral failures")
        return False
    
    def _record_failure(self):
        """Record failure for circuit breaker."""
        self.circuit_breaker['failures'] += 1
        self.circuit_breaker['last_failure'] = datetime.now()
    
    def _record_success(self):
        """Record success (reset failure count)."""
        if self.circuit_breaker['failures'] > 0:
            logger.info(f"Mistral success after {self.circuit_breaker['failures']} failures - resetting")
            self.circuit_breaker['failures'] = 0

    def _record_extraction(self, result: Optional[ExtractionResult], processing_time_ms: float, success: bool = True):
        """Update internal metrics."""
        self.metrics['total_processed'] += 1
        
        if success and result:
            self.metrics['total_success'] += 1
            self.metrics['processing_times_ms'].append(processing_time_ms)
            self.metrics['confidence_scores'].append(result.confidence)
            self.metrics['tags_extracted_total'] += len(result.tags)
            
            if result.confidence < 0.75:
                self.metrics['escalations_to_tier3'] += 1
                
            # Update averages
            if self.metrics['total_success'] > 0:
                self.metrics['avg_tags_per_note'] = (
                    self.metrics['tags_extracted_total'] / self.metrics['total_success']
                )
        else:
            self.metrics['total_failures'] += 1

    # ═══════════════════════════════════════════════════════════════
    # PROMPT CACHE METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def _get_cache_key(self, text: str, language: str) -> str:
        """Generate cache key from text hash."""
        content = f"{language}:{text}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_from_cache(self, cache_key: str) -> Optional[ExtractionResult]:
        """Load result from cache if exists and not expired (24h TTL)."""
        cache_path = self.cache_dir / f"{cache_key}.json"
        
        if not cache_path.exists():
            return None
        
        try:
            # Check TTL (24 hours)
            age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
            if age_hours > 24:
                cache_path.unlink()  # Delete expired
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct ExtractionResult
            return ExtractionResult(**data)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, result: ExtractionResult):
        """Save result to cache."""
        cache_path = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                # Use model_dump() for Pydantic v2
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    @safe_execution(default_return=ExtractionResult(extracted_by="tier2_mistral_fallback", processing_tier="tier2", confidence=0.0))
    @retry_with_backoff(retries=2)
    async def extract(self, text: str, language: str = 'FR') -> ExtractionResult:
        """
        Async extraction with Timeout, Circuit Breaker, Caching, and Metrics.
        """
        start_time = time.time()
        
        # === PROMPT CACHE CHECK ===
        cache_key = self._get_cache_key(text, language)
        cached_result = self._load_from_cache(cache_key)
        if cached_result:
            self.cache_stats['hits'] += 1
            logger.debug(f"Cache HIT for prompt (saves ~2500 tokens)")
            return cached_result
        
        self.cache_stats['misses'] += 1
        
        # Check circuit breaker
        if not self._check_circuit_breaker():
            raise Exception("Circuit breaker OPEN - Mistral unavailable")
            
        prompt = f"Langue: {language}\n\nNOTE CLIENT:\n\"{text}\"\n\nExtrais les informations et réponds en JSON."
        
        try:
            # Call Mistral with Timeout (async)
            response = await asyncio.wait_for(
                self.client.chat.complete_async(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                ),
                timeout=self.timeout_seconds
            )
            
            self._record_success()
            
            content = response.choices[0].message.content
            result_dict = json.loads(content)
            
            # Formater le résultat de manière défensive
            result = self._format_result_safe(result_dict)
            
            # === SAVE TO CACHE ===
            self._save_to_cache(cache_key, result)
            
            processing_time = (time.time() - start_time) * 1000
            self._record_extraction(result, processing_time, success=True)
            
            return result

        except asyncio.TimeoutError:
            logger.error(f"Mistral API timeout after {self.timeout_seconds}s")
            self._record_failure()
            self.metrics['total_timeouts'] += 1
            self._record_extraction(None, 0, success=False)
            raise Exception(f"Mistral timeout ({self.timeout_seconds}s)")
            
        except json.JSONDecodeError as e:
            logger.error(f"Mistral JSON parsing error: {e}")
            self._record_failure()
            self.metrics['total_json_errors'] += 1
            self._record_extraction(None, 0, success=False)
            raise Exception(f"Invalid JSON from Mistral: {e}")
            
        except Exception as e:
            logger.error(f"Mistral API error: {e}")
            self._record_failure()
            self._record_extraction(None, 0, success=False)
            raise e

    def _format_result_safe(self, result_dict: Dict) -> ExtractionResult:
        """Robust formatting with defensive type checks everywhere."""
        
        # Helpers
        def safe_list_extract(value, default: List = None) -> List:
            if default is None: default = []
            if value is None: return default
            if isinstance(value, list): return [v for v in value if isinstance(v, str)]
            if isinstance(value, str): return [value] if value.strip() else default
            if isinstance(value, dict):
                res = []
                for v in value.values():
                    if isinstance(v, list): res.extend([i for i in v if isinstance(i, str)])
                    elif isinstance(v, str): res.append(v)
                return res
            return default

        def safe_string_extract(value, default: str = None) -> Optional[str]:
            if value is None: return default
            if isinstance(value, str): return value.strip() if value.strip() else default
            if isinstance(value, (int, float)): return str(value)
            return default

        def safe_int_extract(value, default: int = None) -> Optional[int]:
            if value is None: return default
            if isinstance(value, int): return value
            if isinstance(value, float): return int(value)
            if isinstance(value, str):
                try: return int(value.replace(',', '').replace('€', '').replace('K', '000').strip())
                except: return default
            return default

        def safe_float_extract(value, default: float = 0.75, min_val: float = 0.0, max_val: float = 1.0) -> float:
            if value is None: return default
            if isinstance(value, (int, float)): return max(min_val, min(max_val, float(value)))
            if isinstance(value, str):
                try:
                    val = float(value.strip('%').replace(',', '.'))
                    if val > 1.0: val = val / 100.0
                    return max(min_val, min(max_val, val))
                except: return default
            return default

        try:
            # Tags & Relations
            raw_tags = safe_list_extract(result_dict.get('tags'), [])
            rel_context = result_dict.get('relationship_context', {})
            
            clean_rel_context = {}
            if isinstance(rel_context, dict):
                gift_for = safe_list_extract(rel_context.get('gift_for'))
                shopping_with = safe_list_extract(rel_context.get('shopping_with'))
                clean_rel_context = {'gift_for': gift_for, 'shopping_with': shopping_with}
                
                for r in gift_for: raw_tags.append(f'gift_for_{r}')
                for r in shopping_with: raw_tags.append(f'shopping_with_{r}')
            
            # Validate tags
            valid_tags = []
            for tag in raw_tags:
                normalized = self.taxonomy.normalize_tag(tag)
                if normalized:
                    valid_tags.append(normalized)
                elif tag.startswith(('gift_for_', 'shopping_with_')):
                    valid_tags.append(tag)

            # Budget
            budget_range = safe_string_extract(result_dict.get('budget_range'))
            budget_min = safe_int_extract(result_dict.get('budget_min'))
            budget_max = safe_int_extract(result_dict.get('budget_max'))
            budget_confidence = safe_string_extract(result_dict.get('budget_confidence'), 'unknown')

            # Client
            client_status = safe_string_extract(result_dict.get('client_status'))
            profession = safe_string_extract(result_dict.get('profession'))

            # Health
            allergies = safe_list_extract(result_dict.get('allergies'), [])
            sev = safe_string_extract(result_dict.get('allergy_severity'), 'low')
            allergy_severity = sev if sev in ['low', 'medium', 'high'] else 'medium'
            dietary = safe_list_extract(result_dict.get('dietary'), [])

            # Temporal
            occasions = safe_list_extract(result_dict.get('occasions'), [])
            urgency = safe_string_extract(result_dict.get('urgency'))
            event_date = safe_string_extract(result_dict.get('event_date'))
            days_until = safe_int_extract(result_dict.get('days_until_event'))

            # Layer 2
            products_mentioned = safe_list_extract(result_dict.get('products_mentioned'), [])
            brands_mentioned = safe_list_extract(result_dict.get('brands_mentioned'), [])
            locations = safe_list_extract(result_dict.get('locations'), [])
            events = safe_list_extract(result_dict.get('events'), [])

            # Metadata
            confidence = safe_float_extract(result_dict.get('confidence'), 0.85)
            reasoning = safe_string_extract(result_dict.get('reasoning'), 'No reasoning provided')

            return ExtractionResult(
                tags=list(set(valid_tags)),
                brief_summary=reasoning[:100], # compatibility
                budget_range=budget_range,
                budget_min=budget_min,
                budget_max=budget_max,
                budget_confidence=budget_confidence,
                client_status=client_status,
                profession=profession,
                allergies=allergies,
                allergy_severity=allergy_severity,
                dietary=dietary,
                occasions=occasions,
                urgency=urgency,
                event_date=event_date,
                days_until_event=days_until,
                products_mentioned=products_mentioned,
                brands_mentioned=brands_mentioned,
                locations=locations,
                events=events,
                relationship_context=clean_rel_context,
                confidence=confidence,
                reasoning=reasoning,
                processing_tier="tier2",
                extracted_by="tier2_mistral",
                model_name=self.model,
                cost=0.0  # Free tier!
            )

        except Exception as e:
            logger.error(f"Fatal error formatting Mistral result: {e}")
            logger.error(f"Raw result_dict: {result_dict}")
            raise e

    def get_metrics_summary(self) -> Dict:
        """Get metrics summary."""
        success_rate = (self.metrics['total_success'] / max(1, self.metrics['total_processed']) * 100)
        avg_time = (statistics.mean(self.metrics['processing_times_ms']) if self.metrics['processing_times_ms'] else 0)
        
        return {
            'provider': '🇫🇷 Mistral (EU)',
            'model': self.metrics['model_name'],
            'total_processed': self.metrics['total_processed'],
            'success_rate': f"{success_rate:.1f}%",
            'avg_processing_time_ms': f"{avg_time:.0f}ms",
            'errors': {
                'timeouts': self.metrics['total_timeouts'],
                'json_errors': self.metrics['total_json_errors'],
                'other': self.metrics['total_failures'] - self.metrics['total_timeouts'] - self.metrics['total_json_errors']
            }
        }
