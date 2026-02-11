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

APP_ENV = os.getenv("ENV", os.getenv("APP_ENV", os.getenv("PYTHON_ENV", "development"))).lower()
IS_PROD_LIKE = APP_ENV in {"production", "prod", "staging"}

if IS_PROD_LIKE and (not SECRET_KEY or SECRET_KEY == DEFAULT_INSECURE_SECRET):
    logger.error("JWT_SECRET_KEY is not configured in %s environment.", APP_ENV)
    raise RuntimeError("JWT_SECRET_KEY must be configured in production-like environments.")

if IS_PROD_LIKE and len(SECRET_KEY) < 32:
    logger.error("JWT_SECRET_KEY is too short for %s environment.", APP_ENV)
    raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters in production-like environments.")

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
