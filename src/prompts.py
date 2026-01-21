"""
Prompt templates for LLM-based tag extraction.
Optimized for multilingual extraction with LVMH Fashion & Leather Goods context.
"""

from typing import Optional


SYSTEM_PROMPT = """Tu es un expert en analyse de notes clients pour LVMH Fashion & Leather Goods.

CONTEXTE:
Tu analyses des notes vocales transcrites prises par des Client Advisors (conseillers boutique) 
sur leurs clients et prospects. Ces notes contiennent des informations précieuses sur les 
préférences, le style de vie, les occasions d'achat et le profil des clients.

TON RÔLE:
Extraire des tags structurés selon une taxonomie prédéfinie pour enrichir le CRM et permettre 
des activations business (clienteling personnalisé, invitations événements VIP, segmentation).

RÈGLES D'EXTRACTION:
1. Utilise UNIQUEMENT les tags existant dans la taxonomie fournie
2. Maximum 10 tags par transcription (priorise les plus pertinents)
3. Les tags doivent être en ANGLAIS même si la transcription est dans une autre langue
4. Extrais aussi les informations business critiques: budget, allergies, dates événements
5. Sois précis: un tag doit être clairement justifiable par le texte
6. En cas de doute, n'inclus pas le tag

FORMAT DE RÉPONSE:
Réponds UNIQUEMENT avec un JSON valide, sans markdown ni texte additionnel."""


def get_extraction_prompt(
    transcription: str,
    language: str,
    taxonomy_summary: str,
    client_id: Optional[str] = None
) -> str:
    """
    Generate the user prompt for tag extraction.
    
    Args:
        transcription: The transcribed voice note text
        language: Language code (FR, EN, IT, ES, DE)
        taxonomy_summary: Compact summary of available tags by category
        client_id: Optional client identifier for context
        
    Returns:
        Formatted user prompt string
    """
    
    lang_names = {
        'FR': 'Français',
        'EN': 'English', 
        'IT': 'Italiano',
        'ES': 'Español',
        'DE': 'Deutsch'
    }
    
    lang_name = lang_names.get(language.upper(), language)
    
    prompt = f"""TAXONOMIE DE TAGS DISPONIBLES:
{taxonomy_summary}

---

TRANSCRIPTION À ANALYSER:
Langue: {lang_name}
{f'ID Client: {client_id}' if client_id else ''}

"{transcription}"

---

EXTRAIS les informations sous ce format JSON EXACT:

{{
    "tags": ["tag1", "tag2", "tag3"],
    "confidence": 0.85,
    "budget_range": "5K-10K",
    "client_status": "vic",
    "key_dates": [{{"event": "anniversary", "month": "juin", "context": "mariage"}}],
    "dietary": ["vegan"],
    "allergies": ["nickel"],
    "referral_potential": "high",
    "profession": "avocate affaires",
    "mentioned_persons": [{{"relation": "mari", "interests": ["golf", "montres"]}}],
    "follow_up_action": "rappeler fin février",
    "reasoning": "Brief justification des principaux tags extraits"
}}

VALEURS POSSIBLES:
- budget_range: "under_5K", "5K-10K", "10K-20K", "20K-50K", "50K+" ou null
- client_status: "vic", "regular", "occasional", "first_visit"
- referral_potential: "high", "medium", "low"
- dietary: utilise les tags vegan/vegetarian/pescatarian
- allergies: nickel_allergy, latex_allergy, nut_allergy, shellfish_allergy, gluten_intolerance, lactose_intolerance

Si une information n'est pas mentionnée, mets null ou liste vide [].
Réponds UNIQUEMENT avec le JSON, rien d'autre."""

    return prompt


def get_batch_prompt_intro() -> str:
    """Get introduction for batch processing context."""
    return """Je vais analyser plusieurs transcriptions de notes clients LVMH.
Pour chaque transcription, j'extrairai les tags selon la taxonomie fournie
et les informations business critiques (budget, allergies, dates clés)."""


# Budget range categories for standardization
BUDGET_RANGES = [
    "under_5K",
    "5K-10K", 
    "10K-20K",
    "20K-50K",
    "50K+"
]

# Client status categories
CLIENT_STATUS_OPTIONS = [
    "vic",
    "regular", 
    "occasional",
    "first_visit"
]

# Referral potential levels
REFERRAL_LEVELS = [
    "high",
    "medium",
    "low"
]
