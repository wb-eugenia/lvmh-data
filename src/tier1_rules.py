"""
Tier 1: Rules-based Tag Extraction.
Deterministic extraction using regex patterns and dictionary lookups.
Cost: 0€ | Speed: ~0.5s/note | Precision: 75-80%
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Tier1Result:
    """Result from Tier 1 rules extraction."""
    tags: List[str]
    budget_range: Optional[str]
    client_status: Optional[str]
    confidence: float
    extracted_by: str = "tier1_rules"


class Tier1RulesEngine:
    """Deterministic rules-based tag extraction."""
    
    # === BUDGET PATTERNS ===
    BUDGET_PATTERNS = [
        # French
        (r'budget\s*:?\s*(\d+)\s*k', lambda m: int(m.group(1)) * 1000),
        (r'budget\s*:?\s*(\d+)\s*€', lambda m: int(m.group(1))),
        (r'budget\s*:?\s*(\d+)\s*000', lambda m: int(m.group(1)) * 1000),
        (r'(\d+)\s*k\s*€?(?:\s*budget)?', lambda m: int(m.group(1)) * 1000),
        (r'entre\s*(\d+)\s*et\s*(\d+)\s*k', lambda m: (int(m.group(1)) + int(m.group(2))) * 500),
        # English
        (r'budget\s*:?\s*\$?(\d+)k', lambda m: int(m.group(1)) * 1000),
        (r'between\s*(\d+)\s*and\s*(\d+)k', lambda m: (int(m.group(1)) + int(m.group(2))) * 500),
        # Flexible/open
        (r'budget\s+(très\s+)?flexible', lambda m: 20000),
        (r'budget\s+(très\s+)?ouvert', lambda m: 25000),
        (r'budget\s+open', lambda m: 20000),
    ]
    
    # === PRODUCT KEYWORDS → TAGS ===
    PRODUCT_TAGS = {
        # French
        'sac': 'leather_goods',
        'pochette': 'small_leather',
        'portefeuille': 'small_leather',
        'ceinture': 'belts',
        'valise': 'travel_luggage',
        'bagage': 'travel_luggage',
        'maroquinerie': 'leather_goods',
        'cuir': 'leather_preference',
        'capucines': 'capucines',
        'alma': 'alma',
        'neverfull': 'neverfull',
        'speedy': 'speedy',
        'keepall': 'keepall',
        # English
        'bag': 'leather_goods',
        'wallet': 'small_leather',
        'belt': 'belts',
        'luggage': 'travel_luggage',
        'leather': 'leather_preference',
    }
    
    # === OCCASION KEYWORDS → TAGS ===
    OCCASION_TAGS = {
        'anniversaire': 'birthday_gift',
        'birthday': 'birthday_gift',
        'compleanno': 'birthday_gift',
        'mariage': 'wedding_gift',
        'wedding': 'wedding_gift',
        'matrimonio': 'wedding_gift',
        'noël': 'christmas_gift',
        'christmas': 'christmas_gift',
        'natale': 'christmas_gift',
        'saint-valentin': 'valentines_gift',
        'valentine': 'valentines_gift',
        'fête des mères': 'mothers_day',
        'fête des pères': 'fathers_day',
        'graduation': 'graduation_gift',
        'diplôme': 'graduation_gift',
        'retirement': 'retirement_gift',
        'retraite': 'retirement_gift',
    }
    
    # === CLIENT STATUS PATTERNS ===
    STATUS_PATTERNS = {
        'vic': ('vic', r'\bVIC\b'),
        'vip': ('vip', r'\bVIP\b'),
        'first_visit': ('first_visit', r'(première\s+visite|first\s+(time|visit)|prima\s+visita|neue\s+kunde)'),
        'regular': ('regular', r'(client\s+régulier|regular\s+client|cliente\s+abituale|stammkunde)'),
        'occasional': ('occasional', r'(client\s+occasionnel|occasional|occasionale)'),
    }
    
    # === DIETARY TAGS ===
    DIETARY_PATTERNS = {
        'vegan': r'\bvegan(e|o|a)?\b',
        'vegetarian': r'\bvégétarien|vegetarian|vegetariano|vegetarisch\b',
        'pescatarian': r'\bpescetarien|pescatarian|pescetariano\b',
        'gluten_free': r'\bsans\s+gluten|gluten.?free|senza\s+glutine\b',
    }
    
    # === ALLERGY TAGS (simple detection, not severity) ===
    ALLERGY_PATTERNS = {
        'nickel_allergy': r'allerg(ie|y).*nickel|nickel.*allerg',
        'latex_allergy': r'allerg(ie|y).*latex|latex.*allerg',
        'nut_allergy': r'allerg(ie|y).*(noix|arachide|nut|peanut)',
        'gluten_intolerance': r'(intol[ée]ran|allerg).*(gluten|coeliaque|celiac)',
        'lactose_intolerance': r'(intol[ée]ran|allerg).*lacto',
        'shellfish_allergy': r'allerg.*(fruits?\s+de\s+mer|shellfish|crustac[ée]|crostacei)',
        'pollen_allergy': r'allerg.*pollen',
        'sulfite_allergy': r'allerg.*(sulfite|sulphite)',
    }
    
    # === PROFESSION PATTERNS (top 20) ===
    PROFESSION_TAGS = {
        'medical_professional': r'\b(médecin|doctor|docteur|chirurgien|surgeon|cardiologue|neurologue|dermatologue)\b',
        'legal_professional': r'\b(avocat|avocate|lawyer|attorney|notaire|juge|judge)\b',
        'finance_professional': r'\b(banquier|banker|trader|investisseur|investor|CFO|comptable)\b',
        'entrepreneur': r'\b(entrepreneur|fondateur|founder|CEO|PDG|startup)\b',
        'creative_professional': r'\b(designer|architecte|architect|artiste|artist|photographe)\b',
        'tech_professional': r'\b(développeur|developer|ingénieur|engineer|data\s+scientist)\b',
        'media_professional': r'\b(journaliste|journalist|producteur|producer|réalisateur|director)\b',
        'academic': r'\b(professeur|professor|chercheur|researcher|universitaire)\b',
    }
    
    # === LIFESTYLE TAGS ===
    LIFESTYLE_PATTERNS = {
        'art_collector': r'\b(collectionn|collect).*(art|tableau|sculpture|peinture)\b',
        'wine_enthusiast': r'\b(amateur|passionn|collect).*(vin|wine|vino)\b',
        'travel_frequent': r'\b(voyage|travel|viaja).*(fréquent|constant|frequent|constante)\b',
        'sports_active': r'\b(pratique|plays|practice).*(sport|tennis|golf|ski|yoga|running)\b',
        'music_lover': r'\b(passionn|amateur|loves).*(musique|music|opéra|opera|concert)\b',
    }
    
    def __init__(self):
        self.stats = {'processed': 0, 'tags_extracted': 0}
    
    def extract_budget(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """Extract budget amount and range."""
        text_lower = text.lower()
        
        for pattern, extractor in self.BUDGET_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    amount = extractor(match)
                    # Classify into ranges
                    if amount < 3000:
                        return amount, 'under_3K'
                    elif amount < 5000:
                        return amount, '3K-5K'
                    elif amount < 10000:
                        return amount, '5K-10K'
                    elif amount < 20000:
                        return amount, '10K-20K'
                    else:
                        return amount, '20K+'
                except:
                    continue
        
        return None, None
    
    def extract_client_status(self, text: str) -> Optional[str]:
        """Extract client status."""
        for status, (tag, pattern) in self.STATUS_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return tag
        return None
    
    def extract_tags_from_patterns(self, text: str, patterns: Dict[str, str]) -> List[str]:
        """Generic pattern matcher for tag extraction."""
        tags = []
        text_lower = text.lower()
        for tag, pattern in patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                tags.append(tag)
        return tags
    
    def extract_product_tags(self, text: str) -> List[str]:
        """Extract product-related tags."""
        tags = []
        text_lower = text.lower()
        for keyword, tag in self.PRODUCT_TAGS.items():
            if keyword in text_lower:
                tags.append(tag)
        return list(set(tags))
    
    def extract_occasion_tags(self, text: str) -> List[str]:
        """Extract occasion-related tags."""
        tags = []
        text_lower = text.lower()
        for keyword, tag in self.OCCASION_TAGS.items():
            if keyword in text_lower:
                tags.append(tag)
        return list(set(tags))
    
    def extract(self, text: str, language: str = 'FR') -> Tier1Result:
        """
        Full Tier 1 extraction.
        
        Returns:
            Tier1Result with extracted tags and metadata
        """
        self.stats['processed'] += 1
        
        all_tags = []
        
        # 1. Products
        all_tags.extend(self.extract_product_tags(text))
        
        # 2. Occasions
        all_tags.extend(self.extract_occasion_tags(text))
        
        # 3. Dietary
        all_tags.extend(self.extract_tags_from_patterns(text, self.DIETARY_PATTERNS))
        
        # 4. Allergies
        all_tags.extend(self.extract_tags_from_patterns(text, self.ALLERGY_PATTERNS))
        
        # 5. Professions
        all_tags.extend(self.extract_tags_from_patterns(text, self.PROFESSION_TAGS))
        
        # 6. Lifestyle
        all_tags.extend(self.extract_tags_from_patterns(text, self.LIFESTYLE_PATTERNS))
        
        # Dedupe
        all_tags = list(set(all_tags))
        
        # Budget
        _, budget_range = self.extract_budget(text)
        
        # Client status
        client_status = self.extract_client_status(text)
        
        # Confidence based on number of tags found
        if len(all_tags) >= 5:
            confidence = 0.85
        elif len(all_tags) >= 3:
            confidence = 0.75
        elif len(all_tags) >= 1:
            confidence = 0.65
        else:
            confidence = 0.50
        
        self.stats['tags_extracted'] += len(all_tags)
        
        return Tier1Result(
            tags=all_tags,
            budget_range=budget_range,
            client_status=client_status,
            confidence=confidence
        )
    
    def report(self) -> str:
        """Generate extraction report."""
        avg_tags = self.stats['tags_extracted'] / max(self.stats['processed'], 1)
        return f"""
🏷️ TIER 1 EXTRACTION STATS
{'='*40}
Notes processed: {self.stats['processed']}
Total tags:      {self.stats['tags_extracted']}
Avg tags/note:   {avg_tags:.1f}
"""


if __name__ == "__main__":
    import pandas as pd
    
    # Test on sample
    engine = Tier1RulesEngine()
    
    test_texts = [
        "Mme Martin, 45 ans, avocate, cherche sac cuir noir. Budget 5K. Végétarienne.",
        "Client VIC, anniversaire mariage, Capucines, budget flexible.",
        "Dr. Smith, cardiologue, voyage fréquent, allergie nickel.",
    ]
    
    print("🏷️ Testing Tier 1 Rules Engine\n")
    
    for text in test_texts:
        result = engine.extract(text)
        print(f"Text: {text[:50]}...")
        print(f"Tags: {result.tags}")
        print(f"Budget: {result.budget_range}")
        print(f"Confidence: {result.confidence:.0%}")
        print()
    
    # Test on real data
    df = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
    
    print(f"\n📊 Testing on {len(df)} notes...\n")
    
    for _, row in df.head(10).iterrows():
        result = engine.extract(row['Transcription'], row['Language'])
        print(f"{row['ID']}: {len(result.tags)} tags - {result.tags[:5]}")
    
    print(engine.report())
