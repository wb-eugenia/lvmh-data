"""
LVMH SSO & RBAC with JWT and Database Persistence.
"""
import os
from typing import Optional, List
from pydantic import BaseModel
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from src.database import SessionLocal, User

# JWT Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PROD")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 Hours
APP_ENV = os.getenv("ENV", os.getenv("APP_ENV", os.getenv("PYTHON_ENV", "development"))).lower()

if APP_ENV in {"production", "prod", "staging"} and (SECRET_KEY == "CHANGE_ME_IN_PROD" or len(SECRET_KEY) < 32):
    raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 chars in production-like environments.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserProfile(BaseModel):
    id: str
    name: str
    role: str # 'CA', 'Manager', 'Admin'
    boutique_id: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> UserProfile:
    """Validate JWT and fetch user from DB"""
    user_id = None
    
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    if not user_id:
         raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return UserProfile(
        id=user.id, 
        name=user.full_name, 
        role=user.role, 
        boutique_id=user.store_id
    )

def check_role(user: UserProfile, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Permission denied")
