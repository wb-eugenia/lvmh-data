"""
Smart Router V2 for Multi-Tier Pipeline.
Routes notes to Tier 1 (Rules), Tier 2 (Ollama), or Tier 3 (GPT) based on explicit priority logic.
"""

import re
from typing import Dict, Literal, List, Optional
from dataclasses import dataclass


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    tier: Literal[1, 2, 3]
    reasons: List[str]
    confidence: float
    priority: str  # 'low', 'medium', 'high'


class SmartRouterV2:
    """
    Router with explicit decision logic:
    1. RGPD Critical -> Tier 3 (Security)
    2. RGPD Sensitive -> Tier 2 (Local Privacy)
    3. Simple & Short -> Tier 1 (Speed/Free)
    4. Complex -> Tier 3 (Precision)
    5. Default -> Tier 2 (Balance)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.tier1_threshold = self.config.get('tier1_confidence', 0.75)
        self.max_tier1_tokens = 250
        
        self.stats = {'tier1': 0, 'tier2': 0, 'tier3': 0}
        
        # Complexity Patterns
        self.complex_patterns = [
            r'\b(vic|vip|ambassad)\b',  # Critical clients
            r'\b(allergi.*sévère|life.?threatening)\b',  # Severe allergies
            r'\b(\d+k|\d+\s?000)\s*(€|eur|dollars?)\b',  # High budgets
            r'\b(plainte|complaint|litige)\b',  # Complaints
        ]
        
        # Simple Patterns (for Tier 1)
        self.simple_patterns = [
            r'cherche\s+(sac|pochette|ceinture|portefeuille|montre|bijou)',
            r'looking\s+for\s+(bag|wallet|belt|watch|jewelry)',
            r'budget\s*:?\s*\d+\s*[kK€]',
            r'cadeau\s+(pour|anniversaire|noël)',
            r'gift\s+(for|birthday|christmas)',
            r'client\s+(vic|vip|régulier)',
            r'vient\s+pour',
        ]
        
        # RGPD Critical (Force Tier 3)
        self.rgpd_critical = [
            r'\b(cancer|hiv|diabète|dépression|suicide)\b',
            r'\b(divorcé.*récent|veuf|custody)\b',
            r'\b(faillite|liquidation judiciaire)\b'
        ]

    def route(self, text: str, language: str = 'FR', metadata: Dict = None) -> RoutingDecision:
        """
        Make routing decision based on priorities.
        """
        metadata = metadata or {}
        text_lower = text.lower()
        token_count = len(text.split())
        
        # 1. RGPD Critical Check
        # Ideally this comes from RGPD filter result, but we check keywords here too as failsafe
        if self._has_rgpd_critical(text_lower):
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=["RGPD Critical Keywords Detected"],
                confidence=0.95,
                priority='high'
            )
            
        # 2. RGPD Sensitive (Tier 2 can handle with local anonymization)
        # We assume if RGPD filter ran before, we might have a flag.
        # For now, let's assume if it's not critical, Tier 2 is safe for "sensitive" but not "critical".
        
        # 3. Simple & Short -> Tier 1
        if token_count < self.max_tier1_tokens:
            if self._has_simple_patterns(text_lower) and not self._is_complex(text_lower):
                self.stats['tier1'] += 1
                return RoutingDecision(
                    tier=1,
                    reasons=[f"Simple pattern, short text ({token_count} tokens)"],
                    confidence=0.85,
                    priority='low'
                )
        
        # 4. Complex -> Tier 3
        if self._is_complex(text_lower):
            self.stats['tier3'] += 1
            return RoutingDecision(
                tier=3,
                reasons=["Complexity patterns detected (VIC, High Budget, etc.)"],
                confidence=0.90,
                priority='medium'
            )
            
        # 5. Default -> Tier 2
        self.stats['tier2'] += 1
        return RoutingDecision(
            tier=2,
            reasons=["Standard complexity, safe for local LLM"],
            confidence=0.80,
            priority='medium'
        )

    def _has_simple_patterns(self, text: str) -> bool:
        """Check if text matches simple patterns."""
        for pattern in self.simple_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _is_complex(self, text: str) -> bool:
        """Check for complexity indicators."""
        for pattern in self.complex_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _has_rgpd_critical(self, text: str) -> bool:
        """Check for critical RGPD keywords."""
        for pattern in self.rgpd_critical:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def explain_decision(self, text: str, decision: RoutingDecision) -> Dict:
        """Debug: Explain why this tier was chosen."""
        return {
            'tier': decision.tier,
            'reasons': decision.reasons,
            'token_count': len(text.split()),
            'is_complex': self._is_complex(text),
            'has_rgpd_critical': self._has_rgpd_critical(text),
            'has_simple_patterns': self._has_simple_patterns(text)
        }

    def get_stats(self) -> Dict:
        """Get routing statistics."""
        total = sum(self.stats.values())
        if total == 0:
            return {'tier1': 0, 'tier2': 0, 'tier3': 0, 'total': 0, 'free_pct': 0}
        
        free = self.stats['tier1'] + self.stats['tier2']
        return {
            'tier1': self.stats['tier1'],
            'tier2': self.stats['tier2'],
            'tier3': self.stats['tier3'],
            'total': total,
            'free_pct': (free / total) * 100
        }
