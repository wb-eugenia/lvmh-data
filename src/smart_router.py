"""
Smart Router for Multi-Tier Pipeline.
Routes notes to Tier 1 (Rules), Tier 2 (NLP), or Tier 3 (LLM) based on complexity.
"""

import re
from typing import Dict, Literal, List, Tuple
from dataclasses import dataclass


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    tier: Literal[1, 2, 3]
    reasons: List[str]
    confidence: float
    priority: str  # 'low', 'medium', 'high'


class SmartRouter:
    """Routes notes to appropriate processing tier."""
    
    # Token thresholds
    TIER1_MAX_TOKENS = 200
    TIER2_MAX_TOKENS = 400
    
    # RGPD keywords that force Tier 3 (contextual analysis needed)
    RGPD_CRITICAL_KEYWORDS = {
        'FR': [
            'burnout', 'dépression', 'anxiété', 'suicide', 'psychiatre', 'psychologue',
            'divorce contentieux', 'garde des enfants', 'pension alimentaire',
            'cancer', 'chimiothérapie', 'maladie grave', 'handicap', 'invalidité',
            'religion', 'musulman', 'juif', 'chrétien', 'athée', 'pratiquant',
            'politique', 'gauche', 'droite', 'militant', 'parti',
            'homosexuel', 'gay', 'lesbienne', 'trans', 'orientation sexuelle'
        ],
        'EN': [
            'burnout', 'depression', 'anxiety', 'suicide', 'psychiatrist', 'psychologist',
            'custody battle', 'child custody', 'alimony', 'contentious divorce',
            'cancer', 'chemotherapy', 'serious illness', 'disability', 'handicap',
            'religion', 'muslim', 'jewish', 'christian', 'atheist', 'practicing',
            'political', 'left', 'right', 'activist', 'party',
            'homosexual', 'gay', 'lesbian', 'trans', 'sexual orientation'
        ],
        'IT': [
            'burnout', 'depressione', 'ansia', 'suicidio', 'psichiatra', 'psicologo',
            'divorzio contenzioso', 'affidamento', 'alimenti',
            'cancro', 'chemioterapia', 'malattia grave', 'disabilità', 'handicap',
            'religione', 'musulmano', 'ebreo', 'cristiano', 'ateo', 'praticante',
            'politica', 'sinistra', 'destra', 'militante', 'partito',
            'omosessuale', 'gay', 'lesbica', 'trans', 'orientamento sessuale'
        ],
        'ES': [
            'burnout', 'depresión', 'ansiedad', 'suicidio', 'psiquiatra', 'psicólogo',
            'divorcio contencioso', 'custodia', 'pensión alimenticia',
            'cáncer', 'quimioterapia', 'enfermedad grave', 'discapacidad', 'minusvalía',
            'religión', 'musulmán', 'judío', 'cristiano', 'ateo', 'practicante',
            'política', 'izquierda', 'derecha', 'militante', 'partido',
            'homosexual', 'gay', 'lesbiana', 'trans', 'orientación sexual'
        ],
        'DE': [
            'burnout', 'depression', 'angst', 'selbstmord', 'psychiater', 'psychologe',
            'sorgerecht', 'unterhalt', 'scheidung',
            'krebs', 'chemotherapie', 'schwere krankheit', 'behinderung', 'handicap',
            'religion', 'muslim', 'jüdisch', 'christlich', 'atheist', 'praktizierend',
            'politik', 'links', 'rechts', 'aktivist', 'partei',
            'homosexuell', 'schwul', 'lesbisch', 'trans', 'sexuelle orientierung'
        ]
    }
    
    # VIP/VIC indicators that force Tier 3
    VIP_INDICATORS = [
        r'\bVIC\b', r'\bVIP\b', r'\btier\s*one\b', r'\btier\s*1\b',
        r'\bclient\s+prioritaire\b', r'\bclient\s+VIP\b', r'\btrès\s+bon\s+client\b',
        r'\bhaut\s+potentiel\b', r'\bhigh\s+potential\b', r'\bultimate\b',
        r'\bplatinum\b', r'\bprivate\s+client\b'
    ]
    
    # Allergy patterns that need severity analysis (Tier 3) - ONLY severe cases
    ALLERGY_PATTERNS = [
        r'allerg(ie|y)\s+(sévère|severe|grave|mortelle|fatal|life.?threatening)',
        r'anaphylax',
        r'épipen|epipen',
        r'choc\s+allergique',
        r'allergic\s+shock'
    ]
    
    # Complex relationship indicators (Tier 3)
    RELATIONSHIP_PATTERNS = [
        r'(venu|venue|came|venuto|venuta|vino).*(avec|with|con|mit)',
        r'cadeau.*(pour|for|per|für).*(mari|femme|fils|fille|mère|père|spouse|husband|wife|son|daughter)',
        r'gift.*(for|to)',
        r'regalo.*(per|a)',
        r'geschenk.*(für|an)'
    ]
    
    # Budget patterns for Tier 1
    BUDGET_PATTERNS = [
        r'budget\s*:?\s*(\d+)\s*[kK€$]?',
        r'(\d+)\s*[kK]\s*(euro|€|\$|budget)',
        r'(\d+)\s*000\s*(euro|€|\$)',
        r'entre\s*(\d+)\s*et\s*(\d+)',
        r'between\s*(\d+)\s*and\s*(\d+)'
    ]
    
    def __init__(self):
        self.stats = {'tier1': 0, 'tier2': 0, 'tier3': 0}
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (~4 chars per token)."""
        return len(text) // 4
    
    def detect_rgpd_keywords(self, text: str, language: str) -> List[str]:
        """Detect RGPD-critical keywords in text."""
        text_lower = text.lower()
        keywords = self.RGPD_CRITICAL_KEYWORDS.get(language, self.RGPD_CRITICAL_KEYWORDS['EN'])
        found = [kw for kw in keywords if kw.lower() in text_lower]
        return found
    
    def detect_vip(self, text: str) -> bool:
        """Detect VIP/VIC client indicators."""
        for pattern in self.VIP_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def detect_allergy_complexity(self, text: str) -> bool:
        """Detect if allergy needs severity analysis."""
        text_lower = text.lower()
        for pattern in self.ALLERGY_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def detect_relationship_complexity(self, text: str) -> bool:
        """Detect complex relationship dynamics."""
        for pattern in self.RELATIONSHIP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def is_simple_pattern(self, text: str) -> bool:
        """Check if note follows simple extractable pattern."""
        # Has clear budget mention
        has_budget = any(re.search(p, text, re.IGNORECASE) for p in self.BUDGET_PATTERNS)
        # Short enough
        is_short = self.estimate_tokens(text) < 150
        # No complex indicators
        no_allergy = not self.detect_allergy_complexity(text)
        no_relationship = not self.detect_relationship_complexity(text)
        
        return has_budget and is_short and no_allergy and no_relationship
    
    def route(self, text: str, language: str, metadata: Dict = None) -> RoutingDecision:
        """
        Route note to appropriate tier.
        
        Returns:
            RoutingDecision with tier, reasons, and confidence
        """
        reasons = []
        tokens = self.estimate_tokens(text)
        metadata = metadata or {}
        
        # === TIER 3 TRIGGERS (highest priority) ===
        
        # 1. RGPD critical keywords
        rgpd_keywords = self.detect_rgpd_keywords(text, language)
        if rgpd_keywords:
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=[f"RGPD keywords detected: {rgpd_keywords[:3]}"],
                confidence=0.95,
                priority='high'
            )
        
        # 2. VIP/VIC client
        if self.detect_vip(text) or metadata.get('is_vip'):
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=["VIP/VIC client - premium processing"],
                confidence=0.90,
                priority='high'
            )
        
        # 3. Complex allergies needing severity
        if self.detect_allergy_complexity(text):
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=["Allergy detected - needs severity analysis"],
                confidence=0.88,
                priority='medium'
            )
        
        # 4. Very long notes
        if tokens > self.TIER2_MAX_TOKENS:
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=[f"Long note ({tokens} tokens) - needs full LLM"],
                confidence=0.85,
                priority='medium'
            )
        
        # 5. Complex relationships
        if self.detect_relationship_complexity(text):
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=["Complex relationship dynamics detected"],
                confidence=0.82,
                priority='medium'
            )
        
        # === TIER 1 TRIGGERS (simplest cases) ===
        
        # Short + simple pattern
        if tokens <= self.TIER1_MAX_TOKENS and self.is_simple_pattern(text):
            self.stats['tier1'] += 1
            return RoutingDecision(
                tier=1,
                reasons=[f"Simple pattern, short note ({tokens} tokens)"],
                confidence=0.80,
                priority='low'
            )
        
        # Very short notes
        if tokens < 100:
            self.stats['tier1'] += 1
            return RoutingDecision(
                tier=1,
                reasons=[f"Very short note ({tokens} tokens)"],
                confidence=0.75,
                priority='low'
            )
        
        # === TIER 2 (default for medium complexity) ===
        
        self.stats['tier2'] += 1
        return RoutingDecision(
            tier=2,
            reasons=[f"Medium complexity ({tokens} tokens), NLP suitable"],
            confidence=0.78,
            priority='medium'
        )
    
    def route_batch(self, notes: List[Dict]) -> Dict[int, List[Dict]]:
        """Route a batch of notes, return grouped by tier."""
        grouped = {1: [], 2: [], 3: []}
        
        for note in notes:
            text = note.get('Transcription', '')
            language = note.get('Language', 'FR')
            decision = self.route(text, language, note)
            
            note['_routing'] = {
                'tier': decision.tier,
                'reasons': decision.reasons,
                'confidence': decision.confidence,
                'priority': decision.priority
            }
            grouped[decision.tier].append(note)
        
        return grouped
    
    def get_stats(self) -> Dict:
        """Get routing statistics."""
        total = sum(self.stats.values())
        if total == 0:
            return {'tier1': 0, 'tier2': 0, 'tier3': 0, 'total': 0}
        
        return {
            'tier1': self.stats['tier1'],
            'tier2': self.stats['tier2'],
            'tier3': self.stats['tier3'],
            'total': total,
            'tier1_pct': self.stats['tier1'] / total * 100,
            'tier2_pct': self.stats['tier2'] / total * 100,
            'tier3_pct': self.stats['tier3'] / total * 100
        }
    
    def report(self) -> str:
        """Generate routing report."""
        stats = self.get_stats()
        return f"""
📊 ROUTING STATISTICS
{'='*40}
Tier 1 (Rules):  {stats['tier1']:>5} ({stats.get('tier1_pct', 0):.1f}%)
Tier 2 (NLP):    {stats['tier2']:>5} ({stats.get('tier2_pct', 0):.1f}%)
Tier 3 (LLM):    {stats['tier3']:>5} ({stats.get('tier3_pct', 0):.1f}%)
{'='*40}
TOTAL:           {stats['total']:>5}

💰 Cost Estimate (vs all-LLM):
Tier 1 savings: {stats['tier1'] * 0.0001:.2f}€
Tier 2 savings: {stats['tier2'] * 0.0001:.2f}€
Total saved:    {(stats['tier1'] + stats['tier2']) * 0.0001:.2f}€
"""


if __name__ == "__main__":
    import pandas as pd
    
    # Test on Wave 2 cleaned data
    df = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
    
    router = SmartRouter()
    
    print("🔀 Testing Smart Router on 300 notes...\n")
    
    grouped = router.route_batch(df.to_dict('records'))
    
    print(f"Tier 1 (Rules): {len(grouped[1])} notes")
    print(f"Tier 2 (NLP):   {len(grouped[2])} notes")
    print(f"Tier 3 (LLM):   {len(grouped[3])} notes")
    
    print(router.report())
    
    # Show examples per tier
    print("\n📝 EXAMPLES PER TIER:")
    for tier in [1, 2, 3]:
        if grouped[tier]:
            note = grouped[tier][0]
            print(f"\n--- TIER {tier} Example ---")
            print(f"ID: {note['ID']}")
            print(f"Routing: {note['_routing']}")
            print(f"Text: {note['Transcription'][:150]}...")
