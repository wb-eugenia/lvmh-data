"""
Cross-Validator - Validation croisée entre Tiers
Fusion intelligente des résultats de différents tiers pour maximiser la précision
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import Counter
import json

logger = logging.getLogger(__name__)


@dataclass
class FieldConfidence:
    """Confidence score for a specific field"""
    value: Any
    confidence: float
    sources: List[int] = field(default_factory=list)  # Which tiers provided this value
    
    def to_dict(self) -> Dict:
        return {
            'value': self.value,
            'confidence': self.confidence,
            'sources': self.sources
        }


@dataclass
class ValidationResult:
    """Result of cross-validation between tiers"""
    merged_result: Dict[str, Any]
    field_confidences: Dict[str, FieldConfidence]
    agreement_score: float  # 0-1, how much tiers agree
    dominant_tier: int  # Which tier contributed most
    validation_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'merged_result': self.merged_result,
            'field_confidences': {k: v.to_dict() for k, v in self.field_confidences.items()},
            'agreement_score': self.agreement_score,
            'dominant_tier': self.dominant_tier,
            'validation_notes': self.validation_notes
        }


class CrossValidator:
    """
    Valide et fusionne les résultats de différents tiers
    
    Stratégie de fusion:
    1. Champs simples (catégories): Vote majoritaire pondéré par confiance
    2. Champs complexes (préférences): Union avec déduplication
    3. Champs critiques (budget, allergies): Tier le plus élevé gagne
    4. Champs incertains: Marquer pour review humain
    """
    
    # Field weights by importance
    FIELD_WEIGHTS = {
        'produit': 1.0,
        'categorie': 1.0,
        'couleur': 0.8,
        'matiere': 0.8,
        'budget': 1.5,  # Critique
        'allergies': 1.5,  # Critique
        'occasion': 0.9,
        'relation': 0.7,
        'vip_status': 1.2,
    }
    
    # Tier reliability weights
    TIER_WEIGHTS = {
        1: 0.7,  # Rules - rapide mais basique
        2: 0.85,  # LLM local - bon équilibre
        3: 0.95,  # GPT-4 - plus précis
    }
    
    def __init__(self, agreement_threshold: float = 0.6):
        self.agreement_threshold = agreement_threshold
    
    def validate(
        self,
        tier_results: Dict[int, Dict[str, Any]],
        tier_confidences: Optional[Dict[int, float]] = None
    ) -> ValidationResult:
        """
        Valide et fusionne les résultats de plusieurs tiers
        
        Args:
            tier_results: {tier_number: extraction_result}
            tier_confidences: {tier_number: confidence_score}
        
        Returns:
            ValidationResult avec résultat fusionné et métadonnées
        """
        if not tier_results:
            return ValidationResult(
                merged_result={},
                field_confidences={},
                agreement_score=0.0,
                dominant_tier=0,
                validation_notes=["No tier results provided"]
            )
        
        # Normalize confidences
        if tier_confidences is None:
            tier_confidences = {tier: self.TIER_WEIGHTS.get(tier, 0.7) 
                              for tier in tier_results.keys()}
        
        # Collect all fields
        all_fields = set()
        for result in tier_results.values():
            all_fields.update(self._flatten_result(result).keys())
        
        # Validate each field
        field_confidences = {}
        merged_result = {}
        validation_notes = []
        
        for field in all_fields:
            field_conf = self._validate_field(
                field, tier_results, tier_confidences
            )
            field_confidences[field] = field_conf
            
            if field_conf.confidence > 0.5:  # Only include confident fields
                self._set_nested_value(merged_result, field, field_conf.value)
            
            if field_conf.confidence < 0.6:
                validation_notes.append(
                    f"Low confidence for '{field}' ({field_conf.confidence:.2f})"
                )
        
        # Calculate agreement score
        agreement_score = self._calculate_agreement(tier_results, field_confidences)
        
        # Determine dominant tier
        dominant_tier = self._get_dominant_tier(tier_results, field_confidences)
        
        # Add summary note
        if agreement_score < self.agreement_threshold:
            validation_notes.append(
                f"Low inter-tier agreement ({agreement_score:.2f}) - consider Tier 3 review"
            )
        
        return ValidationResult(
            merged_result=merged_result,
            field_confidences=field_confidences,
            agreement_score=agreement_score,
            dominant_tier=dominant_tier,
            validation_notes=validation_notes
        )
    
    def _flatten_result(self, result: Dict, prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dict to dot-notation keys"""
        items = {}
        for key, value in result.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                items.update(self._flatten_result(value, new_key))
            else:
                items[new_key] = value
        return items
    
    def _validate_field(
        self,
        field: str,
        tier_results: Dict[int, Dict[str, Any]],
        tier_confidences: Dict[int, float]
    ) -> FieldConfidence:
        """
        Validate a specific field across tiers
        Different strategies based on field type
        """
        # Collect values from all tiers
        values = {}
        for tier, result in tier_results.items():
            flat_result = self._flatten_result(result)
            if field in flat_result:
                values[tier] = flat_result[field]
        
        if not values:
            return FieldConfidence(value=None, confidence=0.0, sources=[])
        
        # Determine field type and validation strategy
        if self._is_enrichment_field(field):
            return self._validate_enrichment_field(field, values, tier_confidences)
        elif self._is_list_field(field):
            return self._validate_list_field(field, values, tier_confidences)
        elif self._is_critical_field(field):
            return self._validate_critical_field(field, values, tier_confidences)
        else:
            return self._validate_simple_field(field, values, tier_confidences)
    
    def _is_list_field(self, field: str) -> bool:
        """Check if field is a list type (colors, materials, etc.)"""
        list_indicators = ['couleurs', 'colors', 'matieres', 'materials', 
                          'preferences', 'tags', 'categories', 'produits_mentionnes']
        return any(ind in field.lower() for ind in list_indicators)
    
    def _is_enrichment_field(self, field: str) -> bool:
        """Fields that should be preserved from lowest tier with data"""
        # Meta analysis fields - always take from Tier 1 (T1 calculates them correctly)
        if field.startswith('meta_analysis.'):
            return True
        # Pilier 4 budget specific - T1 extracts exact amounts
        if 'budget_specific' in field:
            return True
        # Product mentions - T1 extracts via regex
        if 'produits_mentionnes' in field:
            return True
        return False
    
    def _is_tier1_priority_field(self, field: str) -> bool:
        """Fields where Tier 1 (regex) is more reliable than LLM"""
        tier1_fields = ['produits_mentionnes', 'budget_specific', 'quality_score', 
                       'completeness_score', 'missing_info', 'advisor_feedback']
        return any(f in field for f in tier1_fields)
    
    def _is_critical_field(self, field: str) -> bool:
        """Check if field is critical (budget, allergies)"""
        critical = ['budget', 'allergies', 'allergy', 'medical', 'health']
        return any(crit in field.lower() for crit in critical)
    
    def _validate_simple_field(
        self,
        field: str,
        values: Dict[int, Any],
        tier_confidences: Dict[int, float]
    ) -> FieldConfidence:
        """Validate simple scalar field by weighted voting"""
        # Count weighted votes for each value
        value_votes = Counter()
        value_sources = {}
        
        for tier, value in values.items():
            # Normalize value for comparison
            norm_value = self._normalize_value(value)
            weight = tier_confidences.get(tier, 0.7)
            
            value_votes[norm_value] += weight
            
            # Track sources per normalized value
            if norm_value not in value_sources:
                value_sources[norm_value] = []
            value_sources[norm_value].append(tier)
        
        if not value_votes:
            return FieldConfidence(value=None, confidence=0.0, sources=[])
        
        # Get winning value
        best_value, best_votes = value_votes.most_common(1)[0]
        total_votes = sum(value_votes.values())
        confidence = best_votes / total_votes if total_votes > 0 else 0.0
        
        # Apply field weight
        field_weight = self.FIELD_WEIGHTS.get(field.split('.')[-1], 1.0)
        confidence = min(confidence * field_weight, 1.0)
        
        # Get original value (not normalized)
        original_value = values[value_sources[best_value][0]]
        
        return FieldConfidence(
            value=original_value,
            confidence=confidence,
            sources=value_sources[best_value]
        )
    
    def _validate_list_field(
        self,
        field: str,
        values: Dict[int, Any],
        tier_confidences: Dict[int, float]
    ) -> FieldConfidence:
        """Validate list field by union with confidence weighting"""
        # Collect all items with their source tiers
        item_sources = {}  # item -> list of tiers
        
        for tier, value in values.items():
            if not isinstance(value, list):
                value = [value] if value else []
            
            for item in value:
                norm_item = self._normalize_value(item)
                if norm_item not in item_sources:
                    item_sources[norm_item] = {'original': item, 'tiers': []}
                item_sources[norm_item]['tiers'].append(tier)
        
        if not item_sources:
            return FieldConfidence(value=[], confidence=0.0, sources=[])
        
        # Calculate confidence for each item
        merged_items = []
        all_sources = set()
        
        for norm_item, data in item_sources.items():
            # Confidence = proportion of tiers that mentioned this item
            item_confidence = len(data['tiers']) / len(values)
            if item_confidence >= 0.3:  # At least 30% of tiers
                merged_items.append(data['original'])
                all_sources.update(data['tiers'])
        
        # Overall confidence based on agreement
        confidence = len(merged_items) / max(len(item_sources), 1)
        confidence = min(confidence * 1.2, 1.0)  # Boost for list fields
        
        return FieldConfidence(
            value=merged_items,
            confidence=confidence,
            sources=list(all_sources)
        )
    
    def _validate_critical_field(
        self,
        field: str,
        values: Dict[int, Any],
        tier_confidences: Dict[int, float]
    ) -> FieldConfidence:
        """Validate critical field - highest tier wins"""
        # Find highest tier that provided this field
        best_tier = max(values.keys(), key=lambda t: (t, tier_confidences.get(t, 0)))
        
        value = values[best_tier]
        confidence = tier_confidences.get(best_tier, 0.7)
        
        # Boost confidence for critical fields from high tiers
        if best_tier >= 2:
            confidence = min(confidence * 1.1, 1.0)
        
        return FieldConfidence(
            value=value,
            confidence=confidence,
            sources=[best_tier]
        )
    
    def _validate_enrichment_field(
        self,
        field: str,
        values: Dict[int, Any],
        tier_confidences: Dict[int, float]
    ) -> FieldConfidence:
        """Validate enrichment field - Tier 1 always wins for these fields"""
        # For enrichment fields, always prefer Tier 1 (regex-based extraction)
        # as it's more reliable for specific patterns (budgets, products, scores)
        if 1 in values:
            value = values[1]
            # Check if T1 has valid data
            is_valid = False
            if value is not None:
                if isinstance(value, list) and len(value) > 0:
                    is_valid = True
                elif isinstance(value, str) and value.strip():
                    is_valid = True
                elif isinstance(value, (int, float)):
                    is_valid = True  # 0 is valid
                elif isinstance(value, dict) and len(value) > 0:
                    is_valid = True
            
            if is_valid:
                return FieldConfidence(
                    value=value,
                    confidence=tier_confidences.get(1, 0.7),
                    sources=[1]
                )
        
        # Fallback: take lowest tier with any data
        sorted_tiers = sorted(values.keys())
        for tier in sorted_tiers:
            if values[tier] is not None:
                return FieldConfidence(
                    value=values[tier],
                    confidence=tier_confidences.get(tier, 0.5),
                    sources=[tier]
                )
        
        # Last resort
        lowest_tier = sorted_tiers[0]
        return FieldConfidence(
            value=values[lowest_tier],
            confidence=0.0,
            sources=[lowest_tier]
        )
    
    def _normalize_value(self, value: Any) -> str:
        """Normalize value for comparison"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.lower().strip()
        return json.dumps(value, sort_keys=True)
    
    def _set_nested_value(self, result: Dict, key: str, value: Any):
        """Set value in nested dict using dot notation"""
        keys = key.split('.')
        current = result
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    def _calculate_agreement(
        self,
        tier_results: Dict[int, Dict],
        field_confidences: Dict[str, FieldConfidence]
    ) -> float:
        """Calculate overall agreement score between tiers"""
        if not field_confidences:
            return 0.0
        
        # Average confidence weighted by field importance
        total_weight = 0.0
        weighted_confidence = 0.0
        
        for field, conf in field_confidences.items():
            weight = self.FIELD_WEIGHTS.get(field.split('.')[-1], 1.0)
            weighted_confidence += conf.confidence * weight
            total_weight += weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    def _get_dominant_tier(
        self,
        tier_results: Dict[int, Dict],
        field_confidences: Dict[str, FieldConfidence]
    ) -> int:
        """Determine which tier contributed most to final result"""
        tier_contributions = Counter()
        
        for field_conf in field_confidences.values():
            for tier in field_conf.sources:
                tier_contributions[tier] += field_conf.confidence
        
        if not tier_contributions:
            return max(tier_results.keys()) if tier_results else 0
        
        return tier_contributions.most_common(1)[0][0]


# Singleton instance
_cross_validator: Optional[CrossValidator] = None


def get_cross_validator() -> CrossValidator:
    """Get or create cross-validator singleton"""
    global _cross_validator
    if _cross_validator is None:
        _cross_validator = CrossValidator()
    return _cross_validator
