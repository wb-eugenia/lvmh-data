"""
Centralized configuration for the pipeline using Pydantic BaseSettings.
Handles environment variables and default values.
"""

import os
from pydantic import BaseModel, Field
from typing import Literal

class Settings(BaseModel):
    """Configuration centralisée type-safe"""
    
    # Environment
    environment: Literal['dev', 'staging', 'prod'] = 'dev'
    
    # Pipeline Thresholds
    tier1_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    tier2_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_concurrent_notes: int = Field(default=10, ge=1, le=50)
    processing_timeout_seconds: int = Field(default=60, ge=5, le=300)
    
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
    
    # Monitoring
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'
    enable_json_logs: bool = True
    
    # Error Handling
    retry_max_attempts: int = 3
    retry_exponential_base: float = 2.0
    circuit_breaker_threshold: int = 5

# Singleton instance
settings = Settings()
