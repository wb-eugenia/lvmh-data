from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String) # "advisor", "manager"
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
