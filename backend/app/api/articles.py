from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.article import Article, Category
from app.schemas.article import (
    ArticleCreate, ArticleUpdate, ArticleResponse, ArticleListItem,
    CategoryCreate, CategoryResponse
)
from app.api.deps import get_required_current_user, require_role
from app.services.embedding import embedding_service

router = APIRouter(prefix="/articles", tags=["База знаний: Статьи и Категории"])

# ============ КАТЕГОРИИ ============

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()

@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = select(Category).where(Category.slug == category_in.slug)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Категория с таким slug уже существует")
        
    category = Category(
        name=category_in.name,
        slug=category_in.slug,
        description=category_in.description
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

# ============ СТАТЬИ ============

@router.get("", response_model=List[ArticleListItem])
async def list_articles(
    category_id: Optional[int] = None,
    language: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(
        Article,
        Category.name.label("category_name")
    ).outerjoin(Category, Article.category_id == Category.id).where(Article.is_published == True)
    
    if category_id:
        stmt = stmt.where(Article.category_id == category_id)
    if language:
        stmt = stmt.where(Article.language == language)
        
    stmt = stmt.order_by(Article.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    
    items = []
    for row in result.all():
        art = row[0]
        cat_name = row[1]
        items.append(ArticleListItem(
            id=art.id,
            title=art.title,
            summary=art.summary,
            tags=art.tags,
            language=art.language,
            category_name=cat_name,
            views_count=art.views_count,
            helpful_count=art.helpful_count,
            unhelpful_count=art.unhelpful_count,
            created_at=art.created_at
        ))
    return items

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Article).where(Article.id == article_id)
    article = (await db.execute(stmt)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    # Increment view counter
    article.views_count += 1
    await db.commit()
    await db.refresh(article)
    return article

@router.post("", response_model=ArticleResponse)
async def create_article(
    article_in: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    # Compute vector embedding for hybrid search
    text_to_embed = f"{article_in.title}. {article_in.summary or ''} {article_in.content} {article_in.tags or ''}"
    embedding = embedding_service.encode(text_to_embed, normalize=True).tolist()

    article = Article(
        title=article_in.title,
        content=article_in.content,
        summary=article_in.summary,
        tags=article_in.tags,
        language=article_in.language,
        category_id=article_in.category_id,
        created_by_id=user.id,
        is_published=article_in.is_published,
        embedding=embedding
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article

@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    article_update: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = select(Article).where(Article.id == article_id)
    article = (await db.execute(stmt)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    update_data = article_update.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(article, field, val)

    # Re-calculate embedding if text content changed
    if any(k in update_data for k in ["title", "content", "summary", "tags"]):
        text_to_embed = f"{article.title}. {article.summary or ''} {article.content} {article.tags or ''}"
        article.embedding = embedding_service.encode(text_to_embed, normalize=True).tolist()

    await db.commit()
    await db.refresh(article)
    return article

@router.delete("/{article_id}")
async def delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.ADMIN]))
):
    stmt = select(Article).where(Article.id == article_id)
    article = (await db.execute(stmt)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
        
    await db.delete(article)
    await db.commit()
    return {"message": "Статья успешно удалена"}

@router.post("/{article_id}/rate")
async def rate_article(
    article_id: int,
    helpful: bool = Query(...),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Article).where(Article.id == article_id)
    article = (await db.execute(stmt)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")
        
    if helpful:
        article.helpful_count += 1
    else:
        article.unhelpful_count += 1
        
    await db.commit()
    return {
        "article_id": article.id,
        "helpful_count": article.helpful_count,
        "unhelpful_count": article.unhelpful_count
    }
