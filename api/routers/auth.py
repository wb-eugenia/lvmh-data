from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from ..database import get_db, engine
from ..models_sql import Base, User
from ..auth_utils import verify_password, create_access_token, get_password_hash

# Create tables if not exist (simple migration)
Base.metadata.create_all(bind=engine)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

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

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Auto-seed Demo Users on first login if missing
    if form_data.username in ["advisor@lvmh.com", "manager@lvmh.com"]:
        existing = db.query(User).filter(User.email == form_data.username).first()
        if not existing:
            # Create on the fly
            role = "manager" if "manager" in form_data.username else "advisor"
            name = "Jean Dupont" if role == "manager" else "Sophie Martin"
            store = "Paris HQ" if role == "manager" else "Champs-Élysées"
            
            hashed = get_password_hash("lvmh")
            new_user = User(
                email=form_data.username, 
                hashed_password=hashed, 
                full_name=name, 
                role=role, 
                store=store
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
        "store": user.store
    }

@router.post("/seed")
async def seed_users(db: Session = Depends(get_db)):
    """Seed initial users for testing."""
    users = [
        {"email": "advisor@lvmh.com", "password": "lvmh", "full_name": "Sophie Martin", "role": "advisor", "store": "Champs-Élysées"},
        {"email": "manager@lvmh.com", "password": "lvmh", "full_name": "Jean Dupont", "role": "manager", "store": "Paris HQ"},
    ]
    
    created = []
    for u in users:
        db_user = db.query(User).filter(User.email == u["email"]).first()
        if not db_user:
            hashed = get_password_hash(u["password"])
            new_user = User(email=u["email"], hashed_password=hashed, full_name=u["full_name"], role=u["role"], store=u["store"])
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            created.append(new_user.email)
            
    return {"message": "Users created", "users": created}

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from jose import JWTError, jwt
    from ..auth_utils import SECRET_KEY, ALGORITHM
    
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
    return user
