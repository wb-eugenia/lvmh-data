"""
Pydantic models for strict type checking and data validation.
Aligned with Universal Luxury Taxonomy V2.
"""

from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

# ==========================================
# PILIER 1: UNIVERS PRODUIT
# ==========================================

class ProductPreferences(BaseModel):
    colors: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    hardware: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)

class Pilier1Product(BaseModel):
    categories: List[str] = Field(default_factory=list, description="Leather_Goods, Handbag_Main...")
    produits_mentionnes: List[str] = Field(default_factory=list, description="LV Products mentioned by name")
    usage: List[str] = Field(default_factory=list, description="Professional, Travel...")
    preferences: ProductPreferences = Field(default_factory=ProductPreferences)
    
    # RAG Enrichment (New!)
    matched_products: List[Dict[str, Any]] = Field(default_factory=list, description="SKUs identified via Vector Search")

# ==========================================
# PILIER 2: PROFIL CLIENT
# ==========================================

class PurchaseContext(BaseModel):
    type: Optional[str] = Field(None, description="Self_Purchase, Gift...")
    behavior: Optional[str] = Field(None, description="VIP, Regular...")

class Profession(BaseModel):
    sector: Optional[str] = Field(None)
    status: Optional[str] = Field(None)

class Lifestyle(BaseModel):
    passions: List[str] = Field(default_factory=list)
    family: Optional[str] = Field("Unknown")

class Pilier2Client(BaseModel):
    purchase_context: PurchaseContext = Field(default_factory=PurchaseContext)
    profession: Profession = Field(default_factory=Profession)
    lifestyle: Lifestyle = Field(default_factory=Lifestyle)

# ==========================================
# PILIER 3: HOSPITALITE & CARE
# ==========================================

class Allergies(BaseModel):
    food: List[str] = Field(default_factory=list)
    contact: List[str] = Field(default_factory=list)

class Pilier3Care(BaseModel):
    diet: List[str] = Field(default_factory=list)
    allergies: Allergies = Field(default_factory=Allergies)
    values: List[str] = Field(default_factory=list)
    occasion: Optional[str] = Field(None)

# ==========================================
# PILIER 4: ACTION BUSINESS
# ==========================================

class NextBestAction(BaseModel):
    action_type: str = Field(description="gift_suggestion, follow_up, invitation, apology...")
    description: str = Field(description="Human readable recommendation for the CA")
    priority: Literal["Low", "Medium", "High", "Critical"] = Field("Medium")
    target_products: List[str] = Field(default_factory=list, description="Recommended SKUs or categories")
    deadline: Optional[str] = Field(None, description="ISO date or relative string")

class Pilier4Business(BaseModel):
    lead_temperature: Optional[str] = Field("Warm")
    next_best_action: Optional[NextBestAction] = Field(None)
    budget_potential: Optional[str] = Field(None)
    budget_specific: Optional[int] = Field(None, description="Exact budget amount in EUR")
    urgency: Optional[str] = Field(None)

# ==========================================
# META & WRAPPER
# ==========================================

class MetaAnalysis(BaseModel):
    confidence_score: float = Field(0.0)
    missing_info: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    
    # Gamification
    quality_score: float = Field(0.0, description="0-100 score for data richness")
    completeness_score: float = Field(0.0, description="0-100 score for data completeness")
    advisor_feedback: Optional[str] = Field(None, description="Gamified feedback for the advisor")

class ExtractionResult(BaseModel):
    """Unified result matching the 4-Pillar JSON structure."""
    
    pilier_1_univers_produit: Pilier1Product
    pilier_2_profil_client: Pilier2Client
    pilier_3_hospitalite_care: Pilier3Care
    pilier_4_action_business: Pilier4Business
    meta_analysis: MetaAnalysis

    # Metadata fields
    confidence: float = 0.0
    processing_tier: str = "unknown"
    extracted_by: Optional[str] = None
    error: Optional[str] = None
    from_cache: bool = False
    processing_time_ms: float = 0.0
    rgpd_flag: bool = False

    # Legacy fields wrapper (for backward compatibility if needed)
    @property
    def tags(self) -> List[str]:
        """Flatten specific categories as tags for legacy systems"""
        return (
            self.pilier_1_univers_produit.categories + 
            [self.pilier_4_action_business.next_best_action or ""]
        )

# ==========================================
# PIPELINE OUTPUT
# ==========================================

class RoutingDecision(BaseModel):
    tier: int
    reasons: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    priority: str = "Medium"

class RGPDResult(BaseModel):
    contains_sensitive: bool = False
    categories_detected: List[str] = Field(default_factory=list)
    safe_to_store: bool = True
    severity: str = "low"
    reasoning: Optional[str] = None
    anonymized_text: Optional[str] = None

class PipelineOutput(BaseModel):
    id: str
    original_text: Optional[str] = None
    processed_text: str
    language: str = "FR"
    timestamp: datetime = Field(default_factory=datetime.now)
    
    routing: RoutingDecision
    rgpd: RGPDResult
    extraction: Optional[ExtractionResult] = None # Make optional to handle failures
    
    tier: Optional[int] = None # Legacy/Shortcut
    processing_time_ms: float = 0.0
    from_cache: bool = False

