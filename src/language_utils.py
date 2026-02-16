"""
Language detection utilities.
"""

import re
from typing import Optional


def detect_language(text: str) -> str:
    """
    Simple language detection based on common patterns.
    Returns language code: 'en', 'fr', 'es', 'de', 'it', etc.
    """
    if not text:
        return 'en'
    
    # French patterns
    french_patterns = [
        r'\b(le|la|les|un|une|des|et|est|que|qui|dans|pour|avec|sur|ce|cette|pas|vous|nous|ils|elles|avec|sans|voir|faire|être|avoir|mon|ton|son|notre|votre|leur)\b',
        r'[éèêëàâäùûüôöîï]',
    ]
    
    # Spanish patterns
    spanish_patterns = [
        r'\b(el|la|los|las|un|una|unos|unas|y|es|que|como|para|con|sin|ver|hacer|ser|estar|tener|mi|tu|su|nuestro|vuestro|su|lo|que)\b',
        r'[áéíóúüñ]',
    ]
    
    # German patterns
    german_patterns = [
        r'\b(der|die|das|ein|eine|und|ist|zu|mit|von|auf|für|ist|nicht|sich|sein|haben|werden|werden|aus|auch|es|ich|du|er|sie|wir|ihr)\b',
        r'[äöüß]',
    ]
    
    # Italian patterns
    italian_patterns = [
        r'\b(il|la|lo|gli|le|un|una|di|da|in|con|per|tra|fratello|sorella|padre|madre|figlio|figlia|che|come|pero|non|sono|essere|avere|fare|vedere|voi|noi|loro)\b',
        r'[àèéìíòóù]',
    ]
    
    text_lower = text.lower()
    
    french_count = sum(1 for p in french_patterns if re.search(p, text_lower))
    spanish_count = sum(1 for p in spanish_patterns if re.search(p, text_lower))
    german_count = sum(1 for p in german_patterns if re.search(p, text_lower))
    italian_count = sum(1 for p in italian_patterns if re.search(p, text_lower))
    
    counts = {
        'fr': french_count,
        'es': spanish_count,
        'de': german_count,
        'it': italian_count,
    }
    
    max_lang = max(counts, key=counts.get)
    if counts[max_lang] >= 1:
        return max_lang
    
    return 'en'  # Default to English


def is_french(text: str) -> bool:
    """Check if text is primarily French."""
    return detect_language(text) == 'fr'


def is_spanish(text: str) -> bool:
    """Check if text is primarily Spanish."""
    return detect_language(text) == 'es'


def is_german(text: str) -> bool:
    """Check if text is primarily German."""
    return detect_language(text) == 'de'


def is_italian(text: str) -> bool:
    """Check if text is primarily Italian."""
    return detect_language(text) == 'it'
