"""
Unit tests for MultilingualTextCleaner.
"""

import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.text_cleaner import MultilingualTextCleaner


@pytest.fixture
def cleaner():
    return MultilingualTextCleaner()


class TestFrenchCleaning:
    
    def test_removes_hesitations(self, cleaner):
        text = "Mme Martin, euh, 45 ans, cherche sac, hum, budget 5K."
        result = cleaner.clean_text(text, 'FR')
        
        assert "euh" not in result['cleaned'].lower()
        assert "hum" not in result['cleaned'].lower()
        assert "Mme [NAME]" in result['cleaned']
        assert "Martin" not in result['cleaned']
        assert "45 ans" in result['cleaned']
        assert "5K" in result['cleaned']
    
    def test_removes_redundant_expressions(self, cleaner):
        text = "Elle cherche, tu sais, un sac, en quelque sorte, élégant, voilà."
        result = cleaner.clean_text(text, 'FR')
        
        assert "tu sais" not in result['cleaned'].lower()
        assert "en quelque sorte" not in result['cleaned'].lower()
        assert "voilà" not in result['cleaned'].lower()
    
    def test_preserves_content(self, cleaner):
        text = "Cliente VIC, euh, cherche Capucines, tu sais, budget 10K, quoi."
        result = cleaner.clean_text(text, 'FR')
        
        assert "Cliente VIC" in result['cleaned']
        assert "Capucines" in result['cleaned']
        assert "budget 10K" in result['cleaned']
    
    def test_compression_rate(self, cleaner):
        # Heavy filler text
        text = "Euh, donc, elle cherche, tu sais, en fait, du coup, un sac, voilà, quoi, bref."
        result = cleaner.clean_text(text, 'FR')
        
        assert result['fillers_removed'] >= 5
        assert result['compression_ratio'] < 0.6  # At least 40% reduction


class TestEnglishCleaning:
    
    def test_removes_hesitations(self, cleaner):
        text = "He, uh, collects art, um, you know, basically."
        result = cleaner.clean_text(text, 'EN')
        
        assert "uh" not in result['cleaned'].lower()
        assert "um" not in result['cleaned'].lower()
    
    def test_removes_filler_phrases(self, cleaner):
        text = "She, you know, likes bags, sort of, kind of, actually."
        result = cleaner.clean_text(text, 'EN')
        
        assert "you know" not in result['cleaned'].lower()
        assert "sort of" not in result['cleaned'].lower()
        assert "kind of" not in result['cleaned'].lower()


class TestItalianCleaning:
    
    def test_removes_italian_fillers(self, cleaner):
        text = "Lei, tipo, colleziona arte, diciamo, praticamente, bellissimo."
        result = cleaner.clean_text(text, 'IT')
        
        assert "tipo" not in result['cleaned'].lower()
        assert "diciamo" not in result['cleaned'].lower()
        assert "praticamente" not in result['cleaned'].lower()


class TestSpanishCleaning:
    
    def test_removes_spanish_fillers(self, cleaner):
        text = "Ella, ya sabes, colecciona arte, digamos que, pues, bueno."
        result = cleaner.clean_text(text, 'ES')
        
        assert "ya sabes" not in result['cleaned'].lower()
        assert "digamos que" not in result['cleaned'].lower()
        assert "pues" not in result['cleaned'].lower()


class TestGermanCleaning:
    
    def test_removes_german_fillers(self, cleaner):
        text = "Sie, äh, sammelt Kunst, sozusagen, irgendwie, genau."
        result = cleaner.clean_text(text, 'DE')
        
        assert "äh" not in result['cleaned'].lower()
        assert "sozusagen" not in result['cleaned'].lower()
        assert "irgendwie" not in result['cleaned'].lower()


class TestMultilingualCompression:
    
    def test_all_languages_compress(self, cleaner):
        test_cases = {
            'FR': "Mme X, euh, tu sais, en fait, du coup, cherche sac, voilà.",
            'EN': "He, you know, sort of, like, basically, collects art.",
            'IT': "Lei, tipo, diciamo, praticamente, colleziona arte.",
            'ES': "Ella, ya sabes, digamos que, pues, colecciona arte.",
            'DE': "Sie, äh, sozusagen, irgendwie, sammelt Kunst."
        }
        
        for lang, text in test_cases.items():
            result = cleaner.clean_text(text, lang)
            assert result['compression_ratio'] < 0.8, f"{lang} should compress at least 20%"
            assert result['fillers_removed'] >= 2, f"{lang} should remove at least 2 fillers"


class TestEdgeCases:
    
    def test_empty_text(self, cleaner):
        result = cleaner.clean_text("", 'FR')
        assert result['cleaned'] == ""
        assert result['fillers_removed'] == 0
    
    def test_none_text(self, cleaner):
        result = cleaner.clean_text(None, 'FR')
        assert result['cleaned'] == ""
    
    def test_unknown_language(self, cleaner):
        text = "Some text with no cleaning"
        result = cleaner.clean_text(text, 'XX')
        assert result['cleaned'] == text
        assert result['compression_ratio'] == 1.0
    
    def test_no_fillers(self, cleaner):
        text = "Cliente cherche sac cuir noir budget 5000 euros."
        result = cleaner.clean_text(text, 'FR')
        assert result['fillers_removed'] == 0
        assert result['compression_ratio'] > 0.95


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
