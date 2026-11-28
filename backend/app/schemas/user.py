from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel
from app.models.user import UserRole

def format_short_name(full_name: Optional[str], fallback: str = "") -> str:
    if not full_name or not full_name.strip():
        return fallback
    parts = full_name.strip().split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return full_name

class UserBase(BaseModel):
    email: str
    username: str
    full_name: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = UserRole.OPERATOR

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    short_name: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_short_name(cls, user: Any) -> "UserResponse":
        sn = format_short_name(user.full_name, user.username)
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            position=user.position,
            department=user.department,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            short_name=sn
        )

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserActivityStats(BaseModel):
    total_searches: int = 0
    helpful_searches: int = 0
    gap_searches: int = 0
    success_rate: float = 0.0
    articles_created: int = 0
    recent_searches: List[dict] = []
    recent_articles: List[dict] = []
