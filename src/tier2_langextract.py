"""
Tier 2 Extractor using LangExtract

Replaces Tier2Mistral with LangExtract for improved extraction accuracy.
Uses Mistral via OpenAI-compatible endpoint with key rotation.
"""

import os
import logging
import asyncio
import time
from typing import Optional

from src.services.langextract_service import get_langextract_service
from src.models import (
    ExtractionResult,
    Pilier1Product,
    Pilier2Client,
    Pilier3Care,
    Pilier4Business,
    MetaAnalysis,
    ProductPreferences,
    PurchaseContext,
    Profession,
    Lifestyle,
    Allergies,
    NextBestAction,
)

logger = logging.getLogger(__name__)


def _map_langextract_to_extraction_result(lx_tags: list, text: str, confidence: float = 0.90) -> ExtractionResult:
    """
    Map LangExtract tags to ExtractionResult 4-pillar structure.
    """
    # Initialize empty structures
    pilier_1 = Pilier1Product(
        categories=[],
        produits_mentionnes=[],
        usage=[],
        preferences=ProductPreferences(),
    )
    
    pilier_2 = Pilier2Client(
        purchase_context=PurchaseContext(),
        profession=Profession(),
        lifestyle=Lifestyle(),
    )
    
    pilier_3 = Pilier3Care(
        allergies=Allergies(),
    )
    
    pilier_4 = Pilier4Business()
    
    budget_max = None
    
    # Map LangExtract tags to pillars
    for tag in lx_tags:
        tag_class = tag.get("class", "")
        tag_text = tag.get("text", "")
        attrs = tag.get("attributes", {})
        
        if tag_class == "produit":
            # Map to Pilier 1
            if attrs.get("categorie"):
                cat = attrs["categorie"]
                if isinstance(cat, list):
                    cat = cat[0] if cat else ""
                elif not isinstance(cat, str):
                    cat = str(cat)
                if cat:
                    pilier_1.categories.append(cat)
            if attrs.get("marque"):
                pilier_1.produits_mentionnes.append(f"{attrs.get('marque')} {tag_text}")
            if attrs.get("budget"):
                try:
                    budget_max = int(attrs["budget"].replace("€", "").replace(",", ""))
                except:
                    pass
                
        elif tag_class == "profil_client":
            # Map to Pilier 2
            if attrs.get("statut"):
                status = attrs["statut"].lower()
                if status in ["vic", "vip"]:
                    pilier_2.purchase_context.behavior = "VIP"
                elif status == "fidèle":
                    pilier_2.purchase_context.behavior = "Regular"
                elif status == "nouveau":
                    pilier_2.purchase_context.behavior = "New"
                    
        elif tag_class == "hospitalite":
            # Map to Pilier 3
            if attrs.get("occasion"):
                occasion = attrs["occasion"]
                if isinstance(occasion, list):
                    occasion = occasion[0] if occasion else ""
                elif not isinstance(occasion, str):
                    occasion = str(occasion)
                if occasion:
                    pilier_3.occasion = occasion
                
        elif tag_class == "action_business":
            # Map to Pilier 4
            if attrs.get("type_action"):
                action_type = attrs["type_action"]
                if isinstance(action_type, list):
                    action_type = action_type[0] if action_type else "follow_up"
                elif not isinstance(action_type, str):
                    action_type = str(action_type)
                pilier_4.next_best_action = NextBestAction(
                    action_type=action_type,
                    description=f"Action: {action_type}"
                )
            if attrs.get("urgence"):
                urgency = attrs["urgence"].lower()
                if urgency == "haute":
                    pilier_4.urgency = "high"
                else:
                    pilier_4.urgency = "medium"
    
    # Build MetaAnalysis
    meta = MetaAnalysis(
        language_detected="FR",
        word_count=len(text.split()),
        has_budget=bool(budget_max),
        has_brand=bool(pilier_1.produits_mentionnes),
        is_vic=pilier_2.purchase_context.behavior == "VIP",
    )
    
    return ExtractionResult(
        pilier_1_univers_produit=pilier_1,
        pilier_2_profil_client=pilier_2,
        pilier_3_hospitalite_care=pilier_3,
        pilier_4_action_business=pilier_4,
        meta_analysis=meta,
        confidence=confidence,
        processing_tier="tier2_langextract",
        extracted_by="tier2_langextract",
    )


class Tier2LangExtract:
    """
    Tier 2 implementation using LangExtract with Mistral API.
    
    Advantages:
    - Source grounding (char offsets when available)
    - Schema enforcement via few-shot examples
    - RGPD-compliant (Mistral EU)
    - Key rotation support
    """
    
    def __init__(self):
        self._service = get_langextract_service()
        logger.info("Initialized Tier2LangExtract")
    
    async def extract(self, text: str, language: str = "FR") -> ExtractionResult:
        """
        Extract structured data from note using LangExtract.
        
        Args:
            text: Input transcription
            language: Language code
            
        Returns:
            ExtractionResult with 4-pillar structure
        """
        start_time = time.time()
        
        try:
            # Call LangExtract service
            result = self._service.extract(text, language)
            
            if result["success"]:
                extraction = _map_langextract_to_extraction_result(
                    result["tags"],
                    text,
                    confidence=0.90
                )
                extraction.processing_time_ms = (time.time() - start_time) * 1000
                extraction.extracted_by = "tier2_langextract"
                
                logger.info(f"LangExtract extraction success: {len(result['tags'])} tags")
                return extraction
            else:
                error_msg = result.get("error", "Unknown error")
                logger.warning(f"LangExtract extraction failed: {error_msg}")
                
                # Return empty result with error
                return ExtractionResult(
                    pilier_1_univers_produit=Pilier1Product(),
                    pilier_2_profil_client=Pilier2Client(),
                    pilier_3_hospitalite_care=Pilier3Care(),
                    pilier_4_action_business=Pilier4Business(),
                    meta_analysis=MetaAnalysis(),
                    confidence=0.0,
                    processing_tier="tier2_langextract",
                    extracted_by="tier2_langextract",
                    error=error_msg,
                )
                
        except Exception as e:
            logger.error(f"LangExtract extraction exception: {e}")
            return ExtractionResult(
                pilier_1_univers_produit=Pilier1Product(),
                pilier_2_profil_client=Pilier2Client(),
                pilier_3_hospitalite_care=Pilier3Care(),
                pilier_4_action_business=Pilier4Business(),
                meta_analysis=MetaAnalysis(),
                confidence=0.0,
                processing_tier="tier2_langextract",
                extracted_by="tier2_langextract",
                error=str(e),
            )
