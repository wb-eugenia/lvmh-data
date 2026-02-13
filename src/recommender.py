"""
Next Best Action Recommender Engine.
Transforms extracted tags and context into actionable business suggestions.
"""

import json
import os
import re
from typing import List, Dict, Optional, Any
from src.models import ExtractionResult, Pilier4Business, NextBestAction
import logging
from src.analytics.predictions import SyntheticClientPredictions

try:
    from mistralai import Mistral
    HAS_MISTRAL = True
except ImportError:
    HAS_MISTRAL = False

logger = logging.getLogger(__name__)

class RecommenderEngine:
    """
    Engine that generates business recommendations based on extracted pillars.
    """

    NBA_GENERATION_PROMPT = """
Tu es un Manager LVMH expert en stratégie client boutique de luxe.
Génère une Next Best Action concrète, priorisée, orientée conversion.

Règles:
1. Prioriser les actions time-sensitive (réservation, RDV, stock limité, deadline).
2. Mentionner explicitement les contraintes critiques (allergies, restrictions, urgences).
3. Proposer un cross-sell pertinent uniquement si cohérent avec budget et intention.
4. Être concret: QUI, QUOI, QUAND.
5. Pas d'actions génériques.

Réponds en JSON strict:
{
  "nba_text": "string",
  "actions": [
    {
      "type": "reservation|rdv_preparation|cross_sell|verification|follow_up|retention_call",
      "priority": "urgent|high|medium|low|critical",
      "text": "Action concrète",
      "deadline": "ISO-8601 or relative",
      "product_sku": "optional"
    }
  ],
  "overall_priority": "urgent|high|medium|low|critical"
}
"""
    
    def __init__(self):
        self.predictor: Optional[SyntheticClientPredictions] = None
        try:
            self.predictor = SyntheticClientPredictions()
        except Exception as exc:
            logger.warning("Synthetic prediction engine unavailable: %s", exc)

        self.nba_llm_enabled = os.getenv("LVMH_ENABLE_NBA_LLM", "false").lower() in {"1", "true", "yes"}
        self.nba_llm_model = os.getenv("NBA_LLM_MODEL", "mistral-large-latest")
        self.nba_llm_client = None
        if self.nba_llm_enabled:
            api_key = os.getenv("MISTRAL_API_KEY")
            if HAS_MISTRAL and api_key:
                try:
                    self.nba_llm_client = Mistral(api_key=api_key)
                except Exception as exc:
                    logger.warning("NBA LLM disabled (client init failed): %s", exc)
            else:
                logger.warning("NBA LLM requested but Mistral client/api key unavailable.")
    
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
        
        # Match products from RAG if available
        products = [p.get('name', 'N/A') for p in p1.matched_products]
        top_product = products[0] if products else None

        # Optional structured NBA generation via LLM (guarded by env flag).
        if p4.next_best_action is None:
            llm_action = self._generate_nba_llm_action(extraction, source_text or "")
            if llm_action is not None:
                p4.next_best_action = llm_action

        action = p4.next_best_action
        if action is None:
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
            elif p1.categories:
                desc = f"Relance le client sur ses favoris: {', '.join(p1.categories[:2])}. "
                if budget:
                    desc += f"Budget estimé: {budget}."
                    
                action = NextBestAction(
                    action_type="follow_up",
                    description=desc,
                    priority="Medium",
                    target_products=products[:2]
                )

            # Inject deterministic fallback recommendation if found
            if action:
                p4.next_best_action = action

        self._augment_nba_from_text(extraction, source_text or "")

        prediction = self._predict_client_signals(extraction, source_text or "")
        if prediction:
            p4.churn_risk = prediction.get("churn_risk")
            p4.churn_level = prediction.get("churn_level")
            p4.clv_estimate = prediction.get("clv_estimate")
            p4.clv_tier = prediction.get("clv_tier")
            p4.prediction_source = prediction.get("prediction_source")

            if p4.churn_level == "high":
                if p4.next_best_action is None:
                    p4.next_best_action = NextBestAction(
                        action_type="retention_call",
                        description=f"Client a risque churn ({p4.churn_risk:.0%}) - appel de retention prioritaire.",
                        priority="Critical",
                        target_products=products[:1],
                        deadline="48h",
                    )
                else:
                    p4.next_best_action.priority = "Critical"
                    if "churn" not in p4.next_best_action.description.lower():
                        p4.next_best_action.description += f" Risque churn estime: {p4.churn_risk:.0%}."

            if p4.clv_tier == "platinum" and p4.next_best_action is not None:
                if p4.next_best_action.priority in {"Low", "Medium"}:
                    p4.next_best_action.priority = "High"
                if "CLV" not in p4.next_best_action.description:
                    p4.next_best_action.description += f" CLV estime: {p4.clv_estimate:,.0f} EUR."
            
        # --- GAMIFICATION (Super Note Score) ---
        self._calculate_gamification(extraction, source_text=source_text)
            
        return extraction

    def _predict_client_signals(
        self, extraction: ExtractionResult, source_text: str
    ) -> Optional[Dict[str, Any]]:
        if self.predictor is None:
            return None
        try:
            return self.predictor.predict_from_extraction(extraction, source_text=source_text)
        except Exception as exc:
            logger.warning("Prediction enrichment skipped: %s", exc)
            return None

    def _generate_nba_llm_action(
        self,
        extraction: ExtractionResult,
        source_text: str,
    ) -> Optional[NextBestAction]:
        if not self.nba_llm_client:
            return None

        p1 = extraction.pilier_1_univers_produit
        p2 = extraction.pilier_2_profil_client
        p3 = extraction.pilier_3_hospitalite_care
        p4 = extraction.pilier_4_action_business

        constraints: List[str] = []
        if p3.allergies.food or p3.allergies.contact:
            constraints.append(
                f"allergies={p3.allergies.food + p3.allergies.contact}"
            )
        if p4.urgency:
            constraints.append(f"urgency={p4.urgency}")
        if p3.occasion:
            constraints.append(f"occasion={p3.occasion}")

        matched_products = []
        for product in (p1.matched_products or [])[:3]:
            if not isinstance(product, dict):
                continue
            matched_products.append(
                {
                    "name": product.get("name"),
                    "sku": product.get("sku"),
                    "price": product.get("price"),
                    "score": product.get("match_score"),
                }
            )

        payload = {
            "note_summary": (source_text or "")[:500],
            "client_profile": {
                "tier": p2.purchase_context.behavior,
                "purchase_type": p2.purchase_context.type,
                "budget_potential": p4.budget_potential,
                "budget_specific": p4.budget_specific,
            },
            "product_context": {
                "categories": p1.categories[:5],
                "products_mentioned": p1.produits_mentionnes[:5],
                "matched_products": matched_products,
            },
            "constraints": constraints,
        }

        try:
            request_args = {
                "model": self.nba_llm_model,
                "messages": [
                    {"role": "system", "content": self.NBA_GENERATION_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            }
            try:
                response = self.nba_llm_client.chat.complete(
                    **request_args,
                    response_format={"type": "json_object"},
                )
            except TypeError:
                response = self.nba_llm_client.chat.complete(**request_args)

            content = response.choices[0].message.content
            if isinstance(content, list):
                content = "".join(
                    chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                    for chunk in content
                )
            if not isinstance(content, str):
                return None

            data = json.loads(content)
            actions = data.get("actions", []) if isinstance(data, dict) else []
            first_action = actions[0] if actions and isinstance(actions[0], dict) else {}
            description = (
                first_action.get("text")
                or data.get("nba_text")
                or "Relance client avec préparation personnalisée."
            )

            action_type = str(first_action.get("type") or "follow_up").strip().lower() or "follow_up"
            priority = self._normalize_priority(
                first_action.get("priority") or data.get("overall_priority") or "medium"
            )
            deadline = first_action.get("deadline")
            targets = [item.get("name") for item in matched_products if isinstance(item, dict) and item.get("name")]
            if first_action.get("product_sku"):
                targets.insert(0, str(first_action.get("product_sku")))
            target_products = list(dict.fromkeys([str(target).strip() for target in targets if str(target).strip()]))[:3]

            return NextBestAction(
                action_type=action_type,
                description=str(description).strip(),
                priority=priority,
                target_products=target_products,
                deadline=str(deadline).strip() if isinstance(deadline, str) and deadline.strip() else None,
            )
        except Exception as exc:
            logger.warning("NBA LLM generation failed, fallback deterministic rules: %s", exc)
            return None

    def _normalize_priority(self, value: Any) -> str:
        mapping = {
            "critical": "Critical",
            "urgent": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        normalized = str(value or "").strip().lower()
        return mapping.get(normalized, "Medium")

    def _normalize_score_pct(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        if score <= 1.0:
            score *= 100.0
        return max(0.0, min(100.0, score))

    def _extract_meeting_hint(self, source_text: str) -> Optional[str]:
        text = source_text or ""
        # Supports "lundi 11h", "monday at 11:00", "vendredi a 14h30"
        match = re.search(
            r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:a|à|at)?\s*(\d{1,2}(?:h\d{0,2}|:\d{2})?))?",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        day = match.group(1).strip()
        hour = (match.group(2) or "").strip()
        if hour:
            return f"{day} {hour}"
        return day

    def _augment_nba_from_text(self, extraction: ExtractionResult, source_text: str) -> None:
        text = (source_text or "").lower()
        p1 = extraction.pilier_1_univers_produit
        p3 = extraction.pilier_3_hospitalite_care
        p4 = extraction.pilier_4_action_business

        if p4.next_best_action is None:
            p4.next_best_action = NextBestAction(
                action_type="follow_up",
                description="Relance client avec preparation personnalisee.",
                priority="Medium",
                target_products=[],
            )

        action = p4.next_best_action
        assert action is not None
        fragments: List[str] = []

        mentioned_products = [str(prod).strip() for prod in p1.produits_mentionnes if str(prod).strip()]
        rag_products = [str(prod.get("name", "")).strip() for prod in p1.matched_products if isinstance(prod, dict)]
        merged_targets = list(dict.fromkeys([*action.target_products, *mentioned_products[:2], *rag_products[:2]]))
        action.target_products = [target for target in merged_targets if target]

        if self._contains_any_pattern(text, [r"\breserv", r"\br[ée]server", r"\bbook\b", r"\bhold\b"]):
            product_label = action.target_products[0] if action.target_products else "le produit mentionne"
            fragments.append(f"Reserver {product_label} avant le prochain passage client.")
            if action.priority in {"Low", "Medium"}:
                action.priority = "High"

        has_nickel_signal = (
            self._contains_any_pattern(text, [r"\bnickel\b"])
            or any("nickel" in str(item).lower() for item in p3.allergies.contact)
        )
        if has_nickel_signal:
            fragments.append("Verifier les finitions sans nickel avant presentation.")
            if action.priority in {"Low", "Medium"}:
                action.priority = "High"

        if self._contains_any_pattern(text, [r"rendez[-\s]?vous", r"\brdv\b", r"\bappointment\b", r"\bmeeting\b", r"\breviendra\b"]):
            meeting_hint = self._extract_meeting_hint(source_text)
            if meeting_hint:
                fragments.append(f"Preparer la selection pour le RDV {meeting_hint}.")
            else:
                fragments.append("Preparer une selection pour le prochain RDV.")

        if self._contains_any_pattern(text, [r"\bportefeuille\b", r"\bwallet\b", r"\bsmall leather\b"]):
            fragments.append("Preparer un portefeuille assorti en cross-sell.")

        if fragments:
            normalized_description = (action.description or "").strip()
            for fragment in fragments:
                if fragment.lower() not in normalized_description.lower():
                    normalized_description = f"{normalized_description} {fragment}".strip()
            action.description = normalized_description

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
                "diplomacy": [r"\bdiplomat(e)?\b", r"\bonu\b", r"\bunited nations\b", r"\bconsul(?:at)?\b", r"\bambassador\b", r"\bambassadeur\b"],
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

    def _has_specific_occasion(self, extraction: ExtractionResult) -> bool:
        occasion = str(extraction.pilier_3_hospitalite_care.occasion or "").strip().lower()
        if not occasion:
            return False
        if occasion.endswith("_gift"):
            return True
        return occasion in {"wedding_anniversary", "career_milestone", "coming_of_age"}

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
            "occasion_specificity": {
                "weight": 8,
                "expected": signals["occasion_signal"],
                "present": self._has_specific_occasion(extraction),
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
        completeness_score = max(0.0, min(100.0, raw_score))

        meta = extraction.meta_analysis
        meta.quality_score = float(round(final_score, 2))
        meta.completeness_score = float(round(completeness_score, 2))

        confidence_candidates = [
            self._normalize_score_pct(getattr(meta, "confidence_score", 0.0)),
            self._normalize_score_pct(getattr(extraction, "confidence", 0.0)),
        ]
        confidence_score = max(confidence_candidates)
        if confidence_score <= 0.0:
            confidence_score = max(45.0, min(95.0, 40.0 + final_score * 0.55))
        meta.confidence_score = float(round(confidence_score, 2))

        missing_labels = {
            "categories": "Categorie produit non detectee",
            "context": "Type d'achat indetermine",
            "usage": "Usage client non precise",
            "preferences": "Preferences produit non precisees",
            "budget": "Budget non specifie",
            "profession": "Profil socio-professionnel incomplet",
            "occasion": "Occasion non mentionnee",
            "occasion_specificity": "Contexte occasion peu specifique",
            "care": "Informations care/allergies absentes",
        }
        normalized_missing = [
            missing_labels[name]
            for name in missing_sections
            if name in missing_labels
        ]
        meta.missing_info = list(dict.fromkeys(normalized_missing))

        # Gamified feedback
        if final_score >= 80:
            feedback = "Super note: profil client tres complet et exploitable en CRM."
        elif final_score >= 50:
            feedback = "Bonne note: le profil est exploitable, encore un peu de profondeur possible."
        else:
            top_missing = ", ".join(meta.missing_info[:3]) if meta.missing_info else "contexte client"
            feedback = f"Note a enrichir: ajoute des details sur {top_missing}."

        meta.advisor_feedback = feedback
