"""
Competitor Mock for Comparison.
Simulates a basic keyword-based NLP engine (the "Old Way").
"""

import random
import time
from typing import Dict, List

class CompetitorEngine:
    """
    Simulates a legacy keyword-based extraction system.
    High false positives, low context awareness.
    """
    
    KEYWORDS = {
        'sac': 'leather_goods',
        'bag': 'leather_goods',
        'cuir': 'material_leather',
        'noir': 'color_black',
        'rouge': 'color_red',
        'cadeau': 'gift',
        'anniversaire': 'occasion_birthday',
        'femme': 'gender_female',
        'homme': 'gender_male',
        'budget': 'budget_mentioned',
        'allergie': 'allergy_generic', # No severity detection
        'noix': 'allergy_nut',
        'gluten': 'dietary_gluten_free'
    }
    
    def process(self, text: str) -> Dict:
        """Process text using simple keyword matching."""
        start = time.time()
        text_lower = text.lower()
        
        found_tags = []
        for word, tag in self.KEYWORDS.items():
            if word in text_lower:
                found_tags.append(tag)
        
        # Simulate "dumb" RGPD (keyword blocking)
        rgpd_block = False
        rgpd_reason = None
        if 'cancer' in text_lower or 'maladie' in text_lower or 'dépression' in text_lower:
            rgpd_block = True
            rgpd_reason = "Keyword blocked: Health term detected"
        
        # Simulate cost (Cloud API)
        cost = 0.002 # Standard legacy API cost
        
        time.sleep(0.5) # Network latency
        
        return {
            'tags': list(set(found_tags)),
            'confidence': 0.65, # Static low confidence
            'processing_time_ms': int((time.time() - start) * 1000),
            'cost_eur': cost,
            'rgpd_blocked': rgpd_block,
            'rgpd_reason': rgpd_reason,
            'method': 'Legacy Keyword API'
        }

# Singleton
competitor = CompetitorEngine()
