"""
Circuit Breaker implementation for external API calls.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("lvmh-api.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    half_open_max_calls: int = 3


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, message: str, circuit_state: CircuitState):
        super().__init__(message)
        self.circuit_state = circuit_state


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external API calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def is_available(self) -> bool:
        return self._state != CircuitState.OPEN
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback: Any = None,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.
        Returns fallback if circuit is open.
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                else:
                    logger.warning(f"Circuit breaker '{self.name}' is OPEN, rejecting call")
                    if fallback is not None:
                        return fallback
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is open",
                        self._state
                    )
            
            # Check HALF_OPEN limit
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(f"Circuit breaker '{self.name}' HALF_OPEN limit reached")
                    if fallback is not None:
                        return fallback
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' half-open limit reached",
                        self._state
                    )
                self._half_open_calls += 1
        
        # Execute the function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure()
            if fallback is not None:
                logger.warning(f"Circuit breaker '{self.name}' call failed, returning fallback: {e}")
                return fallback
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.config.timeout_seconds
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' CLOSED (recovered)")
            else:
                # Reset failure count on success in CLOSED state
                self._failure_count = 0
    
    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN goes back to OPEN
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(f"Circuit breaker '{self.name}' OPEN (half-open test failed)")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' OPEN (failure threshold reached)")
    
    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time,
        }
    
    async def reset(self) -> None:
        """Manually reset the circuit breaker."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]
    
    def get_all_states(self) -> list[dict]:
        return [breaker.get_state() for breaker in self._breakers.values()]
    
    async def reset_all(self) -> None:
        for breaker in self._breakers.values():
            await breaker.reset()


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()

# Pre-configured circuit breakers
def get_tier2_circuit_breaker() -> CircuitBreaker:
    return circuit_breaker_manager.get_or_create(
        "tier2_mistral",
        CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=30.0
        )
    )

def get_tier3_circuit_breaker() -> CircuitBreaker:
    return circuit_breaker_manager.get_or_create(
        "tier3_openai",
        CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60.0
        )
    )

def get_rgpd_circuit_breaker() -> CircuitBreaker:
    return circuit_breaker_manager.get_or_create(
        "rgpd_llm",
        CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=1,
            timeout_seconds=30.0
        )
    )
