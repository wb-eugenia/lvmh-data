"""
Next Best Action Recommender Engine.
Transforms extracted tags and context into actionable business suggestions.
"""

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
    
    def generate_recommendation(self, extraction: ExtractionResult) -> ExtractionResult:
        """
        Processes an extraction result and populates the next_best_action field.
        """
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
        self._calculate_gamification(extraction)
            
        return extraction

    def _calculate_gamification(self, extraction: ExtractionResult):
        """Calculates a quality score based on richness across pillars."""
        score = 0
        points = []
        
        p1 = extraction.pilier_1_univers_produit
        p2 = extraction.pilier_2_profil_client
        p3 = extraction.pilier_3_hospitalite_care
        
        # Pillar 1 Richness
        if p1.categories: score += 20; points.append("Categories")
        if p1.usage: score += 10; points.append("Usage")
        if p1.preferences.colors or p1.preferences.materials: score += 15; points.append("Prefs")
        
        # Pillar 2 Richness
        if p2.purchase_context.type: score += 10; points.append("Context")
        if p2.profession.sector: score += 10; points.append("Profession")
        
        # Pillar 3 Richness
        if p3.occasion: score += 20; points.append("Occasion")
        if p3.allergies.food or p3.allergies.contact: score += 15; points.append("Health/Allergy")

        final_score = min(score, 100)
        extraction.meta_analysis.quality_score = float(final_score)
        
        # Gamified feedback
        if final_score >= 80:
            feedback = "🌟 Super note ! +10 points d'expert. Tu as capturé un profil ultra-complet."
        elif final_score >= 50:
            feedback = "👍 Bonne note ! Ton profil client s'enrichit bien."
        else:
            feedback = "💡 Note un peu courte. N'hésite pas à préciser l'occasion ou les préférences matières du client."
            
        extraction.meta_analysis.advisor_feedback = feedback
