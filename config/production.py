"""
Centralized configuration for the pipeline using Pydantic BaseSettings.
Handles environment variables and default values.
"""

import os
from pydantic import BaseModel, Field
from typing import Literal


class RuntimeProfile(BaseModel):
    """Profile-level runtime tuning for the same extraction engine."""

    name: str
    rag_top_k: int = Field(default=3, ge=1, le=20)
    rag_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    save_to_cache: bool = True
    save_to_semantic_cache: bool = False
    require_non_empty_tags: bool = True
    defer_non_critical_writes: bool = False
    allow_cross_validation: bool = True
    strict_quality_gate: bool = False

class Settings(BaseModel):
    """Configuration centralisée type-safe"""
    
    # Environment
    environment: Literal['dev', 'staging', 'prod'] = 'dev'
    
    # Pipeline Thresholds
    tier1_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    tier2_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_concurrent_notes: int = Field(default=10, ge=1, le=50)
    max_concurrent_tier2_calls: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_TIER2_CALLS", "4")),
        ge=1,
        le=20
    )
    max_concurrent_tier3_calls: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_TIER3_CALLS", "6")),
        ge=1,
        le=20
    )
    processing_timeout_seconds: int = Field(default=60, ge=5, le=300)
    tier1_match_engine: str = Field(
        default_factory=lambda: (os.getenv("TIER1_MATCH_ENGINE", "aho") or "aho").strip().lower()
    )
    enable_router_feedback_learning: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ROUTER_FEEDBACK_LEARNING", "1") == "1"
    )
    
    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_max_parallel: int = Field(default=4, ge=1, le=10)
    ollama_timeout: int = 120
    
    # OpenAI Configuration
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = "gpt-4o-mini"
    openai_max_retries: int = 3
    openai_timeout: int = 30
    enable_rgpd_llm: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_RGPD_LLM", "1") == "1"
    )
    rgpd_model: str = Field(default_factory=lambda: os.getenv("RGPD_MODEL", "gpt-4o-mini"))
    
    # Cache Configuration
    cache_enabled: bool = True
    cache_dir: str = "cache/pipeline_v2"
    cache_ttl_seconds: int = 86400
    cache_key_salt: str = Field(
        default_factory=lambda: os.getenv("CACHE_KEY_SALT", "pipeline_v2.3_taxonomy_v2.2")
    )
    
    # Monitoring
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'
    enable_json_logs: bool = True
    
    # Error Handling
    retry_max_attempts: int = 3
    retry_exponential_base: float = 2.0
    circuit_breaker_threshold: int = 5

    # Performance Targets (single-note, user-facing path)
    target_single_note_p50_ms: int = Field(
        default_factory=lambda: int(os.getenv("TARGET_SINGLE_NOTE_P50_MS", "6000")),
        ge=1000,
        le=60000,
    )
    target_single_note_p95_ms: int = Field(
        default_factory=lambda: int(os.getenv("TARGET_SINGLE_NOTE_P95_MS", "12000")),
        ge=1000,
        le=120000,
    )
    target_success_rate_pct: float = Field(
        default_factory=lambda: float(os.getenv("TARGET_SUCCESS_RATE_PCT", "99.5")),
        ge=0.0,
        le=100.0,
    )
    target_quality_score: float = Field(
        default_factory=lambda: float(os.getenv("TARGET_QUALITY_SCORE", "80")),
        ge=0.0,
        le=100.0,
    )
    enable_parity_probe: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_PARITY_PROBE", "0") == "1"
    )

    # Runtime Profiles
    single_note_profile: RuntimeProfile = Field(
        default_factory=lambda: RuntimeProfile(
            name="single_note",
            rag_top_k=int(os.getenv("SINGLE_NOTE_RAG_TOP_K", "2")),
            rag_threshold=float(os.getenv("SINGLE_NOTE_RAG_THRESHOLD", "0.42")),
            timeout_seconds=int(os.getenv("SINGLE_NOTE_TIMEOUT_SECONDS", "25")),
            save_to_cache=os.getenv("SINGLE_NOTE_SAVE_TO_CACHE", "1") == "1",
            save_to_semantic_cache=os.getenv("SINGLE_NOTE_SAVE_TO_SEM_CACHE", "0") == "1",
            require_non_empty_tags=os.getenv("SINGLE_NOTE_REQUIRE_TAGS", "1") == "1",
            defer_non_critical_writes=os.getenv("SINGLE_NOTE_DEFER_WRITES", "1") == "1",
            allow_cross_validation=os.getenv("SINGLE_NOTE_ALLOW_CROSS_VALIDATION", "1") == "1",
            strict_quality_gate=os.getenv("SINGLE_NOTE_STRICT_QUALITY_GATE", "1") == "1",
        )
    )
    batch_csv_profile: RuntimeProfile = Field(
        default_factory=lambda: RuntimeProfile(
            name="batch_csv",
            rag_top_k=int(os.getenv("BATCH_RAG_TOP_K", "5")),
            rag_threshold=float(os.getenv("BATCH_RAG_THRESHOLD", "0.30")),
            timeout_seconds=int(os.getenv("BATCH_TIMEOUT_SECONDS", "90")),
            save_to_cache=os.getenv("BATCH_SAVE_TO_CACHE", "1") == "1",
            save_to_semantic_cache=os.getenv("BATCH_SAVE_TO_SEM_CACHE", "0") == "1",
            require_non_empty_tags=os.getenv("BATCH_REQUIRE_TAGS", "0") == "1",
            defer_non_critical_writes=os.getenv("BATCH_DEFER_WRITES", "0") == "1",
            allow_cross_validation=os.getenv("BATCH_ALLOW_CROSS_VALIDATION", "1") == "1",
            strict_quality_gate=os.getenv("BATCH_STRICT_QUALITY_GATE", "0") == "1",
        )
    )
    fast_batch_profile: RuntimeProfile = Field(
        default_factory=lambda: RuntimeProfile(
            name="fast_batch",
            rag_top_k=int(os.getenv("FAST_BATCH_RAG_TOP_K", "1")),
            rag_threshold=float(os.getenv("FAST_BATCH_RAG_THRESHOLD", "1.0")),
            timeout_seconds=int(os.getenv("FAST_BATCH_TIMEOUT_SECONDS", "20")),
            save_to_cache=os.getenv("FAST_BATCH_SAVE_TO_CACHE", "0") == "1",
            save_to_semantic_cache=False,
            require_non_empty_tags=False,
            defer_non_critical_writes=True,
            allow_cross_validation=False,
            strict_quality_gate=False,
        )
    )

    # Batch worker runtime
    batch_worker_count: int = Field(
        default_factory=lambda: int(os.getenv("BATCH_WORKER_COUNT", "2")),
        ge=1,
        le=16,
    )
    batch_queue_max_size: int = Field(
        default_factory=lambda: int(os.getenv("BATCH_QUEUE_MAX_SIZE", "20")),
        ge=1,
        le=1000,
    )

# Singleton instance
settings = Settings()
