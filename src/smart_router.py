"""
Smart Router V3: Intelligent Heuristic Scoring System
Routes notes based on multi-dimensional complexity analysis (0-100 score).

PHILOSOPHY:
- Tier 1 (Rules): Score < 25 → Simple, deterministic cases
- Tier 2 (Mistral): Score 25-75 → Standard complexity
- Tier 3 (Mistral Premium): Score > 75 → Complex, critical, ambiguous cases

SCORING FACTORS (Weighted):
1. Text Complexity (25 points)
2. Linguistic Quality (20 points)
3. Business Criticality (30 points)
4. Intent Type (15 points)
5. RGPD/Risk Flags (10 points)
"""

import re
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComplexityScore:
    """Detailed complexity breakdown"""
    text_complexity: float = 0.0      # 0-25
    linguistic_quality: float = 0.0   # 0-20
    business_criticality: float = 0.0 # 0-30
    intent_type: float = 0.0          # 0-15
    risk_flags: float = 0.0           # 0-10
    
    total: float = 0.0                # 0-100
    factors: List[str] = field(default_factory=list)
    
    def calculate_total(self):
        """Calculate final score"""
        self.total = (
            self.text_complexity +
            self.linguistic_quality +
            self.business_criticality +
            self.intent_type +
            self.risk_flags
        )
        return self.total


@dataclass
class RoutingDecision:
    """Enhanced routing decision with scoring"""
    tier: int                          # 1, 2, or 3
    score: ComplexityScore
    confidence: float                  # 0-1
    reasons: List[str]
    priority: str                      # 'low', 'medium', 'high', 'critical'
    estimated_cost: float              # USD
    estimated_time_ms: float           # milliseconds
    fallback_tier: Optional[int] = None


class SmartRouterV3:
    """
    Intelligent router avec scoring heuristique multi-dimensionnel.
    """
    
    # ═══════════════════════════════════════════════════════════════
    # SCORING WEIGHTS & THRESHOLDS (OPTIMIZED V3)
    # ═══════════════════════════════════════════════════════════════
    
    # Seuils optimisés pour notes écrites
    # Objectif: 20-30% en Tier 1 (vs 4% avant)
    TIER1_MAX_SCORE = 20   # Plus strict: score < 20 = Tier 1
    TIER2_MAX_SCORE = 60  # Score 20-60 = Tier 2
    
    TIER_COSTS = {1: 0.0, 2: 0.0001, 3: 0.005}
    TIER_TIMES = {1: 50, 2: 3000, 3: 5000}
    
    LENGTH_THRESHOLDS = {
        (0, 30): 0, (30, 100): 5, (100, 250): 10,
        (250, 500): 15, (500, 1000): 20, (1000, 9999): 25,
    }
    
    # 2. LINGUISTIC QUALITY (0-20 points)
    LINGUISTIC_RED_FLAGS = {
        'mixed_language': (r'\b(I want|looking for)\b.*\b(sac|cadeau|cherche)\b', 8),
        'spelling_errors': (r'\b(euhhh|hmmmm|beeeen|ouaiii)\b', 5),
        'excessive_punct': (r'([!?.])\1{2,}', 3),
        'no_punctuation': (r'^[^.!?]{100,}$', 6),
        'abbreviations': (r'\b(rdv|svp|tlj|bjr|qq|qqn)\b', 4),
    }
    
    # 3. BUSINESS CRITICALITY (0-30 points) - WEIGHTS OPTIMIZED
    # Réduits car Tier 1 peut extraire VIC, budget, allergies
    BUSINESS_CRITICAL_PATTERNS = {
        'vic': (r'\bVIC\b', 8),           # AVANT: 15 (Tier 1 gère VIC)
        'vip': (r'\bVIP\b', 10),          # AVANT: 12
        'ultimate': (r'\b(ultimate|platinum)\b', 12),  # AVANT: 20
        # Keep budget scoring contextual to avoid false positives such as
        # "800K followers" being interpreted as client budget.
        'budget_10k': (
            r'\b(?:budget|prix|panier|enveloppe|spend|spesa|invest(?:ir|ire)?|around|about|circa)\b'
            r'[^.\n]{0,24}\b(1[0-9]|[2-9]\d)\s*[kK]\b',
            7,  # AVANT: 10
        ),
        'budget_50k': (
            r'\b(?:budget|prix|panier|enveloppe|spend|spesa|invest(?:ir|ire)?|around|about|circa)\b'
            r'[^.\n]{0,24}\b([5-9]\d|[1-9]\d{2})\s*[kK]\b',
            10,  # AVANT: 15
        ),
        'budget_vague': (r'\b(flexible|ouvert|sans limite|no limit)\b', 4),  # AVANT: 8
        'allergy_severe': (r'\b(allergi.*(?:grave|sévère)|choc|anaphyla)', 12),
        'allergy_medium': (r'\b(allergi.*(?:importante?|forte?))', 6),
        'complaint': (r'\b(plainte|complaint|déçu|insatisfait|problème|mécontent|pas content)\b', 10),
        'urgent': (r"\b(urgent|asap|aujourd'hui|today|demain|tomorrow)\b", 8),
        'multi_product': (r'\b(et|and|\+).*(sac|bag|ceinture|belt|montre|watch)', 5),
        'gift_important': (r'\b(cadeau|gift).*(mari|épouse|ceo|directeur|boss)\b', 6),
    }
    
    # 4. INTENT TYPE (0-15 points) - OPTIMIZED
    # "ou" seul = 3pts, comparison stricte = 12pts
    INTENT_PATTERNS = {
        'advisory': (r'\b(conseil.*|recommand.*|suggest.*|que.*pens.*|what.*think|advice)\b', 15),
        'comparison': (r'\b(versus|vs|différence|compare|between)\b', 12),  # AVANT: incluait "ou|or"
        'simple_or': (r'(?<![a-zA-Z])(ou|or)(?!\s*\w+\s+(ou|or)\b)(?:\s|$|\?|!|\.)', 3),  # NOUVEAU: "ou" seul = 3pts
        'negation': (r'\b(pas de|sans|non|not|no|except|sauf)\b', 10),
        'conditional': (r'\b(si|if|peut-être|maybe|depends?|selon)\b', 8),
        'simple_lookup': (r'\b(cherche|veux|want|looking for|besoin|need)\s+(un|une|le|la|a)\s+\w+\b', 0),
    }
    
    # 5. RISK FLAGS (0-10 points)
    RISK_PATTERNS = {
        'rgpd_health': (r'\b(cancer|vih|hiv|diabète|dépression|psychiatr|hospitalis)\b', 10),
        'rgpd_legal': (r'\b(divorc|procès|prison|garde.vue|condamn)', 10),
        'rgpd_financial': (r'\b(faillite|liquidation|surendett|saisie)\b', 8),
        'fraud': (r'\b(cash only|no receipt|urgent.*cash|sans facture)\b', 10),
        'export': (r'\b(russia|iran|north\s*korea|corée.*nord)\b', 8),
    }
    
    NEGATION_CONTEXT = [
        r'(ne|pas|sans|non|not|no)\s+.{0,30}(cherche|veux|want|besoin)',
        r'(sauf|except|excluding)\s+',
        r'(jamais|never|rien|nothing)',
    ]
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.tier1_max = self.config.get('tier1_max_score', self.TIER1_MAX_SCORE)
        self.tier2_max = self.config.get('tier2_max_score', self.TIER2_MAX_SCORE)
        # Mode écrit: ignorer les petites fautes (défaut: True pour app web)
        self.is_written_mode = self.config.get('is_written_mode', True)
        self.stats = {'total_routed': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0, 'scores': [], 'avg_score': 0.0}
    
    def _score_text_complexity(self, text: str) -> Tuple[float, List[str]]:
        score, reasons = 0.0, []
        words = text.split()
        word_count = len(words)
        
        for (min_w, max_w), points in self.LENGTH_THRESHOLDS.items():
            if min_w <= word_count < max_w:
                score += points
                if points > 10: reasons.append(f"Texte long ({word_count} mots): +{points}")
                break
        
        sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
        if sentences:
            avg = word_count / len(sentences)
            if avg > 30: score += 5; reasons.append(f"Phrases complexes (avg {avg:.0f} mots): +5")
        
        q_count = text.count('?')
        if q_count >= 3: score += 3; reasons.append(f"Multiples questions ({q_count}): +3")
        
        return min(score, 25.0), reasons
    
    def _score_linguistic_quality(self, text: str) -> Tuple[float, List[str]]:
        """
        Score linguistic quality with mode awareness.
        In written mode: reduce penalties for minor errors (notes are typed, not spoken).
        """
        score, reasons = 0.0, []
        
        for name, (pattern, points) in self.LINGUISTIC_RED_FLAGS.items():
            if re.search(pattern, text, re.IGNORECASE):
                # Mode écrit: pénalité réduite de moitié pour fautes mineures
                if self.is_written_mode and name in ('spelling_errors', 'abbreviations', 'excessive_punct'):
                    adjusted_points = points // 2
                else:
                    adjusted_points = points
                    
                if adjusted_points > 0:
                    score += adjusted_points
                    reasons.append(f"{name.replace('_', ' ').title()}: +{adjusted_points}")
        
        return min(score, 20.0), reasons
    
    def _score_business_criticality(self, text: str) -> Tuple[float, List[str]]:
        score, reasons = 0.0, []
        for name, (pattern, points) in self.BUSINESS_CRITICAL_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                score += points
                reasons.append(f"{name.replace('_', ' ').title()}: +{points}")
        return min(score, 30.0), reasons
    
    def _score_intent_type(self, text: str) -> Tuple[float, List[str]]:
        score, reasons = 0.0, []
        intent_scores = []
        for name, (pattern, points) in self.INTENT_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                intent_scores.append((name, points))
        if intent_scores:
            intent_scores.sort(key=lambda x: x[1], reverse=True)
            top, points = intent_scores[0]
            score = points
            reasons.append(f"Intent: {top.replace('_', ' ').title()}: +{points}")
        return min(score, 15.0), reasons
    
    def _score_risk_flags(self, text: str) -> Tuple[float, List[str]]:
        score, reasons = 0.0, []
        for name, (pattern, points) in self.RISK_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                score += points
                reasons.append(f"🚨 {name.replace('_', ' ').title()}: +{points}")
        return min(score, 10.0), reasons
    
    def _has_negation_context(self, text: str) -> bool:
        for pattern in self.NEGATION_CONTEXT:
            if re.search(pattern, text, re.IGNORECASE): return True
        return False
    
    def calculate_complexity_score(self, text: str) -> ComplexityScore:
        score = ComplexityScore()
        
        t, r = self._score_text_complexity(text); score.text_complexity = t; score.factors.extend(r)
        l, r = self._score_linguistic_quality(text); score.linguistic_quality = l; score.factors.extend(r)
        b, r = self._score_business_criticality(text); score.business_criticality = b; score.factors.extend(r)
        i, r = self._score_intent_type(text); score.intent_type = i; score.factors.extend(r)
        k, r = self._score_risk_flags(text); score.risk_flags = k; score.factors.extend(r)
        
        score.calculate_total()
        
        if self._has_negation_context(text):
            score.total += 15
            score.factors.append("⚠️ Negation context detected: +15")
        
        return score
    
    def route(self, text: str, language: str = 'FR', metadata: Optional[Dict] = None) -> RoutingDecision:
        metadata = metadata or {}
        complexity = self.calculate_complexity_score(text)
        
        # RGPD BOOST: If RGPD keywords detected, boost score to force Tier 2 minimum
        if complexity.risk_flags >= 8:  # RGPD patterns score 8-10 pts
            rgpd_boost = 30
            complexity.total += rgpd_boost
            complexity.factors.append(f"🔒 RGPD detected → Force Tier 2+ (+{rgpd_boost} pts)")
        
        # Determine tier based on (potentially boosted) score
        if complexity.total < self.tier1_max:
            tier, confidence, priority, fallback = 1, 0.85, 'low', 2
        elif complexity.total < self.tier2_max:
            tier, confidence, priority, fallback = 2, 0.80, 'medium', 3
        else:
            tier, confidence = 3, 0.90
            priority = 'high' if complexity.total < 90 else 'critical'
            fallback = None
        
        # Only force Tier 3 for VERY critical RGPD (>=10 points, not 8)
        if complexity.risk_flags >= 10:
            tier, confidence, priority = 3, 0.95, 'critical'
            complexity.factors.append("🚨 Critical risk → Force Tier 3")
        
        # Complaint override: complaints are sensitive, force Tier 3
        if complexity.business_criticality >= 10 and re.search(r'\b(plainte|complaint|déçu|insatisfait|pas content|mécontent)\b', text, re.IGNORECASE):
            tier, priority = 3, 'high'
            complexity.factors.append("⚠️ Complaint detected → Force Tier 3")
        
        # VIC in text detection (if metadata not provided but VIC in text)
        has_vic_in_text = bool(re.search(r'\bVIC\b', text))
        client_status_from_meta = metadata.get('client_status')
        
        if (client_status_from_meta in ['vic', 'ultimate', 'platinum'] or has_vic_in_text) and complexity.total > 60:
            tier, priority = 3, 'critical'
            complexity.factors.append("👑 VIC/Ultimate + Very Complex → Premium Tier 3")
        
        self.stats['total_routed'] += 1
        self.stats[f'tier{tier}'] += 1
        self.stats['scores'].append(complexity.total)
        self.stats['avg_score'] = sum(self.stats['scores']) / len(self.stats['scores'])
        
        return RoutingDecision(
            tier=tier, score=complexity, confidence=confidence, reasons=complexity.factors,
            priority=priority, estimated_cost=self.TIER_COSTS[tier],
            estimated_time_ms=self.TIER_TIMES[tier], fallback_tier=fallback
        )
    
    def explain_decision(self, text: str, language: str = 'FR') -> Dict:
        d = self.route(text, language)
        return {
            'tier': d.tier, 'total_score': d.score.total,
            'score_breakdown': {
                'text_complexity': d.score.text_complexity, 'linguistic_quality': d.score.linguistic_quality,
                'business_criticality': d.score.business_criticality, 'intent_type': d.score.intent_type,
                'risk_flags': d.score.risk_flags,
            },
            'factors': d.score.factors, 'confidence': d.confidence, 'priority': d.priority,
            'estimated_cost_usd': d.estimated_cost, 'estimated_time_ms': d.estimated_time_ms,
            'fallback_tier': d.fallback_tier, 'word_count': len(text.split()),
        }
    
    def get_stats(self) -> Dict:
        """Get detailed routing statistics with cost savings."""
        total = self.stats['total_routed']
        if total == 0: 
            return {
                'total': 0, 'tier1_pct': 0, 'tier2_pct': 0, 'tier3_pct': 0, 
                'avg_score': 0, 'free_processing_pct': 0,
                'estimated_cost_usd': 0, 'savings_vs_all_tier2': 0
            }
        
        free = self.stats['tier1'] + self.stats['tier2']
        
        # Calcul coût actuel
        tier1_cost = self.stats['tier1'] * self.TIER_COSTS[1]
        tier2_cost = self.stats['tier2'] * self.TIER_COSTS[2]
        tier3_cost = self.stats['tier3'] * self.TIER_COSTS[3]
        total_cost = tier1_cost + tier2_cost + tier3_cost
        
        # Économie vs tout en Tier 2
        all_tier2_cost = total * self.TIER_COSTS[2]
        savings = all_tier2_cost - total_cost
        
        return {
            'total_routed': total, 
            'tier1': self.stats['tier1'], 
            'tier2': self.stats['tier2'], 
            'tier3': self.stats['tier3'],
            'tier1_pct': round((self.stats['tier1'] / total) * 100, 1), 
            'tier2_pct': round((self.stats['tier2'] / total) * 100, 1),
            'tier3_pct': round((self.stats['tier3'] / total) * 100, 1), 
            'avg_score': round(self.stats['avg_score'], 1),
            'free_processing_pct': round((free / total) * 100, 1),
            'estimated_cost_usd': round(total_cost, 6),
            'savings_vs_all_tier2': round(savings, 6),
            'tier1_threshold': self.tier1_max,
            'is_written_mode': self.is_written_mode,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # ML-ENHANCED ROUTER (Learning from Feedback)
    # ═══════════════════════════════════════════════════════════════
    
    def _init_ml(self):
        """Initialize ML components (lazy load)"""
        if not hasattr(self, 'ml_initialized'):
            self.ml_initialized = True
            self.feedback_data = []
            self.ml_model = None
            self.ml_scaler = None
            self.ml_confidence_threshold = 0.85  # Progressive: starts high
            self.ml_min_samples = 50
            self.ml_last_train_date = None
            self.ml_accuracy_history = []
            
            # Try to load existing model
            self._load_model()
    
    def record_feedback(
        self, 
        text: str,
        predicted_tier: int,
        executed_tier: int,
        confidence_achieved: float,
        was_escalated: bool = False,
        final_tier: Optional[int] = None,
        final_confidence: Optional[float] = None
    ):
        """
        Record feedback for ML training.
        
        IMPORTANT: Label is based on final_tier (the tier that ACTUALLY succeeded),
        not the predicted_tier.
        
        Args:
            text: Original note text
            predicted_tier: Tier predicted by router
            executed_tier: First tier that executed
            confidence_achieved: Confidence from executed tier
            was_escalated: Whether note was escalated to higher tier
            final_tier: Tier that ultimately succeeded (for training label)
            final_confidence: Confidence from final tier
        """
        self._init_ml()
        
        # Extract features from text
        complexity = self.calculate_complexity_score(text)
        
        # Determine training label (the tier that WORKED)
        if final_tier is not None:
            label = final_tier
        elif was_escalated:
            label = executed_tier + 1  # Escalated means current tier failed
        else:
            label = executed_tier  # Current tier succeeded
        
        features = [
            complexity.text_complexity,
            complexity.linguistic_quality,
            complexity.business_criticality,
            complexity.intent_type,
            complexity.risk_flags,
            len(text.split()),  # word_count
        ]
        
        feedback_entry = {
            'features': features,
            'predicted_tier': predicted_tier,
            'executed_tier': executed_tier,
            'confidence_achieved': confidence_achieved,
            'was_escalated': was_escalated,
            'final_tier': final_tier or label,
            'final_confidence': final_confidence or confidence_achieved,
            'label': label,  # Training target
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        
        # Save feedback to disk
        self._save_feedback()
        
        logger.debug(f"Recorded feedback: predicted={predicted_tier}, final={label}, samples={len(self.feedback_data)}")
        
        # Auto re-train check
        self._check_retrain()
    
    def _save_feedback(self):
        """Persist feedback data to disk"""
        import json
        from pathlib import Path
        
        def convert_to_native(obj):
            """Convert numpy types to native Python types for JSON serialization"""
            if hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            elif isinstance(obj, dict):
                return {str(k): convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(i) for i in obj]
            return obj
        
        feedback_path = Path('cache/ml_router_feedback.json')
        feedback_path.parent.mkdir(exist_ok=True)
        
        # Convert to native types before saving
        data_to_save = convert_to_native(self.feedback_data)
        
        with open(feedback_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    
    def _load_feedback(self):
        """Load feedback data from disk"""
        import json
        from pathlib import Path
        
        feedback_path = Path('cache/ml_router_feedback.json')
        if feedback_path.exists():
            with open(feedback_path, 'r', encoding='utf-8') as f:
                self.feedback_data = json.load(f)
            logger.info(f"Loaded {len(self.feedback_data)} feedback samples")
    
    def _check_retrain(self):
        """Check if retraining is needed (weekly or accuracy drop)"""
        from datetime import datetime, timedelta
        
        # Check sample count
        if len(self.feedback_data) < self.ml_min_samples:
            return
        
        # Check time since last train (weekly re-train)
        if self.ml_last_train_date:
            days_since = (datetime.now() - self.ml_last_train_date).days
            if days_since < 7:
                return  # Too soon
        
        # Train model
        self.train_model()
    
    def train_model(self):
        """
        Train ML model on collected feedback.
        
        Features: [text_complexity, linguistic_quality, business_criticality, intent_type, risk_flags, word_count]
        Label: final_tier (1, 2, or 3)
        """
        self._init_ml()
        
        if len(self.feedback_data) < self.ml_min_samples:
            logger.warning(f"Not enough samples for training ({len(self.feedback_data)}/{self.ml_min_samples})")
            return False
        
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import cross_val_score
            import numpy as np
        except ImportError:
            logger.error("scikit-learn not installed. Run: pip install scikit-learn")
            return False
        
        # Prepare data
        X = np.array([d['features'] for d in self.feedback_data])
        y = np.array([d['label'] for d in self.feedback_data])
        
        # Check class distribution
        unique, counts = np.unique(y, return_counts=True)
        class_dist = dict(zip(unique, counts))
        logger.info(f"Class distribution: {class_dist}")
        
        # Feature scaling (helps with drift)
        self.ml_scaler = StandardScaler()
        X_scaled = self.ml_scaler.fit_transform(X)
        
        # Train with class balancing (handles imbalance)
        self.ml_model = RandomForestClassifier(
            n_estimators=100,
            class_weight='balanced',  # ⭐ Handles class imbalance
            random_state=42,
            n_jobs=-1
        )
        
        # Cross-validation to estimate accuracy
        cv_scores = cross_val_score(self.ml_model, X_scaled, y, cv=5)
        avg_accuracy = cv_scores.mean()
        
        # Fit on all data
        self.ml_model.fit(X_scaled, y)
        
        # Update training metadata
        from datetime import datetime
        self.ml_last_train_date = datetime.now()
        self.ml_accuracy_history.append({
            'date': self.ml_last_train_date.isoformat(),
            'accuracy': avg_accuracy,
            'samples': len(self.feedback_data),
            'class_distribution': class_dist
        })
        
        # Progressive confidence: lower threshold as accuracy improves
        if avg_accuracy > 0.90:
            self.ml_confidence_threshold = 0.70
        elif avg_accuracy > 0.85:
            self.ml_confidence_threshold = 0.75
        elif avg_accuracy > 0.80:
            self.ml_confidence_threshold = 0.80
        else:
            self.ml_confidence_threshold = 0.85
        
        # Save model
        self._save_model()
        
        logger.info(f"ML Model trained: accuracy={avg_accuracy:.2%}, samples={len(self.feedback_data)}, threshold={self.ml_confidence_threshold}")
        
        return True
    
    def _save_model(self):
        """Persist ML model to disk"""
        from pathlib import Path
        
        try:
            import joblib
        except ImportError:
            logger.warning("joblib not installed, model not saved")
            return
        
        model_dir = Path('models')
        model_dir.mkdir(exist_ok=True)
        
        if self.ml_model:
            joblib.dump(self.ml_model, model_dir / 'router_ml_model.pkl')
        if self.ml_scaler:
            joblib.dump(self.ml_scaler, model_dir / 'router_ml_scaler.pkl')
        
        # Save metadata
        import json
        
        def convert_to_native(obj):
            """Convert numpy types to native Python types"""
            if hasattr(obj, 'item'):
                return obj.item()
            elif isinstance(obj, dict):
                return {str(k): convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(i) for i in obj]
            return obj
        
        metadata = {
            'last_train_date': self.ml_last_train_date.isoformat() if self.ml_last_train_date else None,
            'confidence_threshold': self.ml_confidence_threshold,
            'accuracy_history': convert_to_native(self.ml_accuracy_history)
        }
        with open(model_dir / 'router_ml_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("ML Model saved to models/")
    
    def _load_model(self):
        """Load ML model from disk"""
        from pathlib import Path
        import json
        
        try:
            import joblib
        except ImportError:
            return
        
        model_dir = Path('models')
        model_path = model_dir / 'router_ml_model.pkl'
        scaler_path = model_dir / 'router_ml_scaler.pkl'
        metadata_path = model_dir / 'router_ml_metadata.json'
        
        if model_path.exists():
            self.ml_model = joblib.load(model_path)
            logger.info("Loaded ML model from disk")
        
        if scaler_path.exists():
            self.ml_scaler = joblib.load(scaler_path)
        
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            self.ml_confidence_threshold = metadata.get('confidence_threshold', 0.85)
            self.ml_accuracy_history = metadata.get('accuracy_history', [])
            if metadata.get('last_train_date'):
                from datetime import datetime
                self.ml_last_train_date = datetime.fromisoformat(metadata['last_train_date'])
        
        # Load feedback data
        self._load_feedback()
    
    def route_ml(
        self, 
        text: str, 
        language: str = 'FR',
        metadata: Optional[Dict] = None
    ) -> RoutingDecision:
        """
        Hybrid ML + Heuristic routing.
        
        Uses ML prediction if model is trained and confident,
        otherwise falls back to heuristic scoring.
        """
        self._init_ml()
        
        # Always get heuristic decision as fallback
        heuristic_decision = self.route(text, language, metadata)
        
        # Check if ML is available
        if self.ml_model is None:
            logger.debug("ML model not trained, using heuristic")
            return heuristic_decision
        
        try:
            import numpy as np
        except ImportError:
            return heuristic_decision
        
        # Extract features
        complexity = heuristic_decision.score
        features = np.array([[
            complexity.text_complexity,
            complexity.linguistic_quality,
            complexity.business_criticality,
            complexity.intent_type,
            complexity.risk_flags,
            len(text.split()),
        ]])
        
        # Scale features
        if self.ml_scaler:
            features = self.ml_scaler.transform(features)
        
        # ML prediction with confidence
        ml_tier = self.ml_model.predict(features)[0]
        ml_proba = self.ml_model.predict_proba(features)[0]
        # Works with numpy arrays and list-like outputs from model wrappers.
        ml_confidence = float(max(ml_proba))
        
        # Safety floor: ML must never downgrade critical heuristic decisions.
        safety_floor = 1
        if heuristic_decision.score.risk_flags >= 8:
            safety_floor = max(safety_floor, 2)
        if heuristic_decision.priority in ['high', 'critical'] or heuristic_decision.tier >= 3:
            safety_floor = max(safety_floor, heuristic_decision.tier)
        
        # Decision: Use ML if confident enough
        if ml_confidence >= self.ml_confidence_threshold:
            tier = max(ml_tier, safety_floor)
            confidence = ml_confidence
            reasons = heuristic_decision.reasons + [f"🤖 ML prediction (conf: {ml_confidence:.2f})"]
            if tier != ml_tier:
                reasons.append(f"🛡️ Safety floor applied (heuristic floor={safety_floor}, ml={ml_tier})")
        else:
            # Fallback to heuristic
            tier = heuristic_decision.tier
            confidence = heuristic_decision.confidence
            reasons = heuristic_decision.reasons + [f"📊 ML low confidence ({ml_confidence:.2f}), using heuristic"]
        
        # Determine priority
        priority = heuristic_decision.priority
        if tier == 3 and priority != 'critical':
            priority = 'high'
        
        return RoutingDecision(
            tier=tier,
            score=complexity,
            confidence=confidence,
            reasons=reasons,
            priority=priority,
            estimated_cost=self.TIER_COSTS[tier],
            estimated_time_ms=self.TIER_TIMES[tier],
            fallback_tier=heuristic_decision.tier if tier != heuristic_decision.tier else None
        )
    
    def get_ml_stats(self) -> Dict:
        """Get ML-specific statistics"""
        self._init_ml()
        
        return {
            'ml_enabled': self.ml_model is not None,
            'feedback_samples': len(self.feedback_data),
            'min_samples_needed': self.ml_min_samples,
            'confidence_threshold': self.ml_confidence_threshold,
            'last_train_date': self.ml_last_train_date.isoformat() if self.ml_last_train_date else None,
            'accuracy_history': self.ml_accuracy_history[-5:] if self.ml_accuracy_history else []
        }


# Alias for backward compatibility
SmartRouterV2 = SmartRouterV3

