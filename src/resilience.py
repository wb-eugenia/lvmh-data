"""
Resilience patterns for the pipeline.
Includes decorators for safe execution, retries with backoff, and Circuit Breaker.
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Any, Type, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker pattern to prevent cascading failures.
    If failure_threshold is reached, the circuit opens for recovery_timeout seconds.
    """
    
    def __init__(self, failure_threshold: int = 15,
    recovery_timeout: int = 45):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
    
    def record_failure(self):
        """Record a failure."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"🔌 Circuit Breaker OPENED (failures: {self.failures})")
    
    def record_success(self):
        """Record a success."""
        self.failures = 0
        self.state = "CLOSED"
    
    def allow_request(self) -> bool:
        """Check if request is allowed."""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF-OPEN"
                logger.info("🔌 Circuit Breaker HALF-OPEN (testing recovery)")
                return True
            return False
            
        return True  # HALF-OPEN allows requests to test recovery


def safe_execution(default_return: Any = None, log_error: bool = True):
    """
    Decorator to catch exceptions and return a default value.
    Prevents pipeline crashes on individual note failures.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator


def retry_with_backoff(
    retries: int = 3, 
    base_delay: float = 2.0, 
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for exponential backoff retries.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        break
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Retry {attempt+1}/{retries} for {func.__name__} after {delay}s. Error: {e}")
                    await asyncio.sleep(delay)
            
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        break
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Retry {attempt+1}/{retries} for {func.__name__} after {delay}s. Error: {e}")
                    time.sleep(delay)
            
            raise last_exception
            
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
