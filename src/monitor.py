"""
Monitoring and Observability module.
Uses structlog for JSON logging and tracks real-time pipeline metrics.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional

import structlog
from config.production import settings

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.enable_json_logs else structlog.processors.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class PipelineMetrics:
    """
    Real-time metrics tracking for the pipeline.
    """
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics = {
            'notes_processed': 0,
            'notes_success': 0,
            'notes_failed': 0,
            'notes_cached': 0,
            'tier1_count': 0,
            'tier2_count': 0,
            'tier3_count': 0,
            'total_processing_time_ms': 0,
            'errors_by_type': {}
        }
    
    def record_note(
        self, 
        tier: int, 
        success: bool, 
        processing_time_ms: float,
        cached: bool = False
    ):
        """Record a processed note."""
        self.metrics['notes_processed'] += 1
        
        if success:
            self.metrics['notes_success'] += 1
        else:
            self.metrics['notes_failed'] += 1
        
        if cached:
            self.metrics['notes_cached'] += 1
        
        tier_key = f'tier{tier}_count'
        if tier_key in self.metrics:
            self.metrics[tier_key] += 1
            
        self.metrics['total_processing_time_ms'] += processing_time_ms
    
    def record_error(self, error_type: str):
        """Record an error type."""
        if error_type not in self.metrics['errors_by_type']:
            self.metrics['errors_by_type'][error_type] = 0
        self.metrics['errors_by_type'][error_type] += 1
    
    def get_summary(self) -> Dict:
        """Get metrics summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        processed = max(1, self.metrics['notes_processed'])
        
        return {
            **self.metrics,
            'elapsed_seconds': round(elapsed, 2),
            'throughput_notes_per_sec': round(self.metrics['notes_processed'] / max(1, elapsed), 2),
            'avg_processing_time_ms': round(self.metrics['total_processing_time_ms'] / processed, 2),
            'success_rate': round(self.metrics['notes_success'] / processed * 100, 1),
            'cache_hit_rate': round(self.metrics['notes_cached'] / processed * 100, 1),
            'tier_distribution': {
                'tier1': round(self.metrics['tier1_count'] / processed * 100, 1),
                'tier2': round(self.metrics['tier2_count'] / processed * 100, 1),
                'tier3': round(self.metrics['tier3_count'] / processed * 100, 1)
            }
        }
    
    def log_summary(self):
        """Log summary to structlog."""
        summary = self.get_summary()
        logger.info("pipeline_summary", **summary)
    
    def export_json(self, filepath: str):
        """Export metrics to JSON file."""
        summary = self.get_summary()
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.error("failed_to_export_metrics", error=str(e))

# Singleton instance for global access if needed
metrics = PipelineMetrics()
