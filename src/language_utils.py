"""
Lightweight language detection helpers.
Supports FR, EN, IT, ES, DE and falls back to FR.
"""

import re

SUPPORTED_LANGUAGES = ("FR", "EN", "IT", "ES", "DE")

KEYWORDS = {
    "FR": {"bonjour", "merci", "cadeau", "anniversaire", "client", "sac", "budget", "bonjour"},
    "EN": {"hello", "thanks", "gift", "birthday", "client", "bag", "budget", "please"},
    "IT": {"ciao", "grazie", "regalo", "compleanno", "cliente", "borsa", "budget"},
    "ES": {"hola", "gracias", "regalo", "cumpleaños", "cliente", "bolso", "presupuesto"},
    "DE": {"hallo", "danke", "geschenk", "geburtstag", "kunde", "tasche", "budget"},
}


def detect_language(text: str, fallback: str = "FR") -> str:
    sample = (text or "").lower().strip()
    if not sample:
        return fallback

    tokens = set(re.findall(r"[a-zA-ZÀ-ÿ']+", sample))
    scores = {lang: 0 for lang in SUPPORTED_LANGUAGES}
    for lang, lang_keywords in KEYWORDS.items():
        scores[lang] = len(tokens & lang_keywords)

    best_lang = max(scores, key=scores.get)
    if scores[best_lang] == 0:
        return fallback
    return best_lang
