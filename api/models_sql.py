from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('advisor', 'manager', 'admin')",
            name="ck_users_role_valid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String, nullable=False, default="advisor") # "advisor", "manager", "admin"
    score = Column(Integer, default=0)
    store = Column(String, nullable=True)

    notes = relationship("Note", back_populates="advisor")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    vic_status = Column(String, default="Standard") # Standard, VIC, Ultimate
    total_spent = Column(Float, default=0.0)

    notes = relationship("Note", back_populates="client")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    advisor_id = Column(Integer, ForeignKey("users.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))

    transcription = Column(Text)
    analysis_json = Column(Text) # Stored as JSON string
    points_awarded = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    advisor = relationship("User", back_populates="notes")
    client = relationship("Client", back_populates="notes")
    opportunity_action = relationship("OpportunityAction", back_populates="note", uselist=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(String, index=True)
    advisor_id = Column(String, nullable=True)
    original_text = Column(Text, nullable=False)
    predicted_tags_json = Column(Text, default="[]")
    corrected_tags_json = Column(Text, default="[]")
    corrections_json = Column(Text, default="{}")
    rating = Column(Integer, default=3)
    comment = Column(Text, nullable=True)
    processing_tier = Column(Integer, default=1)
    actual_tier = Column(Integer, nullable=True)
    routing_correct = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OpportunityAction(Base):
    __tablename__ = "opportunity_actions"
    __table_args__ = (
        UniqueConstraint("note_id", name="uq_opportunity_actions_note"),
        CheckConstraint(
            "status IN ('open', 'planned', 'done')",
            name="ck_opportunity_actions_status_valid",
        ),
        CheckConstraint(
            "action_type IN ('open', 'call', 'schedule', 'assign', 'other')",
            name="ck_opportunity_actions_type_valid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=False, index=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False, default="open")
    status = Column(String, nullable=False, default="open")
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note = relationship("Note", back_populates="opportunity_action")
    manager = relationship("User")
