"""
Tier 1: Rules-based Tag Extraction (Enhanced Version).
Deterministic extraction using regex patterns and dictionary lookups.
Cost: 0€ | Speed: ~0.5s/note | Precision: 80-85%
"""

import re
import time
from typing import Dict, List, Optional, Tuple, Any
from src.models import ExtractionResult
from src.resilience import safe_execution
from src.taxonomy import TaxonomyManager


class Tier1RulesEngine:
    """Enhanced deterministic rules-based tag extraction using TaxonomyManager."""
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: BUDGET EXTRACTION (Kept as logic, not taxonomy)
    # ═══════════════════════════════════════════════════════════════════
    
    BUDGET_PATTERNS = [
        # French - explicit budget
        (r'budget\s*(?:de|:)?\s*(\d{1,3})[\s,]?(\d{3})?\s*(?:€|euros?)?', 
         lambda m: int(m.group(1)) * 1000 + int(m.group(2) or 0)),
        (r'budget\s*(?:de|:)?\s*(\d+)\s*[kK]', lambda m: int(m.group(1)) * 1000),
        (r'(\d+)\s*[kK]\s*(?:€|euros?)?\s*(?:de\s+)?budget', lambda m: int(m.group(1)) * 1000),
        (r'entre\s*(\d+)\s*(?:et|à)\s*(\d+)\s*[kK]', 
         lambda m: (int(m.group(1)) + int(m.group(2))) * 500),
        (r'(\d{4,5})\s*(?:€|euros?)', lambda m: int(m.group(1))),
        
        # English
        (r'budget\s*(?:of|:)?\s*\$?(\d+)[kK]', lambda m: int(m.group(1)) * 1000),
        (r'between\s*\$?(\d+)[kK]?\s*and\s*\$?(\d+)[kK]', 
         lambda m: (int(m.group(1)) + int(m.group(2))) * 1000 // 2),
        (r'\$(\d{4,5})', lambda m: int(m.group(1))),
        
        # Qualitative
        (r'budget\s+(?:très\s+)?flexible', lambda m: 15000),
        (r'budget\s+(?:très\s+)?ouvert', lambda m: 20000),
        (r'sans\s+limite', lambda m: 50000),
        (r'no\s+budget\s+limit', lambda m: 50000),
    ]
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4: CLIENT STATUS (Kept as logic)
    # ═══════════════════════════════════════════════════════════════════
    
    STATUS_PATTERNS = {
        'vic': (r'\bVIC\b', 'vic'),
        'vip': (r'\bVIP\b', 'vip'),
        'ultimate': (r'\bultimate\b', 'ultimate'),
        'platinum': (r'\bplatinum\b', 'platinum'),
        'first_visit': (r'(première\s+visite|first\s+(?:time|visit))', 'first_visit'),
        'regular': (r'(client\s+régulier|regular\s+client)', 'regular'),
        'occasional': (r'(client\s+occasionnel|occasional)', 'occasional'),
    }
    
    # ═══════════════════════════════════════════════════════════════════
    # SECTION 9: AGE & GENDER
    # ═══════════════════════════════════════════════════════════════════
    
    AGE_PATTERNS = [
        (r'(\d{2})\s*ans', lambda m: int(m.group(1))),
        (r'(\d{2})\s*(?:years?\s+old|yo|y\.o\.)', lambda m: int(m.group(1))),
        (r'âgé\w?\s+de\s+(\d{2})', lambda m: int(m.group(1))),
    ]
    
    GENDER_PATTERNS = {
        'female': r'\b(Mme|Madame|Mrs|Ms|Dame|femme|cliente|elle|she)\b',
        'male': r'\b(M\.|Mr|Monsieur|Sir|homme|client|il|he)\b',
    }
    
    # ═══════════════════════════════════════════════════════════════════
    # METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def __init__(self):
        self.stats = {'processed': 0, 'tags_extracted': 0}
        self.taxonomy = TaxonomyManager()
        
        # Load keyword map from taxonomy
        self.keyword_map = self.taxonomy.get_all_keywords_map()
    
    def extract_budget(self, text: str) -> Tuple[Optional[int], Optional[str]]:
        """Extract budget amount and range."""
        text_lower = text.lower()
        
        for pattern, extractor in self.BUDGET_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    amount = extractor(match)
                    if amount < 2000: return amount, 'under_2K'
                    elif amount < 5000: return amount, '2K-5K'
                    elif amount < 10000: return amount, '5K-10K'
                    elif amount < 20000: return amount, '10K-20K'
                    elif amount < 50000: return amount, '20K-50K'
                    else: return amount, '50K+'
                except:
                    continue
        return None, None
    
    def extract_age(self, text: str) -> Optional[int]:
        """Extract age from text."""
        for pattern, extractor in self.AGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    age = extractor(match)
                    if 18 <= age <= 99: return age
                except: continue
        return None
    
    def extract_gender(self, text: str) -> Optional[str]:
        """Extract gender from text."""
        for gender, pattern in self.GENDER_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return gender
        return None
    
    def extract_client_status(self, text: str) -> Optional[str]:
        """Extract client status."""
        for status, (pattern, tag) in self.STATUS_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return tag
        return None
    
    def extract_tags_from_taxonomy(self, text: str) -> List[str]:
        """Extract tags using taxonomy keywords."""
        tags = []
        text_lower = text.lower()
        negative_context = r'(pas\s+de|sans|no|not)\s+'
        
        for keyword, tag in self.keyword_map.items():
            # Check if keyword exists
            if len(keyword) <= 3:
                pattern = rf'\b{re.escape(keyword)}\b'
            else:
                pattern = re.escape(keyword)
            
            for match in re.finditer(pattern, text_lower):
                start = match.start()
                preceding = text_lower[max(0, start-10):start]
                if not re.search(negative_context, preceding):
                    tags.append(tag)
                    
        return list(set(tags))

    @safe_execution(default_return=ExtractionResult(
        tags=[], processing_tier="tier1", confidence=0.0, extracted_by="tier1_rules"
    ))
    def extract(self, text: str, language: str = 'FR') -> ExtractionResult:
        """Full Tier 1 extraction returning standardized ExtractionResult."""
        start_time = time.time()
        self.stats['processed'] += 1
        
        all_tags = []
        
        # 1. Taxonomy Tags (Products, Occasions, etc.)
        all_tags.extend(self.extract_tags_from_taxonomy(text))
        
        # 2. Budget
        budget_amount, budget_range = self.extract_budget(text)
        
        # 3. Client Status
        client_status = self.extract_client_status(text)
        
        # 4. Age/Gender
        age = self.extract_age(text)
        gender = self.extract_gender(text)
        
        # Calculate confidence
        confidence = 0.6
        if all_tags: confidence += 0.1
        if budget_range: confidence += 0.1
        
        processing_time = (time.time() - start_time) * 1000
        
        return ExtractionResult(
            tags=all_tags,
            budget_range=budget_range,
            budget_amount=budget_amount,
            client_status=client_status,
            age=age,
            gender=gender,
            processing_tier="tier1",
            confidence=min(confidence, 0.95),
            processing_time_ms=processing_time,
            extracted_by="tier1_rules",
            cost=0.0
        )

    def report(self) -> str:
        """Generate extraction report."""
        return f"Tier 1 Processed: {self.stats['processed']}"

if __name__ == "__main__":
    engine = Tier1RulesEngine()
    text = "Mme Dubois, 45 ans. Cherche sac Capucines cuir noir. Budget 8K€."
    print(engine.extract(text))
