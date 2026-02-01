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
