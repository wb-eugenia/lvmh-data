"""
Clients router - Client search and management endpoints.
"""

from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel

from api.routers.auth import get_current_user
from api.models_sql import User, Client
from api.database import SessionLocal


router = APIRouter(prefix="/clients", tags=["Clients"])


class ClientSearchResult(BaseModel):
    id: int
    name: str
    external_client_id: Optional[str] = None
    category: str = "Regular"
    vic_status: str = "Standard"
    sentiment_score: float = 0.0
    total_interactions: int = 0


@router.get("/search")
async def search_clients(
    q: str,
    current_user: User = Depends(get_current_user),
) -> List[ClientSearchResult]:
    """
    Search clients by name or external client ID.
    Returns up to 10 results for autocomplete.
    """
    db = SessionLocal()
    try:
        query = q.strip()
        if not query or len(query) < 1:
            return []
        
        clients = (
            db.query(Client)
            .filter(
                (Client.name.ilike(f"%{query}%")) |
                (Client.external_client_id.ilike(f"%{query}%"))
            )
            .order_by(Client.total_interactions.desc())
            .limit(10)
            .all()
        )
        
        return [
            ClientSearchResult(
                id=c.id,
                name=c.name or "Client Inconnu",
                external_client_id=c.external_client_id,
                category=c.category or "Regular",
                vic_status=c.vic_status or "Standard",
                sentiment_score=c.sentiment_score or 0.0,
                total_interactions=c.total_interactions or 0,
            )
            for c in clients
        ]
    finally:
        db.close()


@router.get("/{client_id}")
async def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
) -> Optional[ClientSearchResult]:
    """
    Get client details by ID.
    """
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return None
        
        return ClientSearchResult(
            id=client.id,
            name=client.name or "Client Inconnu",
            external_client_id=client.external_client_id,
            category=client.category or "Regular",
            vic_status=client.vic_status or "Standard",
            sentiment_score=client.sentiment_score or 0.0,
            total_interactions=client.total_interactions or 0,
        )
    finally:
        db.close()
