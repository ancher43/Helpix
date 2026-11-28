from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from app.core.database import get_db
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.search_log import SearchLog
from app.schemas.user import (
    UserCreate, UserResponse, Token, LoginRequest, 
    ProfileUpdate, PasswordChangeRequest, UserActivityStats
)
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
        position=user_in.position,
        department=user_in.department,
        phone=user_in.phone,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.from_orm_with_short_name(new_user)

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(or_(User.username == login_data.username, User.email == login_data.username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь заблокирован")

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.from_orm_with_short_name(user))

@router.post("/token", response_model=Token)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 compatible token login for Swagger UI."""
    stmt = select(User).where(or_(User.username == form_data.username, User.email == form_data.username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    
    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, token_type="bearer", user=UserResponse.from_orm_with_short_name(user))

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_required_current_user)):
    return UserResponse.from_orm_with_short_name(current_user)

@router.put("/me", response_model=UserResponse)
async def update_me(
    profile_in: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_current_user)
):
    """Update profile data of currently logged in user."""
    if profile_in.email is not None and profile_in.email != current_user.email:
        # Check uniqueness of email
        stmt = select(User).where(User.email == profile_in.email, User.id != current_user.id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Этот email уже используется другим сотрудником")
        current_user.email = profile_in.email

    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name
    if profile_in.phone is not None:
        current_user.phone = profile_in.phone
    if profile_in.position is not None:
        current_user.position = profile_in.position
    if profile_in.department is not None:
        current_user.department = profile_in.department

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.from_orm_with_short_name(current_user)

@router.put("/change-password")
async def change_password(
    pwd_in: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_current_user)
):
    """Change password for current user."""
    if not verify_password(pwd_in.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверно указан текущий пароль")
    if len(pwd_in.new_password) < 4:
        raise HTTPException(status_code=400, detail="Новый пароль должен содержать не менее 4 символов")

    current_user.hashed_password = get_password_hash(pwd_in.new_password)
    await db.commit()
    return {"status": "ok", "message": "Пароль успешно изменен"}

@router.get("/me/activity", response_model=UserActivityStats)
async def get_my_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_current_user)
):
    """Get activity metrics, recent searches, and created articles for the current user."""
    # 1. Searches by this operator
    search_stmt = (
        select(SearchLog)
        .where(SearchLog.operator_id == current_user.id)
        .order_by(desc(SearchLog.timestamp))
    )
    search_res = await db.execute(search_stmt)
    user_searches = search_res.scalars().all()
    
    total_searches = len(user_searches)
    helpful_searches = sum(1 for s in user_searches if s.is_helpful is True)
    gap_searches = sum(1 for s in user_searches if s.is_search_gap is True or s.is_helpful is False)
    success_rate = round((helpful_searches / total_searches * 100), 1) if total_searches > 0 else 0.0
    
    recent_searches_list = [
        {
            "id": s.id,
            "query_text": s.query_text,
            "search_type": s.search_type,
            "is_helpful": s.is_helpful,
            "is_search_gap": s.is_search_gap,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None
        }
        for s in user_searches[:15]
    ]

    # 2. Articles created or edited by this user
    art_stmt = (
        select(Article)
        .where(or_(Article.created_by_id == current_user.id, Article.updated_by_id == current_user.id))
        .order_by(desc(Article.updated_at))
    )
    art_res = await db.execute(art_stmt)
    user_articles = art_res.scalars().all()
    
    recent_articles_list = [
        {
            "id": a.id,
            "title": a.title,
            "views_count": a.views_count,
            "helpful_count": a.helpful_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None
        }
        for a in user_articles[:15]
    ]

    return UserActivityStats(
        total_searches=total_searches,
        helpful_searches=helpful_searches,
        gap_searches=gap_searches,
        success_rate=success_rate,
        articles_created=len(user_articles),
        recent_searches=recent_searches_list,
        recent_articles=recent_articles_list
    )
