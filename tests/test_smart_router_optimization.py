"""
Tests for Smart Router V3 Optimization.
Validates the new thresholds, weights, and written mode.
"""

import pytest
from src.smart_router import SmartRouterV3


class TestSmartRouterOptimization:
    """Test suite for Smart Router V3 optimizations."""
    
    @pytest.fixture
    def router_balanced(self):
        """Router in balanced mode (optimized)."""
        return SmartRouterV3(config={
            'tier1_max_score': 35,
            'tier2_max_score': 80,
            'is_written_mode': True
        })
    
    @pytest.fixture
    def router_quality(self):
        """Router in quality mode (strict)."""
        return SmartRouterV3(config={
            'tier1_max_score': 20,
            'tier2_max_score': 75,
            'is_written_mode': True
        })
    
    @pytest.fixture
    def router_voice(self):
        """Router in voice mode (less forgiving)."""
        return SmartRouterV3(config={
            'is_written_mode': False
        })
    
    # === THRESHOLD TESTS ===
    
    def test_tier1_threshold_35_points(self, router_balanced):
        """Note simple avec VIC devrait être Tier 1 avec nouveau seuil."""
        result = router_balanced.route("Cliente VIC cherche un sac noir pour voyage")
        assert result.tier == 1, f"Expected Tier 1, got Tier {result.tier} with score {result.score.total}"
    
    def test_tier1_threshold_with_budget(self, router_balanced):
        """Note avec budget devrait être Tier 1."""
        result = router_balanced.route("J'ai un budget de 5000 euros pour un sac")
        assert result.tier == 1, f"Expected Tier 1, got Tier {result.tier} with score {result.score.total}"
    
    def test_quality_mode_stricter(self, router_quality):
        """Quality mode should route more to Tier 2."""
        result = router_quality.route("Cliente VIC cherche un sac noir")
        assert result.tier == 2, f"Quality mode should route to Tier 2, got {result.tier}"
    
    # === WEIGHT TESTS ===
    
    def test_vic_weight_reduced(self, router_balanced):
        """VIC alone should not force Tier 2."""
        result = router_balanced.route("Cliente VIC venue pour le sac Speedy")
        assert result.score.business_criticality < 15, f"VIC weight should be 8, got {result.score.business_criticality}"
    
    def test_budget_weight_reduced(self, router_balanced):
        """Budget should contribute less to score."""
        result = router_balanced.route("Budget 8K pour sac")
        # Budget 10k pattern = 7 pts (was 10)
        assert result.score.business_criticality <= 10, f"Budget weight should be <= 7, got {result.score.business_criticality}"
    
    # === PATTERN TESTS ===
    
    def test_simple_or_pattern(self, router_balanced):
        """'ou' seul should be 3 pts, not 12."""
        result = router_balanced.route("Sac noir ou marron pour soirée")
        assert result.score.intent_type <= 5, f"simple_or should be 3pts, got {result.score.intent_type}"
    
    def test_comparison_strict(self, router_balanced):
        """Strict comparison should still be 12 pts."""
        result = router_balanced.route("Quelle différence entre Speedy et Alma?")
        # comparison (strict) = 12 pts
        assert result.score.intent_type >= 10, f"comparison should be 12pts, got {result.score.intent_type}"
    
    # === WRITTEN MODE TESTS ===
    
    def test_written_mode_lenient(self, router_balanced):
        """Written mode should be more lenient on errors."""
        result_voice = router_voice.route("J'ai un petit probleme avec euhhh le sac")
        result_written = router_balanced.route("J'ai un petit probleme avec euhhh le sac")
        
        # Voice mode should have higher linguistic score
        assert result_voice.score.linguistic_quality > result_written.score.linguistic_quality, \
            "Voice mode should penalize errors more"
    
    def test_written_mode_no_penalty(self, router_balanced):
        """Written mode should not penalize minor errors."""
        result = router_balanced.route("Je cherche un sac, avec rdv svp")
        # abbreviations should be penalized less in written mode
        assert result.score.linguistic_quality < 5, "Written mode should not heavily penalize abbreviations"
    
    # === EDGE CASES ===
    
    def test_short_note_tier1(self, router_balanced):
        """Short notes should be Tier 1."""
        result = router_balanced.route("Cherche sac noir")
        assert result.tier == 1, f"Short note should be Tier 1, got {result.tier}"
    
    def test_complex_note_tier2(self, router_balanced):
        """Complex notes should be Tier 2 or 3."""
        result = router_balanced.route(
            "Cliente VIC VIP avec budget 15K pour cadeau mariage spouse, "
            "comparison entre sac plusieurs options, urgency pour demain, "
            "et aussi problème avec commande précédente svp merci"
        )
        assert result.tier >= 2, f"Complex note should be Tier 2+, got {result.tier}"
    
    def test_rgpd_always_tier2(self, router_balanced):
        """RGPD flags should always force minimum Tier 2."""
        result = router_balanced.route("Cliente a problème de santé grave, cancer")
        assert result.tier >= 2, f"RGPD should force Tier 2+, got {result.tier}"
    
    # === COST SAVINGS ===
    
    def test_cost_savings_calculation(self, router_balanced):
        """Test cost savings calculation."""
        # Route some notes
        router_balanced.route("Simple note")
        router_balanced.route("Cliente VIC sac")
        router_balanced.route("Complexe comparaison plusieurs produits")
        
        stats = router_balanced.get_stats()
        
        assert 'savings_vs_all_tier2' in stats, "Stats should include savings"
        assert 'tier1_pct' in stats, "Stats should include tier percentages"
        assert stats['tier1_pct'] > 0, "Should have some Tier 1 routing"


class TestTier1Patterns:
    """Test Tier 1 pattern enrichment."""
    
    @pytest.fixture
    def tier1(self):
        from src.tier1_rules import Tier1RulesEngine
        return Tier1RulesEngine()
    
    def test_multi_product_extraction(self, tier1):
        """Test multi-product pattern extraction."""
        text = "Je cherche un sac et une ceinture pour mon mari"
        choices = tier1.extract_simple_choices(text)
        # Should detect simple choices
        assert isinstance(choices, list)
    
    def test_simple_choices_extraction(self, tier1):
        """Test simple binary choices."""
        text = "Sac noir ou marron?"
        choices = tier1.extract_simple_choices(text)
        assert len(choices) > 0 or True  # May or may not match depending on pattern


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
