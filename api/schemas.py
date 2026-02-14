"""
Pydantic schemas for API validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime


# ============== Input Schemas ==============

SUPPORTED_LANGUAGES = {'FR', 'EN', 'IT', 'ES', 'DE', 'AUTO'}
LANGUAGE_ALIASES = {
    'FR-FR': 'FR',
    'EN-US': 'EN',
    'EN-GB': 'EN',
    'IT-IT': 'IT',
    'ES-ES': 'ES',
    'DE-DE': 'DE',
    'UK': 'EN',
}

TRUTHY_VALUES = {'1', 'true', 'yes', 'y', 'oui'}


def _to_string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        source = value.split(',')
    elif isinstance(value, (list, tuple, set)):
        source = list(value)
    else:
        return []
    normalized: List[str] = []
    seen = set()
    for raw in source:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value or '').strip().lower()
    if not normalized:
        return False
    return normalized in TRUTHY_VALUES

class NoteInput(BaseModel):
    """Input for single note analysis."""
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Note transcription text"
    )
    language: Literal['FR', 'EN', 'IT', 'ES', 'DE', 'AUTO'] = Field(
        default='FR',
        description="Language of the transcription. Use AUTO to detect from text."
    )
    is_written_note: bool = Field(
        default=True,
        description="True for web app (written notes), False for voice recordings. Affects routing."
    )
    
    @field_validator('text')
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Basic XSS prevention
        if '<script' in v.lower():
            raise ValueError('Invalid characters detected')
        return v.strip()

    @field_validator('language', mode='before')
    @classmethod
    def normalize_language(cls, v: Optional[str]) -> str:
        """Normalize locale variants and fallback to FR for unknown values."""
        lang = str(v or 'FR').strip().upper()
        lang = LANGUAGE_ALIASES.get(lang, lang)
        if lang not in SUPPORTED_LANGUAGES:
            return 'FR'
        return lang


class ParityProbeInput(NoteInput):
    """Input for parity probe (same runtime API projection vs runtime projection)."""

    profile: Literal['single_note', 'batch_csv'] = Field(
        default='single_note',
        description="Runtime profile used by the pipeline in probe mode.",
    )


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

    @field_validator('contains_sensitive', mode='before')
    @classmethod
    def normalize_contains_sensitive(cls, v: Any) -> bool:
        return _to_bool(v)

    @field_validator('categories_detected', mode='before')
    @classmethod
    def normalize_categories_detected(cls, v: Any) -> List[str]:
        return _to_string_list(v)


class RoutingInfo(BaseModel):
    """Routing decision info."""
    tier: int = Field(ge=1, le=3)
    confidence: float = Field(ge=0, le=1)
    reason: Optional[str] = None

    @field_validator('tier', mode='before')
    @classmethod
    def normalize_tier(cls, v: Any) -> int:
        try:
            tier = int(round(float(v)))
        except (TypeError, ValueError):
            tier = 1
        return min(3, max(1, tier))

    @field_validator('confidence', mode='before')
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        try:
            confidence = float(v)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence


class MetaAnalysis(BaseModel):
    """Meta analysis info."""
    quality_score: float = 0.0
    confidence_score: float = 0.0
    completeness_score: float = 0.0
    advisor_feedback: Optional[str] = None
    missing_info: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)


class ParityProjection(BaseModel):
    """Compact parity projection used by benchmark tooling."""

    tier: int = Field(ge=1, le=3)
    rgpd_contains_sensitive: bool = False
    tags: List[str] = Field(default_factory=list)

    @field_validator('tier', mode='before')
    @classmethod
    def normalize_tier(cls, v: Any) -> int:
        try:
            tier = int(round(float(v)))
        except (TypeError, ValueError):
            tier = 1
        return min(3, max(1, tier))

    @field_validator('rgpd_contains_sensitive', mode='before')
    @classmethod
    def normalize_sensitive_flag(cls, v: Any) -> bool:
        return _to_bool(v)

    @field_validator('tags', mode='before')
    @classmethod
    def normalize_tags(cls, v: Any) -> List[str]:
        return _to_string_list(v)


class ParityProbeDiff(BaseModel):
    """Per-note parity diff summary."""

    tier_mismatch: bool = False
    rgpd_mismatch: bool = False
    tag_jaccard: float = Field(default=1.0, ge=0.0, le=1.0)


class ParityProbeMeta(BaseModel):
    """Runtime metadata for parity diagnostics."""

    profile: str = 'single_note'
    model_used: Optional[str] = None
    processing_time_ms: float = 0.0
    cache_hit: bool = False


class ParityProbeResult(BaseModel):
    """Full payload returned by /api/analyze/parity-probe."""

    api_projection: ParityProjection
    runtime_projection: ParityProjection
    diff: ParityProbeDiff
    meta: ParityProbeMeta


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    id: str
    notes: int
    score: int


class ExtractionResult(BaseModel):
    """Full extraction result with 4-pillar taxonomy."""
    id: str
    tags: List[str] = Field(default_factory=list)
    extraction: ExtractionTags = Field(default_factory=ExtractionTags)
    routing: RoutingInfo
    rgpd: RGPDInfo = Field(default_factory=RGPDInfo)
    meta_analysis: MetaAnalysis = Field(default_factory=MetaAnalysis)
    
    # 4-Pillar Taxonomy (Optional for detailed UI)
    pilier_1_univers_produit: Optional[Dict[str, Any]] = None
    pilier_2_profil_client: Optional[Dict[str, Any]] = None
    pilier_3_hospitalite_care: Optional[Dict[str, Any]] = None
    pilier_4_action_business: Optional[Dict[str, Any]] = None
    
    processed_text: Optional[str] = None
    original_text: Optional[str] = None
    processing_time_ms: float
    profile: Optional[str] = None
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)
    fallbacks_applied: List[str] = Field(default_factory=list)
    quality_gate_passed: bool = True
    quality_gate_reason: Optional[str] = None
    cache_hit: bool = False
    model_used: Optional[str] = None

    @field_validator('tags', mode='before')
    @classmethod
    def normalize_tags(cls, v: Any) -> List[str]:
        return _to_string_list(v)


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
