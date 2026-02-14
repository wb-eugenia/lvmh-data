"""
Dependency injection container for application services.
"""

from functools import lru_cache
from typing import Optional

from src.pipeline_async import AsyncPipeline


class PipelineContainer:
    """Container for managing pipeline instances."""
    
    _instance: Optional[AsyncPipeline] = None
    
    @classmethod
    def get_instance(cls, use_cache: bool = True, use_semantic_cache: bool = False, use_cross_validation: bool = True) -> AsyncPipeline:
        """Get or create pipeline singleton."""
        if cls._instance is None:
            cls._instance = AsyncPipeline(
                use_cache=use_cache,
                use_semantic_cache=use_semantic_cache,
                use_cross_validation=use_cross_validation
            )
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the pipeline instance (useful for testing)."""
        cls._instance = None


@lru_cache
def get_pipeline() -> AsyncPipeline:
    """
    Dependency injection for pipeline.
    Use this in FastAPI endpoints instead of global get_pipeline().
    """
    return PipelineContainer.get_instance()


def reset_pipeline() -> None:
    """Reset the pipeline singleton (for testing)."""
    PipelineContainer.reset()
