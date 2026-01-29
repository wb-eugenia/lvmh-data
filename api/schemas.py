"""
Pydantic schemas for API validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime


# ============== Input Schemas ==============

class NoteInput(BaseModel):
    """Input for single note analysis."""
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Note transcription text"
    )
    language: Literal['FR', 'EN', 'IT'] = Field(
        default='FR',
        description="Language of the transcription"
    )
    
    @field_validator('text')
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Basic XSS prevention
        if '<script' in v.lower():
            raise ValueError('Invalid characters detected')
        return v.strip()


class BatchFileInput(BaseModel):
    """Metadata for batch file upload."""
    filename: str
    total_rows: int


# ============== Output Schemas ==============

class ExtractionTags(BaseModel):
    """Extracted tags structure."""
    brand: Optional[str] = None
    product_category: Optional[str] = None
    product_type: Optional[str] = None
    vip_status: Optional[str] = None
    budget_range: Optional[str] = None
    occasion: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)


class RGPDInfo(BaseModel):
    """RGPD/GDPR compliance info."""
    contains_sensitive: bool = False
    categories_detected: List[str] = Field(default_factory=list)
    anonymized_text: Optional[str] = None


class RoutingInfo(BaseModel):
    """Routing decision info."""
    tier: int = Field(ge=1, le=3)
    confidence: float = Field(ge=0, le=1)
    reason: Optional[str] = None


class ExtractionResult(BaseModel):
    """Full extraction result."""
    id: str
    tags: List[str] = Field(default_factory=list)
    extraction: ExtractionTags = Field(default_factory=ExtractionTags)
    routing: RoutingInfo
    rgpd: RGPDInfo = Field(default_factory=RGPDInfo)
    processing_time_ms: float
    cache_hit: bool = False
    model_used: Optional[str] = None


# ============== Stats Schemas ==============

class TierStats(BaseModel):
    """Stats per tier."""
    tier: int
    count: int
    percentage: float
    avg_processing_time_ms: float


class OverviewStats(BaseModel):
    """Dashboard overview stats."""
    total_notes: int
    total_tags: int
    avg_confidence: float
    avg_processing_time_ms: float
    tier_distribution: List[TierStats]
    top_tags: Dict[str, int]
    cache_hit_rate: float


class RGPDStats(BaseModel):
    """RGPD compliance stats."""
    total_notes: int
    sensitive_count: int
    sensitive_rate: float
    categories: Dict[str, int]
    false_positive_rate: float
    false_negative_rate: float


class CostStats(BaseModel):
    """Cost breakdown stats."""
    total_cost: float
    cost_by_tier: Dict[str, float]
    projection_annual: float
    roi_metrics: Dict[str, Any]


# ============== Batch Schemas ==============

class BatchTask(BaseModel):
    """Batch processing task status."""
    task_id: str
    status: Literal['pending', 'processing', 'complete', 'error']
    progress: int
    total: int
    created_at: datetime
    results: List[ExtractionResult] = Field(default_factory=list)
    error: Optional[str] = None


# ============== Pagination ==============

class PaginatedResults(BaseModel):
    """Paginated results response."""
    items: List[ExtractionResult]
    total: int
    page: int
    page_size: int
    total_pages: int
