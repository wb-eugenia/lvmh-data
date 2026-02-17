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

from src.models import (
    ExtractionResult, Pilier1Product, Pilier2Client, Pilier3Care, Pilier4Business,
    MetaAnalysis, ProductPreferences, PurchaseContext, Profession, Lifestyle, Allergies
)

# ... (Previous code)


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

═══════════════════════════════════════════════════════════════
⚠️ RÈGLE CRITIQUE PROFESSION
═══════════════════════════════════════════════════════════════

NE JAMAIS INVENTER/INFÉRER UNE PROFESSION.

EXTRACTION PROFESSION = EXPLICITE UNIQUEMENT:
✅ "Je suis avocate" → profession: "legal_lawyer"
✅ "Médecin urgentiste" → profession: "medical_physician"
✅ "Banquier privé" → profession: "finance_banker"

❌ "Cliente Hong Kong" → profession: null
❌ "VIP Monaco" → profession: null
❌ "Shopping Champs-Élysées" → profession: null

SIGNAUX GÉOGRAPHIQUES = LOCATIONS (Layer 2), PAS profession.
Si aucune mention explicite de profession: profession = null.

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
💰 BUDGET & TIERS (Smart Inference!)
═══════════════════════════════════════════════════════════════

RANGES & TIERS:
- under_2K (entry_level)
- 2K-5K (core)
- 5K-15K (high)
- 15K+ (ultra_high)
- flexible_unknown

EXPLICITE:
- "5000€", "5K", "entre 5 et 10K" → Extract montant exact

IMPLICITE (INFÉRENCE REQUISE):
- "flexible" + VIC → 15K+
- "ouvert" + VIP → 15K+
- "sans limite" → 50K+
- "budget serré" → under_2K
- Pas de mention budget + first_visit → 2K-5K

═══════════════════════════════════════════════════════════════
🎨 PRÉFÉRENCES (Layer 1.5)
═══════════════════════════════════════════════════════════════

COULEURS:
- black, brown_cognac, navy, beige_neutral, bold_colors

MATÉRIAUX:
- smooth_leather, grained_leather, canvas, exotic, suede

USAGE:
- professional_work, travel, evening, casual_daily, gift

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
  
  "budget_tier": "high",                       // entry_level, core, high, ultra_high
  "budget_range": "5K-15K",                    // Range standard
  "budget_min": 5000,                          // Min (si inféré)
  "budget_max": 15000,                         // Max (si inféré)
  "budget_confidence": "explicit|inferred",    // Type extraction
  
  "materials": ["smooth_leather"],             // Liste matériaux
  "colors": ["black"],                         // Liste couleurs
  "usage_context": ["professional_work"],      // Usage principal
  
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
        # Use key rotator for multiple student accounts
        try:
            from src.mistral_rotator import get_mistral_rotator
            self._rotator = get_mistral_rotator()
            api_key = self._rotator.get_key()
        except ImportError:
            self._rotator = None
            api_key = os.getenv("MISTRAL_API_KEY")
        
        if not api_key:
            logger.warning("MISTRAL_API_KEY not found. Tier 2 might fail.")
        
        # Mistral native SDK (async-capable)
        self.client = Mistral(api_key=api_key)
        
        # Rotate to next key (for load balancing)
        self._rotate_client_key()
        
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
        self.timeout_seconds = 10  # Optimized: was 15s, reduced for faster response
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
    
    def _rotate_client_key(self):
        """Rotate to next Mistral key (for load balancing across accounts)."""
        if self._rotator and self._rotator.key_count > 1:
            new_key = self._rotator.rotate()
            self.client = Mistral(api_key=new_key)
            logger.info(f"Rotated to next Mistral API key")
    
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

    @safe_execution(default_return=ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(confidence_score=0.0),
        processing_tier="tier2",
        extracted_by="tier2_mistral_fallback",
        confidence=0.0,
        rgpd_flag=False,
        from_cache=False
    ))
    @retry_with_backoff(retries=1)
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
            
        user_payload = {
            "language": language,
            "note_client": text,
            "task": "Extraire les informations business-critiques selon le system prompt.",
            "output_format": "json_object",
        }
        prompt = json.dumps(user_payload, ensure_ascii=False)
        
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
            self._rotate_client_key()  # Rotate key on timeout
            self._record_failure()
            self.metrics['total_timeouts'] += 1
            self._record_extraction(None, 0, success=False)
            raise Exception(f"Mistral timeout ({self.timeout_seconds}s)")
            
        except json.JSONDecodeError as e:
            logger.error(f"Mistral JSON parsing error: {e}")
            self._rotate_client_key()  # Rotate key on error
            self._record_failure()
            self.metrics['total_json_errors'] += 1
            self._record_extraction(None, 0, success=False)
            raise Exception(f"Invalid JSON from Mistral: {e}")
            
        except Exception as e:
            logger.error(f"Mistral API error: {e}")
            self._rotate_client_key()  # Rotate key on error
            self._record_failure()
            self._record_extraction(None, 0, success=False)
            raise e

    def _format_result_safe(self, result_dict: Dict) -> ExtractionResult:
        """Robust formatting for Taxonomie V2 (4 Piliers)."""
        
        # Helpers
        def get_d(d, k): return d.get(k, {}) if isinstance(d, dict) else {}
        def safe_list(val): return [str(v) for v in val] if isinstance(val, list) else []
        def safe_str(val): return str(val).strip() if val else None
        
        try:
            # Map simplified Tier 2 JSON to strict V2 Models
            # Note: Tier 2 prompt might still return flat JSON if we didn't update the prompt.
            # Ideally we should update the prompt too, but for now we map flat -> structured.
            
            # --- Taxonomy Routing ---
            raw_tags = safe_list(result_dict.get('tags', []))
            categories = []
            occasions = safe_list(result_dict.get('occasions', []))
            
            for t in raw_tags:
                norm = self.taxonomy.normalize_tag(t)
                if not norm: continue
                
                # If it's in core_tags['occasions'], move it there
                if norm in self.taxonomy.get_category_tags('occasions'):
                    if norm not in occasions: occasions.append(norm)
                # If it's in core_tags['context'] (like VIP, urgencies if any), route accordingly
                elif norm in self.taxonomy.get_category_tags('context'):
                    # Context tags can stay in categories for now as "contextual tags"
                    categories.append(norm)
                else:
                    categories.append(norm)

            # --- Pilier 1 ---
            p1 = Pilier1Product(
                categories=categories, 
                usage=safe_list(result_dict.get('usage_context', [])),
                preferences=ProductPreferences(
                    colors=safe_list(result_dict.get('colors', [])),
                    materials=safe_list(result_dict.get('materials', []))
                )
            )
            
            # --- Pilier 2 ---
            p2 = Pilier2Client(
                purchase_context=PurchaseContext(
                    type="Self" if "self" in str(result_dict) else "Gift",
                    behavior=safe_str(result_dict.get('client_status'))
                ),
                profession=Profession(
                    sector=self._sanitize_profession(
                        safe_str(result_dict.get('profession')),
                        locations=safe_list(result_dict.get('locations', [])),
                    )
                ),
                lifestyle=Lifestyle()
            )
            
            # --- Pilier 3 ---
            p3 = Pilier3Care(
                diet=safe_list(result_dict.get('dietary', [])),
                allergies=Allergies(
                    food=[a for a in safe_list(result_dict.get('allergies', []))]
                ),
                occasion=occasions[0] if occasions else None
            )
            
            # --- Pilier 4 ---
            urgency = safe_str(result_dict.get('urgency'))
            # If urgency is a valid tag (like this_month), normalize it
            if urgency:
                 norm_urg = self.taxonomy.normalize_tag(urgency)
                 if norm_urg: urgency = norm_urg

            p4 = Pilier4Business(
                lead_temperature="Warm",
                urgency=urgency,
                budget_potential=f"{safe_str(result_dict.get('budget_tier'))} ({safe_str(result_dict.get('budget_range'))})"
            )
            
            # --- Meta ---
            conf = float(result_dict.get('confidence', 0.8))
            meta = MetaAnalysis(confidence_score=conf)
            
            return ExtractionResult(
                pilier_1_univers_produit=p1,
                pilier_2_profil_client=p2,
                pilier_3_hospitalite_care=p3,
                pilier_4_action_business=p4,
                meta_analysis=meta,
                
                # Metadata
                processing_tier="tier2",
                confidence=conf,
                rgpd_flag=False,
                from_cache=False,
                error=None
            )

        except Exception as e:
            logger.error(f"Error formatting Tier 2 result: {e}")
            # Minimal fallback
            return ExtractionResult(
                pilier_1_univers_produit=Pilier1Product(),
                pilier_2_profil_client=Pilier2Client(),
                pilier_3_hospitalite_care=Pilier3Care(),
                pilier_4_action_business=Pilier4Business(),
                meta_analysis=MetaAnalysis(confidence_score=0.0),
                processing_tier="tier2",
                confidence=0.0,
                error=str(e),
                from_cache=False,
                rgpd_flag=False
            )

    def _sanitize_profession(self, value: Optional[str], locations: Optional[List[str]] = None) -> Optional[str]:
        """Prevent geography/status noise from being persisted as profession."""
        if not value:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        lower = normalized.lower()
        blocked_values = {
            "vip",
            "vic",
            "ultimate",
            "regular",
            "client",
            "unknown",
            "none",
            "null",
        }
        if lower in blocked_values:
            return None

        # Common location-only values occasionally hallucinated as profession.
        blocked_location_tokens = {
            "hong kong",
            "monaco",
            "dubaï",
            "dubai",
            "paris",
            "london",
            "new york",
            "milan",
            "tokyo",
            "singapore",
        }
        if lower in blocked_location_tokens:
            return None

        if locations:
            normalized_locations = {str(loc).strip().lower() for loc in locations if str(loc).strip()}
            if lower in normalized_locations:
                return None

        return normalized

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
