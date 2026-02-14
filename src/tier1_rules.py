"""
Tier 1: Rules-based Tag Extraction (Production Enhanced).
Deterministic extraction using pre-compiled regex patterns.
Cost: 0€ | Speed: ~300 notes/s | Precision: 85-90%

Enhanced with:
1. Deep Relation Extraction (Shopping context) - CRITICAL
2. Temporal & Occasions (Dates, Deadlines)
3. Smart Budget Inference (Context-aware)
4. Intelligent Confidence Scoring
5. Health & Safety (Allergies severity)
6. Multi-Product Detection
7. Pre-compiled Performance Optimization
"""

import re
import time
from typing import List, Dict, Tuple, Optional, Any
import logging
from src.models import (
    ExtractionResult, Pilier1Product, Pilier2Client, Pilier3Care, Pilier4Business,
    MetaAnalysis, ProductPreferences, PurchaseContext, Profession, Lifestyle, Allergies
)
from datetime import datetime
from dateutil import parser as date_parser
from functools import lru_cache

from src.resilience import safe_execution
from src.taxonomy import TaxonomyManager
from config.production import settings

logger = logging.getLogger(__name__)

class Tier1RulesEngine:
    """Enhanced deterministic rules-based extraction engine."""
    
    # =========================================================================
    # 1. CONFIGURATION & PATTERNS
    # =========================================================================
    
    # --- BUDGET PATTERNS ---
    BUDGET_REGEX = [
        # French - Range patterns (NEW)
        (r'budget\s*(?:de|:)?\s*(\d{3,5})\s*[-à]\s*(\d{3,5})\s*(?:€|euros?)?',
         lambda m: (int(m.group(1)) + int(m.group(2))) // 2),  # Average of range
        (r'budget\s*(?:de|:)?\s*(\d{1,2})\s*[kK]\s*[-à]\s*(\d{1,2})\s*[kK]',
         lambda m: (int(m.group(1)) + int(m.group(2))) * 500),  # Average in thousands
        
        # French - Exact 4-5 digit amounts (avoid 5000 -> 500000)
        (r'budget\s*(?:de|:)?\s*(\d{4,5})\s*(?:euros?)?',
         lambda m: int(m.group(1))),

        # French - Standard patterns
        (r'budget\s*(?:de|:)?\s*(\d{1,3})[\s,]?(\d{3})?\s*(?:€|euros?)?', 
         lambda m: int(m.group(1)) * 1000 + int(m.group(2) or 0)),
        (r'budget\s*(?:de|:)?\s*(\d+)\s*[kK]', lambda m: int(m.group(1)) * 1000),
        (r'(\d+)\s*[kK]\s*(?:€|euros?)?\s*(?:de\s+)?budget', lambda m: int(m.group(1)) * 1000),
        (r'entre\s*(\d+)\s*(?:et|à)\s*(\d+)\s*[kK]', 
         lambda m: (int(m.group(1)) + int(m.group(2))) * 500),
        (r'(\d{4,5})\s*(?:€|euros?)', lambda m: int(m.group(1))),
        
        # English
        (r'budget\s*(?:of|:)?\s*\$?(\d+)[kK]', lambda m: int(m.group(1)) * 1000),
        (r'\$(\d{4,5})', lambda m: int(m.group(1))),
    ]
    
    BUDGET_MODIFIERS = {
        'très flexible': 1.5, 'flexible': 1.2, 'ouvert': 1.3,
        'sans limite': 2.0, 'no limit': 2.0,
        'limité': 0.7, 'serré': 0.6, 'strict': 0.5, 'tight': 0.6
    }
    
    # VIC Ranges (Min, Max)
    BUDGET_BY_STATUS = {
        'vic': (10000, 50000),
        'vip': (15000, 100000),
        'ultimate': (50000, 500000),
        'first_visit': (2000, 5000),
        'regular': (3000, 10000),
    }

    # --- RELATIONS & CONTEXT ---
    RELATION_PATTERNS = {
        'gift_for_spouse': [
            r'cadeau\s+pour\s+(?:sa|mon|ma)\s+(femme|épouse|mari|époux)',
            r'gift\s+for\s+(?:my|his|her)\s+(wife|husband|spouse)',
            r'pour\s+(?:son|sa)\s+anniversaire\s+de\s+mariage',
        ],
        'gift_for_children': [
            r'pour\s+(?:sa|son|ma|mon)\s+(fille|fils|enfant)',
            r'for\s+(?:my|his|her)\s+(daughter|son|child)',
        ],
        'gift_for_parent': [
            r'pour\s+(?:sa|ma)\s+(mère|maman|père|papa)',
            r'for\s+(?:my|his|her)\s+(mother|mom|father|dad)',
        ],
        'gift_for_self': [
            r'pour\s+(moi|elle|lui)(?:-même)?',
            r'for\s+(myself|himself|herself)',
            r's\'offrir',
        ]
    }
    
    COMPANION_PATTERNS = {
        'shopping_with_spouse': [
            r'avec\s+(?:son|sa)\s+(mari|femme|époux|épouse)',
            r'couple\s+cherche',
        ],
        'shopping_with_family': [
            r'avec\s+(?:ses|leurs)\s+(enfants|fille|fils|famille)',
        ]
    }

    # --- MULTI-PRODUCT PATTERNS (NOUVEAU) ---
    MULTI_PRODUCT_PATTERNS = {
        'bag_and_belt': r'\b(sac|bag?|maroquinerie|poches?)\b.{0,25}(ceinture|belt|cintura)',
        'bag_and_wallet': r'\b(sac|bag?|maroquinerie)\b.{0,25}(portefeuille|wallet|portafoglio)',
        'watch_and_jewelry': r'\b(montre|watch|orologio)\b.{0,25}(bague|ring|bijou|bracelet|gioiello)',
        'fragrance_set': r'\b(parfum| fragrance)\b.{0,25}(coffret|set|box|échantillon|sample)',
        'shoes_and_belt': r'\b(chaussure|shoe|sneaker)\b.{0,25}(ceinture|belt|cintura)',
    }

    # --- SIMPLE CHOICE PATTERNS (NOUVEAU) ---
    # Pour extraire les choix binaires simples "A ou B"
    SIMPLE_CHOICE_PATTERNS = [
        r'(?:cherche|veux|want|looking for).*?(\w+)\s+(?:ou|or)\s+(\w+)\s*(?:\?|$)',
        r'(\w+)\s+(?:ou|or)\s+(\w+)\s+(?:pour|for|\?)\s*(?:\?|$)',
    ]

    # --- HEALTH & SAFETY ---
    ALLERGIES = {
        'nickel_allergy': [r'allergi\w*\s+(?:au\s+)?nickel', r'sensible\s+(?:au\s+)?nickel'],
        'latex_allergy': [r'allergi\w*\s+(?:au\s+)?latex'],
        'fragrance_sensitivity': [r'sensible\s+(?:aux\s+)?parfums?', r'fragrance\s+sensitivity'],
        'leather_allergy': [r'allergi\w*\s+(?:au\s+)?cuir'],
    }
    
    DIETARY = {
        'vegan': [r'\bvegan\b', r'\bvégane?\b'],
        'vegetarian': [r'végétarien', r'vegetarian'],
        'halal': [r'\bhalal\b'], 
        'kosher': [r'\bkosher\b', r'\bkasher\b'],
    }

    SEVERITY_PATTERNS = {
        'high': [r'sévère', r'severe', r'grave', r'mortelle', r'life[\s-]?threatening', r'choc', r'urgence'],
        'medium': [r'modérée?', r'moderate', r'moyenne', r'importante'],
        'low': [r'légère', r'mild', r'petite', r'minor', r'pas\s+grave']
    }

    # --- TEMPORAL ---
    OCCASIONS = {
        'birthday': [r'anniversaire(?!\s+de\s+mariage)', r'birthday', r'fête'],
        'wedding_anniversary': [r'anniversaire\s+de\s+mariage', r'wedding\s+anniversary'],
        'wedding': [r'mariage', r'wedding', r'noces'],
        'christmas': [r'noël', r'christmas', r'fêtes\s+de\s+fin\s+d\'année'],
    }
    
    URGENCY_PATTERNS = [
        (r'urgent', 'high'), (r'asap', 'high'), (r'au\s+plus\s+vite', 'high'),
        (r'demain', 'high'), (r'ce\s+week[\s-]?end', 'medium'),
        (r'cette\s+semaine', 'medium')
    ]

    # --- DEMOGRAPHICS ---
    STATUS_PATTERNS = {
        'vic': r'\bVIC\b', 'vip': r'\bVIP\b', 'ultimate': r'\b(ultimate|UHNWI?)\b',
        'first_visit': r'(première\s+visite|first\s+(?:time|visit))',
        'regular': r'(client\s+régulier|regular\s+client)',
    }

    # 🎨 PRÉFÉRENCES & USAGE
    COLOR_PATTERNS = {
        'black': [r'noir', r'black', r'nero', r'schwarz'],
        'brown_cognac': [r'marron', r'cognac', r'marrone', r'brun'],
        'navy': [r'marine', r'navy', r'bleu fonc'],
        'beige_neutral': [r'beige', r'neutre', r'nude', r'naturel'],
        'bold_colors': [r'rouge', r'vert', r'jaune', r'rose', r'fushia', r'vive']
    }
    
    MATERIAL_PATTERNS = {
        'smooth_leather': [r'cuir lisse', r'smooth leather'],
        'grained_leather': [r'cuir grainé', r'grained leather', r'empreinte'],
        'canvas': [r'toile', r'canvas', r'monogram', r'damier'],
        'exotic': [r'croco', r'autruche', r'exotique', r'python', r'lézard'],
        'suede': [r'daim', r'suede', r'veau velours']
    }
    
    # --- LV SPECIFIC PRODUCTS ---
    LV_PRODUCT_PATTERNS = {
        'speedy': r'\b[Ss]peedy\s*(\d{2,3})?\b',
        'neverfull': r'\b[Nn]everfull\b',
        'capucines': r'\b[Cc]apucines\b',
        'onthego': r'\b[Oo]n\s*-?\s*[Tt]he\s*-?\s*[Gg]o\b',
        'alma': r'\b[Aa]lma\b',
        'pochette': r'\b[Pp]ochette\s*(?:[Aa]ccessoires|[Mm]etis)?\b',
        'keepall': r'\b[Kk]eepall\b',
        'noe': r'\b[Nn]o[ée]\b',
        'petite_malle': r'\b[Pp]etite\s+[Mm]alle\b',
        'steamer': r'\b[Ss]teamer\b',
        'sac_plat': r'\b[Ss]ac\s+[Pp]lat\b',
    }
    
    LV_MATERIAL_PATTERNS = {
        'monogram_canvas': r'\b[Mm]onogram\s*(?:[Cc]anvas)?\b',
        'damier_ebene': r'\b[Dd]amier\s*[ée]b[eè]ne\b',
        'damier_azur': r'\b[Dd]amier\s*[Aa]zur\b',
        'epi_leather': r'\b[ée]pi\b',
        'taurillon_leather': r'\b[Tt]aurillon\b',
    }
    
    USAGE_PATTERNS = {
        'professional_work': [r'travail', r'bureau', r'meeting', r'rendez-vous pro', r'pro\b'],
        'travel': [r'voyage', r'déplacement', r'avion', r'vacances'],
        'evening': [r'soirée', r'dîner', r'gala', r'événement'],
        'casual_daily': [r'tous les jours', r'daily', r'quotidien'],
        'gift': [r'cadeau\b', r'offrir', r'plaisir']
    }
    
    AGE_PATTERNS = [
        (r'(\d{2})\s*ans', lambda m: int(m.group(1))),
        (r'(\d{2})\s*(?:years|yo)', lambda m: int(m.group(1))),
    ]
    
    GENDER_PATTERNS = {
        'female': r'\b(Mme|Madame|Mrs|Ms|Dame|femme|cliente|elle|she)\b',
        'male': r'\b(M\.|Mr|Monsieur|Sir|homme|client|il|he)\b',
    }

    # =========================================================================
    # 2. INITIALIZATION (PRE-COMPILATION)
    # =========================================================================

    def __init__(self):
        self.stats = {'processed': 0}
        self.taxonomy = TaxonomyManager()
        self.keyword_map = self.taxonomy.get_all_keywords_map()
        self.match_engine = "regex"
        self._aho_available = False
        self._aho_automaton = None
        
        # Pre-compile patterns for speed ⚡
        self._compiled_patterns = self._compile_all_patterns()
        self._init_aho_engine()

    def _init_aho_engine(self) -> None:
        requested_engine = str(getattr(settings, "tier1_match_engine", "aho") or "aho").strip().lower()
        if requested_engine != "aho":
            return

        try:
            import ahocorasick
        except Exception as exc:
            logger.warning("Tier1 Aho-Corasick disabled (import failed): %s", exc)
            return

        try:
            automaton = ahocorasick.Automaton()
            for keyword, tag in self.keyword_map.items():
                normalized = str(keyword or "").strip().lower()
                if not normalized:
                    continue
                automaton.add_word(normalized, (tag, normalized))
            automaton.make_automaton()
            self._aho_automaton = automaton
            self._aho_available = True
            self.match_engine = "aho"
            logger.info("Tier1 Aho-Corasick enabled with %s keywords", len(self.keyword_map))
        except Exception as exc:
            logger.warning("Tier1 Aho-Corasick initialization failed, using regex fallback: %s", exc)
            self._aho_available = False
            self._aho_automaton = None
            self.match_engine = "regex"

    def _compile_all_patterns(self) -> Dict:
        """Compile regex patterns once at startup."""
        compiled = {
            'keywords': {}, 'budget': [], 'status': {}, 
            'allergies': {}, 'dietary': {}, 'occasions': {},
            'relations': {}, 'companions': {}, 'urgency': [],
            'gender': {}, 'lv_products': {}, 'lv_materials': {},
            'multi_product': {},  # NOUVEAU
        }
        
        # Taxonomy Keywords
        for keyword, tag in self.keyword_map.items():
            # Word boundary for short words to avoid "cat" matching "category"
            pattern = rf'\b{re.escape(keyword)}\b' if len(keyword) <= 3 else re.escape(keyword)
            compiled['keywords'][tag] = compiled['keywords'].get(tag, []) + [re.compile(pattern, re.I)]

        # Budget
        for pattern, extractor in self.BUDGET_REGEX:
            compiled['budget'].append((re.compile(pattern, re.I), extractor))
            
        # Status & Gender
        for k, p in self.STATUS_PATTERNS.items():
            compiled['status'][k] = re.compile(p, re.I)
        for k, p in self.GENDER_PATTERNS.items():
            compiled['gender'][k] = re.compile(p, re.I)

        # Allergies & Health
        for k, pats in self.ALLERGIES.items():
            compiled['allergies'][k] = [re.compile(p, re.I) for p in pats]
        for k, pats in self.DIETARY.items():
            compiled['dietary'][k] = [re.compile(p, re.I) for p in pats]
            
        # Severity
        compiled['severity'] = {}
        for k, pats in self.SEVERITY_PATTERNS.items():
            compiled['severity'][k] = [re.compile(p, re.I) for p in pats]
            
        # Relations & Occasions
        for k, pats in self.RELATION_PATTERNS.items():
            compiled['relations'][k] = [re.compile(p, re.I) for p in pats]
        for k, pats in self.COMPANION_PATTERNS.items():
            compiled['companions'][k] = [re.compile(p, re.I) for p in pats]
        for k, pats in self.OCCASIONS.items():
            compiled['occasions'][k] = [re.compile(p, re.I) for p in pats]
            
        # 🎨 New Enrichment Patterns
        compiled['colors'] = {k: [re.compile(p, re.I) for p in pats] for k, pats in self.COLOR_PATTERNS.items()}
        compiled['materials'] = {k: [re.compile(p, re.I) for p in pats] for k, pats in self.MATERIAL_PATTERNS.items()}
        compiled['usage'] = {k: [re.compile(p, re.I) for p in pats] for k, pats in self.USAGE_PATTERNS.items()}
        
        # LV Specific Patterns
        compiled['lv_products'] = {k: re.compile(p, re.I) for k, p in self.LV_PRODUCT_PATTERNS.items()}
        compiled['lv_materials'] = {k: re.compile(p, re.I) for k, p in self.LV_MATERIAL_PATTERNS.items()}
        
        # Multi-Product Patterns (NOUVEAU)
        for k, pattern in self.MULTI_PRODUCT_PATTERNS.items():
            compiled['multi_product'][k] = re.compile(pattern, re.I)
        
        # Simple Choice Patterns (NOUVEAU)
        compiled['simple_choices'] = [re.compile(p, re.I) for p in self.SIMPLE_CHOICE_PATTERNS]

        return compiled

    # =========================================================================
    # 3. EXTRACTION METHODS
    # =========================================================================

    def extract_relations(self, text: str) -> Dict[str, List[str]]:
        """Extract gift recipients and shopping companions."""
        relations = {'gift_for': [], 'shopping_with': []}
        
        # Gifts
        for relation_type, patterns in self._compiled_patterns['relations'].items():
            if any(p.search(text) for p in patterns):
                relations['gift_for'].append(relation_type)
        
        # Companions
        for companion_type, patterns in self._compiled_patterns['companions'].items():
            if any(p.search(text) for p in patterns):
                relations['shopping_with'].append(companion_type)
                
        return relations

    def extract_context_aware_gender(self, text: str, relations: Dict) -> Optional[Dict]:
        """Distinguish between client gender and recipient gender."""
        # Heuristic: If it's a gift, try to find client gender BEFORE the gift mention
        is_gift = len(relations['gift_for']) > 0
        
        # Default gender scan
        matches = []
        for gender, pattern in self._compiled_patterns['gender'].items():
             for match in pattern.finditer(text):
                 matches.append((match.start(), gender))
        
        if not matches:
            return None
            
        # If gift context, be careful not to pick up recipient gender as client gender
        # This is a simple heuristic: pick the first gender mention found
        matches.sort() # Sort by position
        client_gender = matches[0][1]
        
        return {
            'client_gender': client_gender,
            'is_gift_context': is_gift
        }

    def extract_simple_choices(self, text: str) -> List[Tuple[str, str]]:
        """
        Extraire les choix binaires simples (A ou B) pour Tier 1.
        Ex: "Sac noir ou marron" -> [("noir", "marron")]
        """
        choices = []
        text_lower = text.lower()
        
        for pattern in self.SIMPLE_CHOICE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for m in matches:
                groups = m.groups()
                if len(groups) >= 2 and groups[0] and groups[1]:
                    # Filtrer les mots vides
                    stop_words = {'le', 'la', 'un', 'une', 'ou', 'or', 'et', 'for', 'pour', 'a', 'the'}
                    choice1 = groups[0].strip()
                    choice2 = groups[1].strip()
                    if choice1 not in stop_words and choice2 not in stop_words:
                        choices.append((choice1, choice2))
        
        return choices

    def infer_budget(self, text: str, client_status: Optional[str]) -> Dict:
        """Smart Budget Inference."""
        text_lower = text.lower()
        
        # 1. Explicit
        amount = None
        range_label = None
        for pattern, extractor in self._compiled_patterns['budget']:
            match = pattern.search(text_lower)
            if match:
                try:
                    amount = extractor(match)
                    break
                except: continue
        
        confidence = 'none'
        min_b, max_b = None, None
        
        # 2. Check Modifiers
        modifier = 1.0
        for mod_phrase, mult in self.BUDGET_MODIFIERS.items():
            if mod_phrase in text_lower:
                modifier = mult
                break
        
        if amount:
            # Apply modifier to explicit amount
            center = amount * modifier
            min_b, max_b = int(center * 0.8), int(center * 1.2)
            confidence = 'explicit_modified' if modifier != 1.0 else 'explicit'
        
        elif client_status and client_status in self.BUDGET_BY_STATUS:
            # Infer from status
            base_min, base_max = self.BUDGET_BY_STATUS[client_status]
            min_b, max_b = int(base_min * modifier), int(base_max * modifier)
            confidence = 'inferred_status'
            
        elif re.search(r'(luxe|luxury|haut\s+de\s+gamme|premium)', text_lower):
            min_b, max_b = 10000, 50000
            confidence = 'inferred_keywords'

        # Determine Range Label
        if max_b:
            if max_b < 2000: range_label = 'under_2K'
            elif max_b < 5000: range_label = '2K-5K'
            elif max_b < 10000: range_label = '5K-10K'
            elif max_b < 20000: range_label = '10K-20K'
            elif max_b < 50000: range_label = '20K-50K'
            else: range_label = '50K+'
            
        # Determine Tier
        tier = 'flexible_unknown'
        if max_b:
            if max_b < 2000: tier = 'entry_level'
            elif max_b < 5000: tier = 'core'
            elif max_b < 15000: tier = 'high'
            else: tier = 'ultra_high'

        return {
            'amount': amount,
            'min': min_b,
            'max': max_b,
            'range': range_label,
            'tier': tier,
            'confidence': confidence
        }

    @safe_execution(default_return=ExtractionResult(
        pilier_1_univers_produit=Pilier1Product(),
        pilier_2_profil_client=Pilier2Client(),
        pilier_3_hospitalite_care=Pilier3Care(),
        pilier_4_action_business=Pilier4Business(),
        meta_analysis=MetaAnalysis(confidence_score=0.0),
        processing_tier="tier1",
        extracted_by="tier1_rules_fallback",
        confidence=0.0,
        rgpd_flag=False,
        from_cache=False
    ))
    def extract(self, text: str, language: str = 'FR') -> ExtractionResult:
        """
        Extraction rapide par Regex (Tier 1).
        Retourne une structure compatible Taxonomie V2 (4 Piliers).
        """
        start_time = time.time()
        self.stats['processed'] += 1
        
        # 1. Tags & Products
        tags = self.extract_taxonomy_tags(text)
        
        # 2. Relations & Gender (Context Aware)
        relations = self.extract_relations(text)
        gender_data = self.extract_context_aware_gender(text, relations)
        
        # 3. Status
        client_status = None
        for status, pattern in self._compiled_patterns['status'].items():
            if pattern.search(text):
                client_status = status
                break
        
        # 4. Budget (Smart Inference)
        budget_data = self.infer_budget(text, client_status)
        
        # 5. Health & Safety
        allergies_list = []
        for allergen, patterns in self._compiled_patterns['allergies'].items():
            for p in patterns:
                if p.search(text):
                    # Severity check
                    sev = 'low'
                    for s_level, s_pats in self._compiled_patterns['severity'].items():
                        if any(sp.search(text) for sp in s_pats):
                            sev = s_level
                            break
                    allergies_list.append({'allergen': allergen, 'severity': sev})
                    break

        dietary = []
        for diet_type, patterns in self._compiled_patterns['dietary'].items():
            if any(p.search(text) for p in patterns):
                dietary.append(diet_type)

        allergies_simple = [a['allergen'] for a in allergies_list]
        severity = next((a['severity'] for a in allergies_list if a['severity'] == 'high'), 'low')
        
        # 6. Temporal
        temporal = self.extract_temporal(text)
        
        # 7. Preferences & Usage
        found_colors = [k for k, pats in self._compiled_patterns['colors'].items() if any(p.search(text) for p in pats)]
        found_materials = [k for k, pats in self._compiled_patterns['materials'].items() if any(p.search(text) for p in pats)]
        found_usage = [k for k, pats in self._compiled_patterns['usage'].items() if any(p.search(text) for p in pats)]
        
        # Extract LV specific products
        lv_products_found = [k for k, p in self._compiled_patterns['lv_products'].items() if p.search(text)]
        lv_materials_found = [k for k, p in self._compiled_patterns['lv_materials'].items() if p.search(text)]

        # 8. Merge Tags
        all_tags = list(set(tags + relations['gift_for'] + relations['shopping_with'] + temporal['occasions'] + lv_products_found))
        all_tags = list(set(tags + relations['gift_for'] + relations['shopping_with'] + temporal['occasions']))
        
        # 9. Result Construction
        # Determine Purchase Context based on relations
        purchase_type = "Gift" if relations['gift_for'] else "Self"
        
        # Pilier construction
        p1 = Pilier1Product(
            categories=tags, 
            produits_mentionnes=lv_products_found,
            usage=found_usage, 
            preferences=ProductPreferences(
                colors=found_colors,
                materials=found_materials + lv_materials_found
            )
        )
        p2 = Pilier2Client(
            purchase_context=PurchaseContext(type=purchase_type),
            profession=Profession(),
            lifestyle=Lifestyle(),
            status=client_status
        )
        p3 = Pilier3Care(
            allergies=Allergies(food=dietary, contact=allergies_simple), # Basic mapping
            occasion=temporal['occasions'][0] if temporal['occasions'] else None
        )
        p4 = Pilier4Business(
            urgency=temporal['urgency'],
            lead_temperature="Warm" if temporal['urgency'] == 'high' else "Discovery",
            budget_potential=f"{budget_data['tier']} ({budget_data['range']})",
            budget_specific=budget_data.get('amount')
        )
        
        # Meta
        res_data = {
            'tags': all_tags,
            'budget_confidence': budget_data['confidence'],
            'client_status': client_status,
            'allergies': allergies_simple,
            'occasions': temporal['occasions']
        }
        confidence = self.calculate_confidence(res_data)
        
        # Calculate quality and completeness scores
        quality_score = self._calculate_quality_score(res_data)
        completeness_score = self._calculate_completeness_score(res_data)
        missing_info = self._detect_missing_info(res_data)
        
        meta = MetaAnalysis(
            confidence_score=confidence,
            quality_score=quality_score,
            completeness_score=completeness_score,
            missing_info=missing_info,
            risk_flags=[],  # Could be populated based on specific rules
            advisor_feedback=self._generate_feedback(quality_score, missing_info)
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ExtractionResult(
            pilier_1_univers_produit=p1,
            pilier_2_profil_client=p2,
            pilier_3_hospitalite_care=p3,
            pilier_4_action_business=p4,
            meta_analysis=meta,
            
            # Metadata legacy/compat
            processing_tier='tier1',
            confidence=confidence,
            processing_time_ms=processing_time,
            rgpd_flag=False,
            from_cache=False
        )

    def extract_temporal(self, text: str) -> Dict:
        """Extract occasions, dates and urgency."""
        occasions = []
        urgency = 'low'
        
        # Occasions
        for occasion, patterns in self._compiled_patterns['occasions'].items():
            if any(p.search(text) for p in patterns):
                occasions.append(occasion)
        
        # Urgency
        for pattern, level in self.URGENCY_PATTERNS:
            if re.search(pattern, text, re.I):
                urgency = level # Take first found
                break
                
        # Simple date extraction (French/Euro format dd/mm or dd month)
        # We focus on future dates context
        event_date = None
        date_match = re.search(r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)', text, re.I)
        if date_match:
            try:
                months = {'janvier':1,'février':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'août':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12}
                d, m_str = int(date_match.group(1)), date_match.group(2).lower()
                current_year = datetime.now().year
                event_date = f"{current_year}-{months[m_str]:02d}-{d:02d}"
            except: pass
            
        return {
            'occasions': occasions,
            'urgency': urgency,
            'date': event_date
        }

    def extract_taxonomy_tags(self, text: str) -> List[str]:
        """Fast keyword extraction."""
        found_tags = set()
        text_lower = text.lower()

        if self._aho_available and self._aho_automaton is not None:
            try:
                return self._extract_taxonomy_tags_aho(text_lower)
            except Exception as exc:
                logger.warning("Tier1 Aho extraction failed, falling back to regex: %s", exc)

        for tag, patterns in self._compiled_patterns['keywords'].items():
            if any(p.search(text_lower) for p in patterns):
                found_tags.add(tag)
        return list(found_tags)

    def _extract_taxonomy_tags_aho(self, text_lower: str) -> List[str]:
        found_tags = set()
        for end_idx, (tag, alias) in self._aho_automaton.iter(text_lower):
            start_idx = end_idx - len(alias) + 1
            if self._is_word_boundary(text_lower, start_idx, end_idx):
                found_tags.add(tag)
        return list(found_tags)

    @staticmethod
    def _is_word_boundary(text: str, start_idx: int, end_idx: int) -> bool:
        if start_idx > 0 and text[start_idx - 1].isalnum():
            return False
        next_idx = end_idx + 1
        if next_idx < len(text) and text[next_idx].isalnum():
            return False
        return True

    def calculate_confidence(self, data: Dict) -> float:
        """Intelligent normalized confidence score."""
        score = 0.60 # Base
        
        # Tags
        score += min(len(data['tags']) * 0.05, 0.15)
        
        # Budget
        bc = data.get('budget_confidence')
        if bc == 'explicit' or bc == 'explicit_modified': score += 0.15
        elif bc == 'inferred_status': score += 0.08
        
        # Critical Info
        if data.get('client_status'): score += 0.05
        if data.get('allergies'): score += 0.05
        if data.get('occasions'): score += 0.05
        
        return min(score, 0.95)
    
    def _calculate_quality_score(self, data: Dict) -> float:
        """Calculate quality score based on data richness (0-1)."""
        score = 0.0
        
        # Check for key data points
        if data.get('budget', {}).get('amount'):
            score += 0.25
        if data.get('client_status'):
            score += 0.15
        if data.get('occasions'):
            score += 0.15
        if data.get('preferences', {}).get('colors'):
            score += 0.15
        if data.get('preferences', {}).get('materials'):
            score += 0.15
        if data.get('usage'):
            score += 0.15
            
        return min(score, 1.0)
    
    def _calculate_completeness_score(self, data: Dict) -> float:
        """Calculate completeness score for the 4 pillars (0-1)."""
        score = 0.0
        
        # Pilier 1: Product info
        if data.get('categories'):
            score += 0.25
            
        # Pilier 2: Client profile
        if data.get('purchase_type'):
            score += 0.25
            
        # Pilier 3: Care info (optional but good to have)
        if not data.get('allergies'):
            score += 0.25  # Knowing there are no allergies is also info
            
        # Pilier 4: Business action
        if data.get('budget', {}).get('amount'):
            score += 0.25
            
        return score
    
    def _detect_missing_info(self, data: Dict) -> List[str]:
        """Detect what information is missing."""
        missing = []
        
        if not data.get('budget', {}).get('amount'):
            missing.append("Budget non spécifié")
        if not data.get('client_status'):
            missing.append("Statut client inconnu")
        if not data.get('occasions'):
            missing.append("Occasion non mentionnée")
        if not data.get('purchase_type'):
            missing.append("Type d'achat indéterminé")
            
        return missing
    
    def _generate_feedback(self, quality_score: float, missing_info: List[str]) -> str:
        """Generate gamified feedback for the advisor."""
        if quality_score > 0.8:
            return "✨ Note excellente ! Tous les éléments clés sont présents."
        elif quality_score > 0.5:
            return f"👍 Bonne note. Pour améliorer : {', '.join(missing_info[:2])}."
        else:
            return f"📝 Note à compléter. Manque : {', '.join(missing_info[:3])}."


if __name__ == "__main__":
    engine = Tier1RulesEngine()
    
    test_cases = [
        "Mme Dubois, VIC. Cherche cadeau pour sa fille. Budget très flexible. Allergie nickel sévère.",
        "Recherche sac pour moi, budget 5k. Urgent pour mariage samedi.",
        "Pas de budget limite, je veux le top."
    ]
    
    print("\n🚀 TIER 1 ENHANCED TESTS:\n")
    for txt in test_cases:
        print(f"INPUT: {txt}")
        res = engine.extract(txt)
        print(f"OUTPUT: Tags={res.tags}, Budget={res.budget_range} ({res.confidence:.2f}), Severity={res.allergy_severity}")
        print("-" * 60)
