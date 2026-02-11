import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# Secret key for JWT (must be overridden in production through env)
DEFAULT_INSECURE_SECRET = "CHANGE_ME_IN_PROD"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_INSECURE_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

logger = logging.getLogger(__name__)

if SECRET_KEY == DEFAULT_INSECURE_SECRET and os.getenv("ENV", "development").lower() == "production":
    logger.error("JWT_SECRET_KEY is not configured in production environment.")
    raise RuntimeError("JWT_SECRET_KEY must be configured in production.")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=True)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
