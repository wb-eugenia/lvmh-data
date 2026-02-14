"""
GraphQL schema and resolvers for LVMH API.
"""

import strawberry
from typing import List, Optional
from datetime import datetime
import json

from api.database import SessionLocal
from api.models_sql import User, Note, Client


@strawberry.type
class UserType:
    id: int
    email: str
    full_name: Optional[str]
    role: str
    score: int
    store: Optional[str]


@strawberry.type
class ClientType:
    id: int
    name: str
    vic_status: str
    total_spent: float


@strawberry.type
class NoteType:
    id: int
    transcription: Optional[str]
    points_awarded: int
    timestamp: datetime
    analysis_json: Optional[str]
    
    @strawberry.field
    def analysis(self) -> dict:
        if self.analysis_json:
            try:
                return json.loads(self.analysis_json)
            except:
                pass
        return {}
    
    @strawberry.field
    def tier(self) -> int:
        return self.analysis().get('routing', {}).get('tier', 1)
    
    @strawberry.field
    def tags(self) -> List[str]:
        return self.analysis().get('extraction', {}).get('tags', [])


@strawberry.type
class StatsType:
    total_notes: int
    total_users: int
    total_clients: int
    avg_quality: float
    tier_distribution: dict


@strawberry.type
class Query:
    @strawberry.field
    def users(self, role: Optional[str] = None, limit: int = 50) -> List[UserType]:
        db = SessionLocal()
        try:
            query = db.query(User)
            if role:
                query = query.filter(User.role == role)
            return [UserType(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                score=u.score,
                store=u.store
            ) for u in query.limit(limit).all()]
        finally:
            db.close()
    
    @strawberry.field
    def clients(self, vic_status: Optional[str] = None, limit: int = 50) -> List[ClientType]:
        db = SessionLocal()
        try:
            query = db.query(Client)
            if vic_status:
                query = query.filter(Client.vic_status == vic_status)
            return [ClientType(
                id=c.id,
                name=c.name,
                vic_status=c.vic_status,
                total_spent=c.total_spent
            ) for c in query.limit(limit).all()]
        finally:
            db.close()
    
    @strawberry.field
    def notes(self, 
              advisor_id: Optional[int] = None,
              client_id: Optional[int] = None,
              limit: int = 50) -> List[NoteType]:
        db = SessionLocal()
        try:
            query = db.query(Note)
            if advisor_id:
                query = query.filter(Note.advisor_id == advisor_id)
            if client_id:
                query = query.filter(Note.client_id == client_id)
            return [NoteType(
                id=n.id,
                transcription=n.transcription,
                points_awarded=n.points_awarded,
                timestamp=n.timestamp,
                analysis_json=n.analysis_json
            ) for n in query.order_by(Note.timestamp.desc()).limit(limit).all()]
        finally:
            db.close()
    
    @strawberry.field
    def note(self, id: int) -> Optional[NoteType]:
        db = SessionLocal()
        try:
            n = db.query(Note).filter(Note.id == id).first()
            if n:
                return NoteType(
                    id=n.id,
                    transcription=n.transcription,
                    points_awarded=n.points_awarded,
                    timestamp=n.timestamp,
                    analysis_json=n.analysis_json
                )
            return None
        finally:
            db.close()
    
    @strawberry.field
    def stats(self) -> StatsType:
        db = SessionLocal()
        try:
            total_notes = db.query(Note).count()
            total_users = db.query(User).count()
            total_clients = db.query(Client).count()
            
            notes = db.query(Note).all()
            total_points = sum(n.points_awarded or 0 for n in notes)
            avg_quality = (total_points / total_notes / 15) * 100 if total_notes > 0 else 0
            
            tier_dist = {1: 0, 2: 0, 3: 0}
            for n in notes:
                try:
                    data = json.loads(n.analysis_json) if n.analysis_json else {}
                    tier = data.get('routing', {}).get('tier', 1)
                    tier_dist[tier] = tier_dist.get(tier, 0) + 1
                except:
                    pass
            
            return StatsType(
                total_notes=total_notes,
                total_users=total_users,
                total_clients=total_clients,
                avg_quality=round(avg_quality, 1),
                tier_distribution=tier_dist
            )
        finally:
            db.close()


schema = strawberry.Schema(query=Query)
