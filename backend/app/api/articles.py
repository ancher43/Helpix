from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload, aliased
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.article import Article, Category
from app.schemas.article import (
    ArticleCreate, ArticleUpdate, ArticleResponse, ArticleListItem,
    CategoryCreate, CategoryResponse
)
from app.schemas.user import format_short_name
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
    sort_by: Optional[str] = Query("created_at"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    AuthorUser = aliased(User, name="author_user")
    EditorUser = aliased(User, name="editor_user")
    
    stmt = (
        select(
            Article,
            Category.name.label("category_name"),
            AuthorUser.full_name.label("author_full_name"),
            AuthorUser.username.label("author_username"),
            AuthorUser.position.label("author_position"),
            EditorUser.full_name.label("editor_full_name"),
            EditorUser.username.label("editor_username")
        )
        .outerjoin(Category, Article.category_id == Category.id)
        .outerjoin(AuthorUser, Article.created_by_id == AuthorUser.id)
        .outerjoin(EditorUser, Article.updated_by_id == EditorUser.id)
        .where(Article.is_published == True)
    )
    
    if category_id:
        stmt = stmt.where(Article.category_id == category_id)
        
    if sort_by in ("popular", "views"):
        stmt = stmt.order_by(Article.views_count.desc(), Article.helpful_count.desc())
    else:
        stmt = stmt.order_by(Article.created_at.desc())
        
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    
    items = []
    for row in result.all():
        art = row[0]
        cat_name = row[1]
        author_fn = row[2]
        author_un = row[3]
        author_pos = row[4]
        editor_fn = row[5]
        editor_un = row[6]
        
        author_short = format_short_name(author_fn, author_un or "Автор неизвестен")
        editor_short = format_short_name(editor_fn, editor_un or "") if editor_fn or editor_un else None
        
        items.append(ArticleListItem(
            id=art.id,
            title=art.title,
            summary=art.summary,
            tags=art.tags,
            category_name=cat_name,
            views_count=art.views_count,
            helpful_count=art.helpful_count,
            unhelpful_count=art.unhelpful_count,
            author_id=art.created_by_id,
            author_name=author_short,
            author_full_name=author_fn,
            author_position=author_pos,
            editor_name=editor_short,
            created_at=art.created_at,
            updated_at=art.updated_at
        ))
    return items

def _build_article_response(article: Article) -> ArticleResponse:
    author_short = None
    author_full = None
    author_pos = None
    editor_short = None
    
    if article.author:
        author_full = article.author.full_name
        author_short = format_short_name(article.author.full_name, article.author.username)
        author_pos = article.author.position
    if article.editor:
        editor_short = format_short_name(article.editor.full_name, article.editor.username)
        
    cat_resp = CategoryResponse.model_validate(article.category) if article.category else None
    
    return ArticleResponse(
        id=article.id,
        title=article.title,
        content=article.content,
        summary=article.summary,
        tags=article.tags,
        category_id=article.category_id,
        is_published=article.is_published,
        views_count=article.views_count,
        helpful_count=article.helpful_count,
        unhelpful_count=article.unhelpful_count,
        created_by_id=article.created_by_id,
        updated_by_id=article.updated_by_id,
        author_name=author_short,
        author_full_name=author_full,
        author_position=author_pos,
        editor_name=editor_short,
        created_at=article.created_at,
        updated_at=article.updated_at,
        category=cat_resp
    )

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.author),
            selectinload(Article.editor)
        )
        .where(Article.id == article_id)
    )
    article = (await db.execute(stmt)).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    # Increment view counter
    article.views_count += 1
    await db.commit()
    
    stmt = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.author),
            selectinload(Article.editor)
        )
        .where(Article.id == article_id)
    )
    article = (await db.execute(stmt)).scalar_one()
    return _build_article_response(article)

@router.post("", response_model=ArticleResponse)
async def create_article(
    article_in: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    # Compute vector embedding for hybrid search
    text_to_embed = f"{article_in.title}. {article_in.summary or ''} {article_in.content} {article_in.tags or ''}"
    embedding = embedding_service.encode(text_to_embed, normalize=True).tolist()

    now_utc = datetime.now(timezone.utc)
    article = Article(
        title=article_in.title,
        content=article_in.content,
        summary=article_in.summary,
        tags=article_in.tags,
        category_id=article_in.category_id,
        created_by_id=user.id,
        is_published=article_in.is_published,
        embedding=embedding,
        created_at=now_utc,
        updated_at=now_utc
    )
    db.add(article)
    await db.commit()
    
    stmt = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.author),
            selectinload(Article.editor)
        )
        .where(Article.id == article.id)
    )
    created_article = (await db.execute(stmt)).scalar_one()
    return _build_article_response(created_article)

@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    article_update: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.author),
            selectinload(Article.editor)
        )
        .where(Article.id == article_id)
    )
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

    article.updated_by_id = user.id
    article.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    stmt = (
        select(Article)
        .options(
            selectinload(Article.category),
            selectinload(Article.author),
            selectinload(Article.editor)
        )
        .where(Article.id == article.id)
    )
    updated_article = (await db.execute(stmt)).scalar_one()
    return _build_article_response(updated_article)

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
    return {"status": "ok", "deleted_id": article_id, "message": "Статья успешно удалена"}

@router.post("/{article_id}/feedback")
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
        "article_id": article_id,
        "helpful_count": article.helpful_count,
        "unhelpful_count": article.unhelpful_count
    }
