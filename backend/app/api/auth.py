from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.core.database import get_db
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, Token, LoginRequest
from app.api.deps import get_required_current_user

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    stmt = select(User).where(or_(User.email == user_in.email, User.username == user_in.username))
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email или логином уже зарегистрирован")

    new_user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(or_(User.username == login_data.username, User.email == login_data.username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь заблокирован")

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.model_validate(user))

@router.post("/token", response_model=Token)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 compatible token login for Swagger UI."""
    stmt = select(User).where(or_(User.username == form_data.username, User.email == form_data.username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    
    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.model_validate(user))

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_required_current_user)):
    return current_user
