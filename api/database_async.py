"""
Async database support for SQLAlchemy.
"""

import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lvmh.db")

def _get_async_database_url(url: str) -> str:
    """Convert sync DB URL to async version."""
    if url.startswith("sqlite"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    return url

ASYNC_DATABASE_URL = _get_async_database_url(SQLALCHEMY_DATABASE_URL)

_async_engine: Optional[object] = None
_async_session_maker: Optional[object] = None

def _get_engine():
    """Lazy initialization of async engine."""
    global _async_engine, _async_session_maker
    if _async_engine is None:
        try:
            _async_engine = create_async_engine(
                ASYNC_DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
            )
            _async_session_maker = async_sessionmaker(
                _async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            import logging
            logging.getLogger("lvmh-api.async_db").warning(f"Async DB unavailable: {e}")
            _async_engine = False
            _async_session_maker = False
    if _async_engine is False:
        raise RuntimeError("Async database not available")
    return _async_engine, _async_session_maker

def get_async_session_maker():
    """Get the async session maker."""
    _, maker = _get_engine()
    return maker

Base = declarative_base()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency."""
    _, AsyncSessionLocal = _get_engine()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
