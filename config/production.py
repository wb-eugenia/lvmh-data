"""
Centralized configuration for the pipeline using Pydantic BaseSettings.
Handles environment variables and default values.
"""

import os
from pydantic import BaseModel, Field
from typing import Literal, Optional
from dotenv import load_dotenv

load_dotenv(override=True)


class RuntimeProfile(BaseModel):
    """Runtime profile configuration for different processing tiers"""
    name: str
    llm_provider: str = "mistral"
    llm_model: str = "mistral-small"
    max_tokens: int = 1024
    temperature: float = 0.1
    timeout: int = 30
    timeout_seconds: int = 30
    allow_cross_validation: bool = True
    save_to_cache: bool = True
    save_to_semantic_cache: bool = False
    rag_top_k: int = 5
    rag_threshold: float = 0.5
    require_non_empty_tags: bool = False
    strict_quality_gate: bool = False
    defer_non_critical_writes: bool = False  # Save notes to DB by default


class Settings(BaseModel):
    """Configuration centralisee type-safe"""
    
    # Environment
    environment: Literal['dev', 'staging', 'prod'] = 'dev'
    
    # Persistance - save notes to DB by default
    defer_non_critical_writes: bool = False  # Save notes synchronously
    
    # Pipeline Thresholds
    tier1_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    tier2_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_concurrent_notes: int = Field(default=10, ge=1, le=50)
    max_concurrent_tier2_calls: int = Field(default=10, ge=1, le=50)
    max_concurrent_tier3_calls: int = Field(default=5, ge=1, le=20)
    processing_timeout_seconds: int = Field(default=60, ge=5, le=300)
    
    # Pipeline Options
    use_cache: bool = True
    use_semantic_cache: bool = False
    use_cross_validation: bool = False
    use_note_validation: bool = False
    
    # LangExtract Configuration (Tier 2)
    use_langextract_tier2: bool = True  # Use LangExtract for Tier 2 extraction
    
    # Profiles
    single_note_profile: Optional[RuntimeProfile] = None
    batch_csv_profile: Optional[RuntimeProfile] = None
    fast_batch_profile: Optional[RuntimeProfile] = None
    
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
    
    # Cache Configuration
    cache_enabled: bool = True
    cache_dir: str = "cache/pipeline_v2"
    cache_ttl_seconds: int = 86400
    cache_key_salt: str = Field(default="lvmh-v3-salt")
    
    # Monitoring
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'
    enable_json_logs: bool = True
    
    # Error Handling
    retry_max_attempts: int = 3
    retry_exponential_base: float = 2.0
    circuit_breaker_threshold: int = 5
    
    # BigQuery Configuration
    bigquery_enabled: bool = Field(default_factory=lambda: os.getenv("BIGQUERY_ENABLED", "false").lower() == "true")
    bigquery_project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    bigquery_dataset: str = Field(default="lvmh_data")
    bigquery_table: str = Field(default="notes")
    bigquery_credentials_path: str = Field(default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
    
    # Router Configuration
    router_tier1_threshold: int = Field(default=25)
    router_tier2_threshold: int = Field(default=75)
    router_is_written_mode: bool = Field(default=False)
    
    # RGPD Configuration
    enable_rgpd_llm: bool = Field(default=False)
    rgpd_model: str = Field(default="mistral")
    
    # Router Feedback
    enable_router_feedback_learning: bool = Field(default=False)
    
    # Note Validation
    use_note_validation: bool = Field(default=False)
    
    # Runtime profiles
    single_note_profile: RuntimeProfile = Field(default_factory=lambda: RuntimeProfile(
        name="single_note",
        llm_provider="mistral",
        llm_model="mistral-small",
        max_tokens=1024,
        temperature=0.1,
        timeout=30,
        allow_cross_validation=True,
    ))
    
    batch_csv_profile: RuntimeProfile = Field(default_factory=lambda: RuntimeProfile(
        name="batch_csv",
        llm_provider="mistral",
        llm_model="mistral-small",
        max_tokens=512,
        temperature=0.1,
        timeout=60,
        allow_cross_validation=False,
    ))
    
    fast_batch_profile: RuntimeProfile = Field(default_factory=lambda: RuntimeProfile(
        name="fast_batch",
        llm_provider="mistral",
        llm_model="mistral-small",
        max_tokens=256,
        temperature=0.1,
        timeout=15,
        allow_cross_validation=False,
    ))


# Singleton instance
settings = Settings()
