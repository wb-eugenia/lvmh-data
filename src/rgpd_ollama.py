"""
RGPD Filter with Ollama (Local LLM).
Uses Qwen 2.5 7B for contextual RGPD detection - FREE processing.
"""

import json
import re
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class RGPDResult:
    """Result from RGPD detection."""
    contains_sensitive: bool
    categories_detected: List[str]
    sensitive_spans: List[Dict]
    safe_to_store: bool
    severity: str  # 'none', 'low', 'medium', 'high'
    reasoning: str
    anonymized_text: Optional[str] = None


class RGPDOllamaFilter:
    """
    RGPD-compliant filter using local Ollama (Qwen 2.5 7B).
    Cost: 0€ | Speed: ~2-3s/note
    """
    
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "qwen2.5:7b"
    
    SYSTEM_PROMPT = """Tu es un expert RGPD/GDPR pour LVMH.
Analyse le texte et détecte les données sensibles (Article 9 RGPD).

CATÉGORIES SENSIBLES:
- health_mental: Santé mentale (dépression, burnout, anxiété sévère, suicide)
- health_physical: Maladies graves (cancer, handicap) - PAS allergies/régimes
- family_conflict: Divorce contentieux, garde d'enfants
- religion: Croyances religieuses explicites
- political: Opinions politiques explicites
- sexual_orientation: Orientation sexuelle

NON-SENSIBLE (OK pour business):
- Allergies alimentaires (gluten, lactose, noix)
- Allergies matériaux (nickel, latex)
- Régimes alimentaires (vegan, végétarien)
- "Divorcé" sans contexte conflictuel
- Profession, âge, préférences shopping

RÉPONDS EN JSON:
{
    "contains_sensitive": true/false,
    "categories_detected": ["category1"],
    "sensitive_spans": [{"text": "...", "category": "...", "severity": "low/medium/high"}],
    "safe_to_store": true/false,
    "severity": "none/low/medium/high",
    "reasoning": "Brief explanation"
}"""

    def __init__(self, model: str = None):
        self.model = model or self.MODEL
        self.stats = {'processed': 0, 'sensitive': 0, 'clean': 0}
        self._check_ollama()
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                print(f"✅ RGPD Ollama ready with {self.model}")
                return True
            return False
        except:
            print("⚠️ Ollama not running for RGPD")
            return False
    
    def _call_ollama(self, text: str, language: str) -> Optional[Dict]:
        """Call Ollama API for RGPD detection."""
        try:
            prompt = f"""Langue: {language}

Texte à analyser:
"{text}"

Analyse RGPD (JSON):"""
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": self.SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 400,
                }
            }
            
            response = requests.post(self.OLLAMA_URL, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                text_response = result.get('response', '')
                return self._parse_json(text_response)
            return None
            
        except Exception as e:
            print(f"RGPD Ollama error: {e}")
            return None
    
    def _parse_json(self, text: str) -> Optional[Dict]:
        """Parse JSON from LLM response."""
        try:
            return json.loads(text)
        except:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
        return None
    
    def detect(self, text: str, language: str = 'FR') -> RGPDResult:
        """Detect RGPD-sensitive data in text."""
        self.stats['processed'] += 1
        
        result = self._call_ollama(text, language)
        
        if result:
            contains = result.get('contains_sensitive', False)
            if contains:
                self.stats['sensitive'] += 1
            else:
                self.stats['clean'] += 1
            
            return RGPDResult(
                contains_sensitive=contains,
                categories_detected=result.get('categories_detected', []),
                sensitive_spans=result.get('sensitive_spans', []),
                safe_to_store=result.get('safe_to_store', True),
                severity=result.get('severity', 'none'),
                reasoning=result.get('reasoning', '')
            )
        else:
            self.stats['clean'] += 1
            return RGPDResult(
                contains_sensitive=False,
                categories_detected=[],
                sensitive_spans=[],
                safe_to_store=True,
                severity='none',
                reasoning='RGPD check failed, assuming clean'
            )
    
    def anonymize(self, text: str, spans: List[Dict]) -> str:
        """Anonymize sensitive spans in text."""
        anonymized = text
        for span in sorted(spans, key=lambda x: len(x.get('text', '')), reverse=True):
            original = span.get('text', '')
            category = span.get('category', 'sensitive')
            if original:
                placeholder = f"[RGPD_{category.upper()}]"
                anonymized = anonymized.replace(original, placeholder)
        return anonymized
    
    def process_note(self, text: str, language: str = 'FR') -> Dict:
        """Full RGPD processing with optional anonymization."""
        result = self.detect(text, language)
        
        output = {
            'contains_sensitive': result.contains_sensitive,
            'categories_detected': result.categories_detected,
            'severity': result.severity,
            'safe_to_store': result.safe_to_store,
            'reasoning': result.reasoning,
        }
        
        if result.contains_sensitive and result.sensitive_spans:
            output['anonymized_text'] = self.anonymize(text, result.sensitive_spans)
            output['sensitive_spans'] = result.sensitive_spans
        
        return output
    
    def report(self) -> str:
        """Generate stats report."""
        total = self.stats['processed']
        if total == 0:
            return "No notes processed"
        
        return f"""
🔒 RGPD OLLAMA STATS
{'='*40}
Processed:  {total}
Sensitive:  {self.stats['sensitive']} ({self.stats['sensitive']/total*100:.1f}%)
Clean:      {self.stats['clean']} ({self.stats['clean']/total*100:.1f}%)
"""


if __name__ == "__main__":
    import pandas as pd
    
    print("🔒 Testing RGPD Ollama Filter (Qwen 2.5 7B)\n")
    
    filter = RGPDOllamaFilter()
    
    test_cases = [
        ("Cliente végétarienne, allergie nickel, cherche sac cuir.", "FR"),
        ("Client en burnout depuis 6 mois, divorce contentieux.", "FR"),
        ("Mme Martin, divorcée, cherche cadeau pour ses enfants.", "FR"),
        ("VIP client mentions he's gay and looking for a gift.", "EN"),
        ("Doctor, first visit, looking for leather bag, budget 5K.", "EN"),
    ]
    
    for text, lang in test_cases:
        print(f"\n{'='*60}")
        print(f"Text: {text}")
        print(f"{'='*60}")
        
        result = filter.process_note(text, lang)
        
        print(f"Sensitive: {result['contains_sensitive']}")
        print(f"Categories: {result['categories_detected']}")
        print(f"Severity: {result['severity']}")
        print(f"Reasoning: {result['reasoning']}")
    
    print(filter.report())
