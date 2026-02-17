"""
LVMH Schema and Examples for LangExtract

4-Pillar Taxonomy:
1. PRODUIT (marque, catégorie, budget, style)
2. PROFIL CLIENT (statut VIC, contexte achat)
3. HOSPITALITÉ (occasion, préférences)
4. ACTION BUSINESS (next step, urgence)
"""

import textwrap
import langextract as lx

LVMH_PROMPT = textwrap.dedent("""
    Extraire les informations LVMH des notes Client Advisor selon 4 piliers:
    
    1. PRODUIT: Marque, catégorie (sac, montre, parfum, etc.), budget, style
    2. PROFIL CLIENT: Statut (VIC, fidèle, nouveau), contexte d'achat
    3. HOSPITALITÉ: Occasion (anniversaire, mariage, événement), préférences, contraintes
    4. ACTION BUSINESS: Prochaine étape, niveau d'urgence, type d'action
    
    Règles:
    - Utiliser le texte exact (pas de paraphrase)
    - Extraire tous les attributs pertinents
    - Ordre d'apparition dans le texte
    - Pas d'hallucination
""")

LVMH_EXAMPLES = [
    # Example 1: VIC customer with specific product
    lx.data.ExampleData(
        text="Mme Dupont cliente VIC cherche sac Hermès budget 8000€ anniversaire mari.",
        extractions=[
            lx.data.Extraction(
                extraction_class="profil_client",
                extraction_text="cliente VIC",
                attributes={"statut": "VIC"}
            ),
            lx.data.Extraction(
                extraction_class="produit",
                extraction_text="sac Hermès budget 8000€",
                attributes={"marque": "Hermès", "categorie": "sac", "budget": "8000€"}
            ),
            lx.data.Extraction(
                extraction_class="hospitalite",
                extraction_text="anniversaire mari",
                attributes={"occasion": "anniversaire"}
            )
        ]
    ),
    # Example 2: Loyal customer with watch interest
    lx.data.ExampleData(
        text="Monsieur Martin client fidèle souhaite vedere orologio Rolex pour suo compleanno.",
        extractions=[
            lx.data.Extraction(
                extraction_class="profil_client",
                extraction_text="client fidèle",
                attributes={"statut": "fidèle"}
            ),
            lx.data.Extraction(
                extraction_class="produit",
                extraction_text="orologio Rolex",
                attributes={"marque": "Rolex", "categorie": "montre", "langue": "IT"}
            ),
            lx.data.Extraction(
                extraction_class="hospitalite",
                extraction_text="suo compleanno",
                attributes={"occasion": "anniversaire"}
            )
        ]
    ),
    # Example 3: New customer with gift intent
    lx.data.ExampleData(
        text="Nouvelle cliente interested in a Chanel bag around 5000€ for her wedding anniversary.",
        extractions=[
            lx.data.Extraction(
                extraction_class="profil_client",
                extraction_text="Nouvelle cliente",
                attributes={"statut": "nouveau", "langue": "EN"}
            ),
            lx.data.Extraction(
                extraction_class="produit",
                extraction_text="Chanel bag around 5000€",
                attributes={"marque": "Chanel", "categorie": "sac", "budget": "5000€"}
            ),
            lx.data.Extraction(
                extraction_class="hospitalite",
                extraction_text="wedding anniversary",
                attributes={"occasion": "anniversaire mariage"}
            )
        ]
    ),
    # Example 4: With business action
    lx.data.ExampleData(
        text="Mme Bernard veut sac Louis Vuitton urgently pour événement ce weekend. Rappeler demain.",
        extractions=[
            lx.data.Extraction(
                extraction_class="produit",
                extraction_text="sac Louis Vuitton",
                attributes={"marque": "Louis Vuitton", "categorie": "sac"}
            ),
            lx.data.Extraction(
                extraction_class="hospitalite",
                extraction_text="événement ce weekend",
                attributes={"occasion": "événement"}
            ),
            lx.data.Extraction(
                extraction_class="action_business",
                extraction_text="Rappeler demain",
                attributes={"type_action": "rappel", "urgence": "haute"}
            )
        ]
    ),
]


def get_lvmh_prompt():
    """Get LVMH extraction prompt."""
    return LVMH_PROMPT


def get_lvmh_examples():
    """Get LVMH few-shot examples."""
    return LVMH_EXAMPLES
