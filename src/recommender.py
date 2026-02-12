"""
Next Best Action Recommender Engine.
Transforms extracted tags and context into actionable business suggestions.
"""

import re
from typing import List, Dict, Optional, Any
from src.models import ExtractionResult, Pilier4Business, NextBestAction
import logging

logger = logging.getLogger(__name__)

class RecommenderEngine:
    """
    Engine that generates business recommendations based on extracted pillars.
    """
    
    def __init__(self):
        # Could load business rules from a JSON config eventually
        pass
    
    def generate_recommendation(self, extraction: ExtractionResult, source_text: Optional[str] = None) -> ExtractionResult:
        """
        Processes an extraction result and populates the next_best_action field.
        """
        # Lightweight deterministic enrichment to reduce missing critical fields
        # when LLM outputs are partial (timeouts/rate-limit/degraded answers).
        self._enrich_from_text(extraction, source_text or "")

        p1 = extraction.pilier_1_univers_produit
        p2 = extraction.pilier_2_profil_client
        p3 = extraction.pilier_3_hospitalite_care
        p4 = extraction.pilier_4_action_business
        
        # 1. Detect Occasions (High Priority)
        occasion = p3.occasion
        urgency = p4.urgency
        budget = p4.budget_potential
        status = p2.purchase_context.behavior or "client"
        
        action = None
        
        # Match products from RAG if available
        products = [p.get('name', 'N/A') for p in p1.matched_products]
        top_product = products[0] if products else None
        
        # --- RULE 1: Birthdays/Anniversaries ---
        if occasion in ['birthday', 'birthday_gift', 'wedding_anniversary']:
            priority = "High" if urgency in ['urgent', 'today', 'this_week'] else "Medium"
            desc = f"Contacte le {status} pour son {occasion.replace('_', ' ')}. "
            if top_product:
                desc += f"Suggère le {top_product} qui correspond à ses goûts."
            else:
                desc += "Propose une sélection de nouveautés."
            
            action = NextBestAction(
                action_type="gift_suggestion",
                description=desc,
                priority=priority,
                target_products=products[:2],
                deadline=urgency
            )
            
        # --- RULE 2: VIC Service Passage ---
        elif "luxury_service" in p1.categories and status in ['vic', 'ultimate']:
            action = NextBestAction(
                action_type="invitation",
                description=f"Le client {status.upper()} est passé pour un service. Invite-le à découvrir la nouvelle collection en salon privé.",
                priority="High",
                target_products=["new_collection"]
            )
            
        # --- RULE 3: New Lead Exploration ---
        elif status == 'first_visit' or not status:
            desc = "Envoie un mot de remerciement post-visite. "
            if top_product:
                desc += f"Relance sur le {top_product}."
            
            action = NextBestAction(
                action_type="follow_up",
                description=desc,
                priority="Medium",
                target_products=products[:1]
            )
            
        # --- RULE 4: Specific Product Intent ---
        elif p1.categories and not action:
            desc = f"Relance le client sur ses favoris: {', '.join(p1.categories[:2])}. "
            if budget:
                desc += f"Budget estimé: {budget}."
                
            action = NextBestAction(
                action_type="follow_up",
                description=desc,
                priority="Medium",
                target_products=products[:2]
            )

        # Inject recommendation if found
        if action:
            p4.next_best_action = action
            
        # --- GAMIFICATION (Super Note Score) ---
        self._calculate_gamification(extraction, source_text=source_text)
            
        return extraction

    def _append_unique(self, values: List[str], value: str) -> None:
        if not value:
            return
        normalized = value.strip()
        if not normalized:
            return
        lower_existing = {v.lower() for v in values if isinstance(v, str)}
        if normalized.lower() in lower_existing:
            return
        values.append(normalized)

    def _contains_any_pattern(self, text: str, patterns: List[str]) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _enrich_from_text(self, extraction: ExtractionResult, source_text: str) -> None:
        text = source_text or ""
        lower = text.lower()

        p1 = extraction.pilier_1_univers_produit
        p2 = extraction.pilier_2_profil_client
        p3 = extraction.pilier_3_hospitalite_care

        # ---- Purchase context enrichment ----
        if not (p2.purchase_context.type or "").strip():
            if self._contains_any_pattern(
                lower,
                [
                    r"\bgift\b", r"\bcadeau\b", r"\bregal[oi]\b", r"\bgeschenk\b",
                    r"\bcompleanno\b", r"\bcumplea", r"\banniversaire\b",
                    r"\bwedding\b", r"\bmariage\b", r"\bboda\b",
                ],
            ):
                p2.purchase_context.type = "Gift"
            elif self._contains_any_pattern(
                lower,
                [
                    r"\bfor himself\b", r"\bfor herself\b", r"\bpour (lui|elle)\b",
                    r"\bpour moi\b", r"\bself\b", r"\bpersonal use\b",
                ],
            ):
                p2.purchase_context.type = "Self"

        if not (p2.purchase_context.behavior or "").strip():
            if self._contains_any_pattern(lower, [r"\b(vic|vip|ultimate|platinum)\b"]):
                p2.purchase_context.behavior = "vic"
            elif self._contains_any_pattern(
                lower,
                [
                    r"\b(first visit|first[-\s]?time|new client)\b",
                    r"\bpremi[eè]re visite\b",
                    r"\bprimera visita\b",
                    r"\bprimo cliente\b",
                    r"\bneuer kunde\b",
                    r"\bnouveau client\b",
                ],
            ):
                p2.purchase_context.behavior = "first_visit"
            elif self._contains_any_pattern(
                lower,
                [
                    r"\bregular client\b", r"\bclient r[eé]gulier\b",
                    r"\bcliente regular\b", r"\bcliente occasionale\b",
                    r"\blong[-\s]?time client\b",
                ],
            ):
                p2.purchase_context.behavior = "regular"

        # ---- Profession enrichment ----
        if not (p2.profession.sector or "").strip():
            sector_patterns = {
                "healthcare": [r"\bdoctor\b", r"\bdr\.\b", r"\bsurgeon\b", r"\bpsycholog"],
                "legal": [r"\blawyer\b", r"\bbarrister\b", r"\bavocat\b", r"\bdroit\b"],
                "media": [r"\bjournalist\b", r"\bjournaliste\b", r"\bvogue\b", r"\bpresse\b"],
                "sports": [r"\btennis\b", r"\bgolf\b", r"\bplayer\b", r"\bathlet"],
                "finance": [r"\bhedge fund\b", r"\banalyst\b", r"\binvest", r"\bcapital\b"],
                "business": [r"\bentrepreneur\b", r"\bfounder\b", r"\bceo\b", r"\bmanager\b"],
                "diplomacy": [r"\bdiplomat\b", r"\bonu\b", r"\bun\b", r"\bconsulat"],
                "aviation": [r"\bpilot\b", r"\bairline\b", r"\bstewardess\b"],
            }
            for sector, patterns in sector_patterns.items():
                if self._contains_any_pattern(lower, patterns):
                    p2.profession.sector = sector
                    break

        # ---- Usage enrichment ----
        if not p1.usage:
            usage_patterns = {
                "travel": [r"\btravel\b", r"\bvoyage\b", r"\btrip\b", r"\bcircuit\b", r"\btourn"],
                "professional": [r"\bwork\b", r"\bprofessional\b", r"\bbureau\b", r"\boffice\b", r"\bmeeting\b"],
                "daily": [r"\bdaily\b", r"\bquotidien\b", r"\beveryday\b"],
                "event": [r"\bevent\b", r"\bsoir[ée]e\b", r"\bgala\b"],
            }
            for usage_tag, patterns in usage_patterns.items():
                if self._contains_any_pattern(lower, patterns):
                    self._append_unique(p1.usage, usage_tag)

        # ---- Preferences enrichment ----
        color_map = {
            "black": [r"\bblack\b", r"\bnoir\b", r"\bnero\b", r"\bnegro\b", r"\bschwarz\b"],
            "white": [r"\bwhite\b", r"\bblanc\b", r"\bbianco\b", r"\bblanco\b", r"\bwei[ßs]\b"],
            "brown": [r"\bbrown\b", r"\bmarron\b", r"\bmar[ró]n\b", r"\bbraun\b"],
            "beige": [r"\bbeige\b"],
            "red": [r"\bred\b", r"\brouge\b", r"\brojo\b", r"\brot\b"],
            "blue": [r"\bblue\b", r"\bbleu\b", r"\bazul\b", r"\bblau\b"],
        }
        for color, patterns in color_map.items():
            if self._contains_any_pattern(lower, patterns):
                self._append_unique(p1.preferences.colors, color)

        material_map = {
            "leather": [r"\bleather\b", r"\bcuir\b", r"\bcuoio\b", r"\bpiel\b", r"\bleder\b"],
            "canvas": [r"\bcanvas\b", r"\btoile\b", r"\blona\b"],
            "metal": [r"\bmetal\b", r"\bm[ée]tal\b"],
        }
        for material, patterns in material_map.items():
            if self._contains_any_pattern(lower, patterns):
                self._append_unique(p1.preferences.materials, material)

        # ---- Occasion enrichment (multilingual) ----
        if not (p3.occasion or "").strip():
            occasion_patterns = {
                "birthday": [
                    r"\bbirthday\b", r"\banniversaire\b", r"\bcompleanno\b",
                    r"\bcumplea", r"\bgeburtstag\b",
                ],
                "wedding": [
                    r"\bwedding\b", r"\bmariage\b", r"\bmatrimonio\b", r"\bboda\b", r"\bhochzeit\b",
                ],
                "graduation": [
                    r"\bgraduat", r"\bdiplom", r"\blaurea\b", r"\babschluss\b",
                ],
                "housewarming": [
                    r"\bhousewarming\b", r"\bpendaison de cr[ée]maill", r"\beinweihung\b",
                ],
                "christmas": [r"\bchristmas\b", r"\bno[eë]l\b", r"\bnavidad\b", r"\bweihnacht"],
                "valentine": [r"\bvalentin", r"\bvalentine\b", r"\bsaint[-\s]?valentin"],
            }
            for occasion, patterns in occasion_patterns.items():
                if self._contains_any_pattern(lower, patterns):
                    p3.occasion = occasion
                    break

        # ---- Care / allergy enrichment ----
        if self._contains_any_pattern(lower, [r"\b(allerg|allergy|allergi|allergie)\w*"]):
            if self._contains_any_pattern(lower, [r"\bgluten\b", r"\bceliac", r"\bc[oœ]liaque"]):
                self._append_unique(p3.allergies.food, "gluten_allergy")
            if self._contains_any_pattern(lower, [r"\bnut\b", r"\bnoix\b", r"\barachid", r"\bpeanut"]):
                self._append_unique(p3.allergies.food, "nut_allergy")
            if self._contains_any_pattern(lower, [r"\blactose\b", r"\bdairy\b"]):
                self._append_unique(p3.allergies.food, "lactose_intolerance")
            if self._contains_any_pattern(lower, [r"\bnickel\b"]):
                self._append_unique(p3.allergies.contact, "nickel_allergy")
            if self._contains_any_pattern(lower, [r"\blatex\b"]):
                self._append_unique(p3.allergies.contact, "latex_allergy")
            if self._contains_any_pattern(lower, [r"\bfragrance\b", r"\bparfum\b"]):
                self._append_unique(p3.allergies.contact, "fragrance_sensitivity")
            if not p3.allergies.food and not p3.allergies.contact:
                self._append_unique(p3.values, "allergy_mentioned")

        if self._contains_any_pattern(lower, [r"\bvegan\b", r"\bv[ée]gan"]):
            self._append_unique(p3.diet, "vegan")
        if self._contains_any_pattern(lower, [r"\bvegetar", r"\bv[ée]g[eé]tar"]):
            self._append_unique(p3.diet, "vegetarian")
        if self._contains_any_pattern(lower, [r"\bhalal\b"]):
            self._append_unique(p3.diet, "halal")
        if self._contains_any_pattern(lower, [r"\bkosher\b", r"\bcasher\b"]):
            self._append_unique(p3.diet, "kosher")

        # Explicit "no allergy" mention still counts as care information.
        if self._contains_any_pattern(
            lower,
            [
                r"\b(no|without)\s+allerg",
                r"\baucune\s+allerg",
                r"\bsans\s+allerg",
                r"\bsin\s+alerg",
                r"\bkeine\s+allerg",
            ],
        ):
            self._append_unique(p3.values, "no_known_allergies")

    def _has_any(self, values: List[str]) -> bool:
        return any(isinstance(value, str) and value.strip() for value in values)

    def _has_products(self, extraction: ExtractionResult) -> bool:
        return bool(extraction.pilier_1_univers_produit.matched_products)

    def _has_usage(self, extraction: ExtractionResult) -> bool:
        return self._has_any(extraction.pilier_1_univers_produit.usage)

    def _has_preferences(self, extraction: ExtractionResult) -> bool:
        prefs = extraction.pilier_1_univers_produit.preferences
        return (
            self._has_any(prefs.colors)
            or self._has_any(prefs.materials)
            or self._has_any(prefs.styles)
            or self._has_any(prefs.hardware)
        )

    def _has_context(self, extraction: ExtractionResult) -> bool:
        context = extraction.pilier_2_profil_client.purchase_context
        return bool((context.type or "").strip() or (context.behavior or "").strip())

    def _has_profession(self, extraction: ExtractionResult) -> bool:
        profession = extraction.pilier_2_profil_client.profession
        return bool((profession.sector or "").strip() or (profession.status or "").strip())

    def _has_occasion(self, extraction: ExtractionResult) -> bool:
        return bool((extraction.pilier_3_hospitalite_care.occasion or "").strip())

    def _has_care_details(self, extraction: ExtractionResult) -> bool:
        p3 = extraction.pilier_3_hospitalite_care
        return (
            self._has_any(p3.allergies.food)
            or self._has_any(p3.allergies.contact)
            or self._has_any(p3.diet)
            or self._has_any(p3.values)
        )

    def _has_budget(self, extraction: ExtractionResult) -> bool:
        p4 = extraction.pilier_4_action_business
        return bool(
            (p4.budget_potential or "").strip()
            or p4.budget_specific is not None
            or (p4.urgency or "").strip()
        )

    def _text_signals(self, source_text: str) -> Dict[str, bool]:
        text = (source_text or "").lower()
        word_count = len(re.findall(r"\w+", text))

        def has_any(words: List[str]) -> bool:
            return any(word in text for word in words)

        return {
            "long_note": word_count >= 18,
            "usage_signal": has_any(
                [
                    "travail", "work", "bureau", "office", "voyage", "travel",
                    "daily", "quotidien", "soir", "evening", "meeting",
                ]
            ),
            "preference_signal": has_any(
                [
                    "couleur", "color", "matiere", "material", "cuir",
                    "leather", "canvas", "monogram", "damier", "style",
                ]
            ),
            "budget_signal": has_any(
                [
                    "budget", "euro", "eur", "k", "€", "prix", "price",
                ]
            ),
            "profession_signal": has_any(
                [
                    "docteur", "doctor", "avocat", "lawyer", "ceo", "cfo",
                    "manager", "directeur", "entrepreneur", "founder",
                    "architecte", "architect", "ingenieur", "engineer",
                    "professeur", "professor",
                ]
            ),
            "occasion_signal": has_any(
                [
                    "anniversaire", "birthday", "compleanno", "cumplea", "geburtstag",
                    "wedding", "mariage", "matrimonio", "boda", "hochzeit",
                    "graduation", "diplom", "laurea", "christmas", "noel", "navidad",
                    "valentin", "valentine", "housewarming", "pendaison de cremaill",
                ]
            ),
            "care_signal": has_any(
                [
                    "allerg", "allergy", "vegan", "vegetar", "gluten",
                    "halal", "kosher", "intolerance", "lactose",
                ]
            ),
        }

    def _calculate_gamification(self, extraction: ExtractionResult, source_text: Optional[str] = None):
        """Calculates a context-aware quality score based on expected information richness."""
        p1 = extraction.pilier_1_univers_produit
        signals = self._text_signals(source_text or "")

        components = {
            "categories": {
                "weight": 20,
                "expected": True,
                "present": bool(p1.categories),
            },
            "context": {
                "weight": 15,
                "expected": True,
                "present": self._has_context(extraction),
            },
            "usage": {
                "weight": 10,
                "expected": signals["usage_signal"],
                "present": self._has_usage(extraction),
            },
            "preferences": {
                "weight": 15,
                "expected": signals["preference_signal"],
                "present": self._has_preferences(extraction),
            },
            "budget": {
                "weight": 10,
                "expected": signals["budget_signal"] or signals["long_note"],
                "present": self._has_budget(extraction),
            },
            "profession": {
                "weight": 10,
                "expected": signals["profession_signal"],
                "present": self._has_profession(extraction),
            },
            "occasion": {
                "weight": 10,
                "expected": signals["occasion_signal"],
                "present": self._has_occasion(extraction),
            },
            "care": {
                "weight": 10,
                "expected": signals["care_signal"],
                "present": self._has_care_details(extraction),
            },
            "rag": {
                "weight": 10,
                "expected": bool(p1.categories),
                "present": self._has_products(extraction),
            },
        }

        expected_weight = 0
        earned_weight = 0
        missing_sections: List[str] = []

        for name, component in components.items():
            if component["expected"]:
                expected_weight += component["weight"]
                if component["present"]:
                    earned_weight += component["weight"]
                else:
                    missing_sections.append(name)

        # Prevent inflated scores on very short notes.
        word_count = len(re.findall(r"\w+", source_text or ""))
        length_factor = min(1.0, max(0.0, word_count / 18.0))
        floor = 0.72 + 0.28 * length_factor

        raw_score = (earned_weight / expected_weight * 100.0) if expected_weight > 0 else 0.0
        final_score = max(0.0, min(100.0, raw_score * floor))
        extraction.meta_analysis.quality_score = float(round(final_score, 2))
        
        # Gamified feedback
        if final_score >= 80:
            feedback = "Super note: profil client tres complet et exploitable en CRM."
        elif final_score >= 50:
            feedback = "Bonne note: le profil est exploitable, encore un peu de profondeur possible."
        else:
            top_missing = ", ".join(missing_sections[:3]) if missing_sections else "contexte client"
            feedback = f"Note a enrichir: ajoute des details sur {top_missing}."
            
        extraction.meta_analysis.advisor_feedback = feedback
