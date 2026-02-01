"""
Mock LVMH SSO & RBAC for UI demo.
"""
from typing import Optional, List
from pydantic import BaseModel
from fastapi import Header, HTTPException

class UserProfile(BaseModel):
    id: str
    name: str
    role: str # 'CA', 'Manager', 'Admin'
    boutique_id: str

# Mock Database
MOCK_USERS = {
    "token_aurelie": UserProfile(id="CA_001", name="Aurélie Dupont", role="CA", boutique_id="PARIS_RIVOLI"),
    "token_julien": UserProfile(id="CA_002", name="Julien Martin", role="CA", boutique_id="PARIS_RIVOLI"),
    "token_manager": UserProfile(id="MGR_001", name="Marc Lefebvre", role="Manager", boutique_id="PARIS_RIVOLI"),
}

async def get_current_user(authorization: str = Header(None)) -> UserProfile:
    """Mock dependency to get user from token"""
    if not authorization or not authorization.startswith("Bearer "):
        # For demo purposes, we fallback to Aurélie if no token
        return MOCK_USERS["token_aurelie"]
        
    token = authorization.replace("Bearer ", "")
    if token in MOCK_USERS:
        return MOCK_USERS[token]
    
    raise HTTPException(status_code=401, detail="Invalid token")

def check_role(user: UserProfile, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Permission denied")
