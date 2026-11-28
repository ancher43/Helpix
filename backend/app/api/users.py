from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.search_log import SearchLog
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserActivityStats
from app.api.deps import require_role, get_required_current_user

router = APIRouter(prefix="/users", tags=["Управление сотрудниками"])

@router.get("", response_model=List[UserResponse])
async def list_users(
    query: Optional[str] = None,
    role: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MODERATOR]))
):
    """List all employees/users with search and role filtering."""
    stmt = select(User)
    
    if role and role in [r.value for r in UserRole]:
        stmt = stmt.where(User.role == UserRole(role))
        
    if query:
        q = f"%{query}%"
        stmt = stmt.where(
            or_(
                User.full_name.ilike(q),
                User.username.ilike(q),
                User.email.ilike(q),
                User.position.ilike(q),
                User.department.ilike(q)
            )
        )
        
    stmt = stmt.order_by(User.id).offset(skip).limit(limit)
    res = await db.execute(stmt)
    users = res.scalars().all()
    
    return [UserResponse.from_orm_with_short_name(u) for u in users]

@router.post("", response_model=UserResponse)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Create a new employee/user (Administrator only)."""
    # Check if username or email exists
    stmt = select(User).where(or_(User.email == user_in.email, User.username == user_in.username))
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Сотрудник с таким email или логином уже зарегистрирован")
        
    new_user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        position=user_in.position,
        department=user_in.department,
        phone=user_in.phone,
        role=user_in.role,
        hashed_password=get_password_hash(user_in.password),
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse.from_orm_with_short_name(new_user)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MODERATOR]))
):
    """Get details of a specific employee."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return UserResponse.from_orm_with_short_name(user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Update employee details, role, status, or reset password (Administrator only)."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
        
    if user_in.email is not None and user_in.email != user.email:
        existing = (await db.execute(select(User).where(User.email == user_in.email, User.id != user_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Этот email уже занят другим сотрудником")
        user.email = user_in.email
        
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.position is not None:
        user.position = user_in.position
    if user_in.department is not None:
        user.department = user_in.department
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.is_active is not None:
        # Prevent self-deactivation
        if user.id == current_user.id and user_in.is_active is False:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать собственную учетную запись администратора")
        user.is_active = user_in.is_active
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)
        
    await db.commit()
    await db.refresh(user)
    return UserResponse.from_orm_with_short_name(user)

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Deactivate or remove employee (Administrator only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственную учетную запись")
        
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
        
    # Soft delete / deactivation preferred to maintain logs and articles integrity
    user.is_active = False
    await db.commit()
    return {"status": "ok", "message": f"Сотрудник {user.full_name or user.username} успешно деактивирован"}

@router.get("/{user_id}/activity", response_model=UserActivityStats)
async def get_user_activity(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.MODERATOR]))
):
    """Get activity metrics and history of a specific user."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
        
    # 1. Searches
    search_stmt = (
        select(SearchLog)
        .where(SearchLog.operator_id == user.id)
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

    # 2. Articles
    art_stmt = (
        select(Article)
        .where(or_(Article.created_by_id == user.id, Article.updated_by_id == user.id))
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
