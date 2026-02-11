import os
from typing import Callable, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth_utils import create_access_token, get_password_hash, verify_password
from ..database import engine, get_db
from ..models_sql import Base, User

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
VALID_ROLES = {"advisor", "manager", "admin"}


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
DEFAULT_DEMO_ENABLED = "false" if APP_ENV in {"production", "prod"} else "true"
ALLOW_DEMO_ACCOUNTS = _env_flag("ALLOW_DEMO_ACCOUNTS", DEFAULT_DEMO_ENABLED)
ALLOW_SEED_ENDPOINT = _env_flag("ALLOW_SEED_ENDPOINT", "false")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "lvmh")
DEFAULT_AUTO_SCHEMA = "false" if APP_ENV in {"production", "prod"} else "true"
AUTO_CREATE_SCHEMA = _env_flag("AUTO_CREATE_SCHEMA", DEFAULT_AUTO_SCHEMA)

# Dev convenience only. In production, prefer Alembic migrations.
if AUTO_CREATE_SCHEMA:
    Base.metadata.create_all(bind=engine)


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str
    points: int
    store: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    store: Optional[str] = None


def _normalize_roles(roles: Iterable[str]) -> set[str]:
    return {
        str(role).strip().lower()
        for role in roles
        if str(role).strip()
    }


def require_roles(*allowed_roles: str) -> Callable:
    normalized_roles = _normalize_roles(allowed_roles)
    if not normalized_roles:
        raise ValueError("At least one role must be provided to require_roles().")

    async def _require(current_user: User = Depends(get_current_user)) -> User:
        current_role = str(current_user.role or "").strip().lower()
        if current_role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for role '{current_user.role}'. Required: {sorted(normalized_roles)}",
            )
        return current_user

    return _require


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Auto-seed demo users on first login if missing.
    if ALLOW_DEMO_ACCOUNTS and form_data.username in {"advisor@lvmh.com", "manager@lvmh.com", "admin@lvmh.com"}:
        existing = db.query(User).filter(User.email == form_data.username).first()
        if not existing:
            if "admin" in form_data.username:
                role = "admin"
                name = "Alexandre Admin"
                store = "Global HQ"
            elif "manager" in form_data.username:
                role = "manager"
                name = "Jean Dupont"
                store = "Paris HQ"
            else:
                role = "advisor"
                name = "Sophie Martin"
                store = "Champs-Elysees"

            hashed = get_password_hash(DEMO_PASSWORD)
            new_user = User(
                email=form_data.username,
                hashed_password=hashed,
                full_name=name,
                role=role,
                store=store,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role, "id": user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "name": user.full_name,
        "points": user.score,
        "store": user.store,
    }


@router.post("/seed")
async def seed_users(db: Session = Depends(get_db)):
    """Seed initial users for testing (upsert mode)."""
    if not ALLOW_SEED_ENDPOINT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seed endpoint disabled")

    users = [
        {
            "email": "advisor@lvmh.com",
            "password": DEMO_PASSWORD,
            "full_name": "Sophie Martin",
            "role": "advisor",
            "store": "Champs-Elysees",
        },
        {
            "email": "manager@lvmh.com",
            "password": DEMO_PASSWORD,
            "full_name": "Jean Dupont",
            "role": "manager",
            "store": "Paris HQ",
        },
        {
            "email": "admin@lvmh.com",
            "password": DEMO_PASSWORD,
            "full_name": "Alexandre Admin",
            "role": "admin",
            "store": "Global HQ",
        },
    ]

    created = []
    updated = []
    for user_payload in users:
        db_user = db.query(User).filter(User.email == user_payload["email"]).first()
        hashed = get_password_hash(user_payload["password"])
        if db_user:
            db_user.hashed_password = hashed
            db_user.full_name = user_payload["full_name"]
            db_user.role = user_payload["role"]
            db_user.store = user_payload["store"]
            updated.append(db_user.email)
        else:
            new_user = User(
                email=user_payload["email"],
                hashed_password=hashed,
                full_name=user_payload["full_name"],
                role=user_payload["role"],
                store=user_payload["store"],
            )
            db.add(new_user)
            created.append(user_payload["email"])

    db.commit()
    return {
        "message": "Users upserted",
        "created": created,
        "updated": updated,
    }


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import JWTError, jwt

    from ..auth_utils import ALGORITHM, SECRET_KEY

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    user_role = str(user.role or "").strip().lower()
    if user_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unsupported role '{user.role}'",
        )
    return user
