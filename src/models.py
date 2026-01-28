"""
Pydantic models for strict type checking and data validation across the pipeline.
"""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


class RGPDResult(BaseModel):
    """Result from RGPD analysis."""
    contains_sensitive: bool = Field(..., description="Whether sensitive data was detected")
    categories_detected: List[str] = Field(default_factory=list, description="List of sensitive categories found")
    sensitive_spans: List[Dict[str, Any]] = Field(default_factory=list, description="Specific spans of sensitive text")
    safe_to_store: bool = Field(True, description="Whether the data is safe to store")
    severity: Literal['none', 'low', 'medium', 'high'] = Field('none', description="Severity of RGPD risk")
    reasoning: str = Field("", description="Explanation for the classification")
    anonymized_text: Optional[str] = Field(None, description="Text with sensitive parts redacted")


class RoutingDecision(BaseModel):
    """Result of the routing logic."""
    tier: Literal[1, 2, 3] = Field(..., description="Selected processing tier")
    reasons: List[str] = Field(default_factory=list, description="Reasons for routing decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in routing decision")
    priority: Literal['low', 'medium', 'high'] = Field('medium', description="Processing priority")


class ExtractionResult(BaseModel):
    """Unified result from any extraction tier (1, 2, or 3) with strict validation."""
    
    note_id: Optional[str] = Field(None, description="ID of the note being processed")
    client_id: Optional[str] = Field(None, description="Client ID if available")
    
    # Layer 1: Core tags
    tags: List[str] = Field(default_factory=list, description="Extracted tags")
    
    # Layer 2: Entities
    products_mentioned: List[str] = Field(default_factory=list, description="Specific products mentioned")
    professions: List[str] = Field(default_factory=list, description="Client professions")
    
    # Structured data
    budget_range: Optional[str] = Field(None, description="Budget range (e.g., '5K-10K')")
    budget_amount: Optional[int] = Field(None, description="Specific budget amount if found")
    client_status: Optional[str] = Field(None, description="Client status (VIC, VIP, regular, etc.)")
    
    allergies: List[str] = Field(default_factory=list, description="List of allergies")
    allergy_severity: Literal['low', 'medium', 'high'] = Field('low', description="Severity of allergies")
    dietary: List[str] = Field(default_factory=list, description="Dietary restrictions")
    
    relationship_context: Dict[str, List[str]] = Field(default_factory=dict, description="Relationships (shopping_with, gift_for)")
    key_dates: List[Dict[str, Any]] = Field(default_factory=list, description="Important dates mentioned")
    
    # Metadata
    processing_tier: Literal['tier1', 'tier2', 'tier3'] = Field(..., description="Tier that processed this result")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of extraction")
    processing_time_ms: float = Field(0.0, description="Processing time in milliseconds")
    
    rgpd_flag: bool = Field(False, description="Whether RGPD sensitive data was detected")
    error: Optional[str] = Field(None, description="Error message if any")
    
    # Legacy fields for backward compatibility (optional)
    reasoning: Optional[str] = Field(None, description="Reasoning for extraction")
    model_name: Optional[str] = Field(None, description="Specific model used")
    cost: float = Field(0.0, description="Cost of processing")
    
    age: Optional[int] = Field(None, description="Client age")
    gender: Optional[str] = Field(None, description="Client gender")

    @validator('tags')
    def tags_valid(cls, v):
        """Validate tags against taxonomy."""
        # Lazy import to avoid circular dependency if any
        from src.taxonomy import TaxonomyManager
        
        # Initialize manager (cached in practice)
        taxonomy = TaxonomyManager()
        
        # We allow some dynamic tags (relationships) but warn/fail on others
        # For this implementation, we'll filter or raise. 
        # User requested raise ValueError.
        
        valid_tags = []
        invalid = []
        
        for tag in v:
            normalized = taxonomy.normalize_tag(tag)
            if normalized:
                valid_tags.append(normalized)
            else:
                # Still allow dynamic tags if they follow pattern, otherwise track as invalid
                if tag.startswith('shopping_with_') or tag.startswith('gift_for_'):
                    valid_tags.append(tag)
                else:
                    invalid.append(tag)
        
        if invalid:
            # Log warning but don't crash if we want to be lenient, OR raise if strict.
            # With fuzzy matching, we can be strict about the rest.
            raise ValueError(f"Invalid tags (could not normalize): {invalid}")
            
        return list(set(valid_tags))


class PipelineOutput(BaseModel):
    """Final output for a processed note."""
    id: str = Field(..., description="Note ID")
    original_text: str = Field(..., description="Original transcription")
    processed_text: str = Field(..., description="Cleaned/Anonymized text")
    language: str = Field("FR", description="Language code")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    routing: RoutingDecision
    rgpd: RGPDResult
    extraction: ExtractionResult
    
    processing_time_ms: float = Field(0.0, description="Total processing time in ms")
    error: Optional[str] = Field(None, description="Error message if failed")
    from_cache: bool = Field(False, description="Whether result came from cache")
