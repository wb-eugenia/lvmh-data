"""
Redis client for caching and distributed operations.
"""

import os
import json
import logging
from typing import Any, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import Redis

logger = logging.getLogger("lvmh-api.redis")

_redis_client: Optional[Redis] = None


def get_redis_url() -> str:
    """Get Redis URL from environment or default."""
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def get_redis() -> Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            get_redis_url(),
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class RedisCache:
    """Redis-backed cache with TTL support."""
    
    def __init__(self, prefix: str = "lvmh", ttl: int = 3600):
        self.prefix = prefix
        self.ttl = ttl
    
    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            r = await get_redis()
            value = await r.get(self._key(key))
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            r = await get_redis()
            await r.setex(
                self._key(key),
                ttl or self.ttl,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            r = await get_redis()
            await r.delete(self._key(key))
            return True
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            r = await get_redis()
            return await r.exists(self._key(key)) > 0
        except Exception as e:
            logger.warning(f"Redis exists error: {e}")
            return False


class BatchTaskStore:
    """Redis-backed batch task storage."""
    
    TASK_PREFIX = "lvmh:batch:task:"
    TASK_TTL = 86400  # 24 hours
    
    @staticmethod
    def _key(task_id: str) -> str:
        return f"{BatchTaskStore.TASK_PREFIX}{task_id}"
    
    @classmethod
    async def save(cls, task_id: str, data: dict) -> bool:
        """Save batch task data."""
        try:
            r = await get_redis()
            await r.setex(
                cls._key(task_id),
                cls.TASK_TTL,
                json.dumps(data, default=str)
            )
            return True
        except Exception as e:
            logger.warning(f"Batch task save error: {e}")
            return False
    
    @classmethod
    async def get(cls, task_id: str) -> Optional[dict]:
        """Get batch task data."""
        try:
            r = await get_redis()
            value = await r.get(cls._key(task_id))
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Batch task get error: {e}")
        return None
    
    @classmethod
    async def delete(cls, task_id: str) -> bool:
        """Delete batch task."""
        try:
            r = await get_redis()
            await r.delete(cls._key(task_id))
            return True
        except Exception as e:
            logger.warning(f"Batch task delete error: {e}")
            return False
    
    @classmethod
    async def list_tasks(cls, pattern: str = "*") -> list[str]:
        """List all task IDs."""
        try:
            r = await get_redis()
            keys = await r.keys(f"{cls.TASK_PREFIX}{pattern}")
            return [k.replace(cls.TASK_PREFIX, "") for k in keys]
        except Exception as e:
            logger.warning(f"Batch task list error: {e}")
            return []
