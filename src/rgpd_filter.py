"""
RGPD Filter for LVMH Voice Notes.
Detects and anonymizes sensitive personal data before extraction.
Uses LLM for contextual detection of GDPR-sensitive information.
"""

import json
import os
import re
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

# Lazy import to avoid Cloud Run startup timeout
OpenAI = None

def _get_openai_client():
    global OpenAI
    if OpenAI is None:
        from openai import OpenAI
    return OpenAI


logger = logging.getLogger(__name__)


# RGPD Categories (Article 9 - Special Categories)
RGPD_CATEGORIES = {
    'health_mental': 'Mental health conditions (depression, burnout, anxiety, etc.)',
    'health_physical': 'Physical health conditions (diseases, disabilities)',
    'family_conflict': 'Family conflicts (divorce disputes, custody, etc.)',
    'religion': 'Religious beliefs or practices',
    'political': 'Political opinions',
    'sexual_orientation': 'Sexual orientation or life',
    'ethnic_origin': 'Racial or ethnic origin',
    'biometric': 'Biometric data for identification',
    'genetic': 'Genetic data'
}


class RGPDFilter:
    """RGPD-compliant filter for sensitive data detection and anonymization."""
    
    SYSTEM_PROMPT = """Tu es un expert RGPD/GDPR pour LVMH.
Ton rôle est de détecter les données sensibles (Article 9 RGPD) dans les notes clients.

CATÉGORIES SENSIBLES À DÉTECTER:
- health_mental: Santé mentale (dépression, burnout, anxiété, stress pathologique)
- health_physical: Santé physique (maladies, handicaps) - SAUF allergies alimentaires/matériaux
- family_conflict: Conflits familiaux (divorce contentieux, garde d'enfants)
- religion: Croyances religieuses
- political: Opinions politiques
- sexual_orientation: Orientation sexuelle
- ethnic_origin: Origine ethnique (sauf si contexte culturel neutre)

IMPORTANT:
- Les allergies alimentaires (gluten, lactose, noix) sont OK pour le business
- Les allergies matériaux (nickel, latex) sont OK pour le business
- "Divorcé(e)" seul n'est PAS sensible, seulement si contexte conflictuel
- Régime alimentaire (vegan, végétarien) n'est PAS sensible
- Profession n'est PAS sensible

RÉPONDS EN JSON:
{
    "contains_sensitive": true/false,
    "categories_detected": ["category1", "category2"],
    "sensitive_spans": [{"text": "...", "category": "...", "severity": "low/medium/high"}],
    "safe_to_store": true/false,
    "reasoning": "Brief explanation"
}"""
    
    def __init__(self, model: str = 'gpt-4o-mini'):
        self.model = model
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")
        self.client = _get_openai_client()(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def detect_sensitive_data(self, text: str, language: str) -> Dict:
        """Detect sensitive RGPD data in text with retry logic."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "language": language,
                                "text_to_analyze": text,
                                "task": "Detect sensitive RGPD/GDPR data categories in this note.",
                                "output_format": "json_object",
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result['api_response'] = response
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            return {
                'contains_sensitive': False,
                'categories_detected': [],
                'sensitive_spans': [],
                'safe_to_store': True,
                'reasoning': 'ERROR: Invalid LLM response',
                'error': str(e)
            }
    
    def anonymize_text(self, text: str, sensitive_spans: List[Dict]) -> str:
        """Replace sensitive spans with anonymized placeholders."""
        anonymized = text
        
        # Sort by position (longest first to avoid index issues)
        for span in sorted(sensitive_spans, key=lambda x: len(x.get('text', '')), reverse=True):
            original = span.get('text', '')
            category = span.get('category', 'sensitive')
            if original:
                placeholder = f"[RGPD_{category.upper()}_REDACTED]"
                anonymized = anonymized.replace(original, placeholder)
        
        return anonymized
    
    def process_note(self, note: Dict, cost_tracker=None) -> Dict:
        """Full RGPD processing pipeline for a note."""
        text = note.get('Transcription', '')
        language = note.get('Language', 'FR')
        
        # Detect
        detection = self.detect_sensitive_data(text, language)
        
        # Track cost if tracker provided
        if cost_tracker and 'api_response' in detection:
            cost_tracker.track_call(detection['api_response'], step='rgpd')
            del detection['api_response']
        
        # Anonymize if needed
        if detection.get('contains_sensitive', False):
            anonymized_text = self.anonymize_text(text, detection.get('sensitive_spans', []))
        else:
            anonymized_text = text
        
        return {
            'ID': note.get('ID'),
            'original_text': text,
            'anonymized_text': anonymized_text,
            'rgpd_result': detection,
            'contains_sensitive': detection.get('contains_sensitive', False),
            'categories_detected': detection.get('categories_detected', []),
            'safe_to_store': detection.get('safe_to_store', True)
        }
    
    def generate_report(self, results: List[Dict]) -> Dict:
        """Generate RGPD compliance report."""
        total = len(results)
        sensitive_count = sum(1 for r in results if r.get('contains_sensitive', False))
        
        categories_count = {}
        for r in results:
            for cat in r.get('categories_detected', []):
                categories_count[cat] = categories_count.get(cat, 0) + 1
        
        return {
            'total_notes': total,
            'notes_with_sensitive_data': sensitive_count,
            'percentage_sensitive': sensitive_count / total * 100 if total > 0 else 0,
            'categories_breakdown': categories_count,
            'compliance_status': 'COMPLIANT' if sensitive_count == 0 else 'REQUIRES_REVIEW'
        }


if __name__ == "__main__":
    # Test with sample text
    filter = RGPDFilter()
    
    test_cases = [
        {
            'ID': 'TEST_001',
            'Transcription': "Client en burnout depuis 6 mois, divorce difficile en cours.",
            'Language': 'FR'
        },
        {
            'ID': 'TEST_002',
            'Transcription': "Cliente allergie nickel, végétarienne, pratique yoga.",
            'Language': 'FR'
        }
    ]
    
    for test in test_cases:
        result = filter.process_note(test)
        print(f"\n{'='*50}")
        print(f"ID: {result['ID']}")
        print(f"Contains Sensitive: {result['contains_sensitive']}")
        print(f"Categories: {result['categories_detected']}")
        print(f"Safe to Store: {result['safe_to_store']}")
