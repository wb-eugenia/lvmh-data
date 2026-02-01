from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, JSON, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = "sqlite:///./lvmh_store.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(String, primary_key=True, index=True) # e.g., "PARIS_RIVOLI"
    location = Column(String)
    daily_goal = Column(Integer, default=50)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True) # e.g., "CA_001"
    full_name = Column(String)
    hashed_password = Column(String)
    role = Column(String) # "CA", "Manager", "Admin"
    store_id = Column(String, ForeignKey("stores.id"))
    
    # store = relationship("Store", back_populates="users")

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(String, primary_key=True, index=True)
    advisor_id = Column(String, ForeignKey("users.id"))
    store_id = Column(String, ForeignKey("stores.id"))
    transcription = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Analysis Data
    meta_analysis = Column(JSON) # Sentiment, Feedback, Quality Score
    pilier_1 = Column(JSON) # Univers Produit
    pilier_2 = Column(JSON) # Intention
    pilier_3 = Column(JSON) # Contexte
    pilier_4 = Column(JSON) # Next Best Action
    
    tier = Column(Integer)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed Initial Data if empty
    db = SessionLocal()
    if not db.query(Store).first():
        rivoli = Store(id="PARIS_RIVOLI", location="Paris, France", daily_goal=100)
        db.add(rivoli)
        
        # Default Users
        # Password: "password"
        pwd_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW" 
        
        ca1 = User(id="CA_001", full_name="Aurélie Dupont", role="CA", store_id="PARIS_RIVOLI", hashed_password=pwd_hash)
        mgr1 = User(id="MGR_001", full_name="Jean-Pierre Manager", role="Manager", store_id="PARIS_RIVOLI", hashed_password=pwd_hash)
        
        db.add_all([ca1, mgr1])
        db.commit()
    db.close()
