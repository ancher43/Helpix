from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.search_log import SearchLog
from app.models.cluster import SearchGapCluster
from app.schemas.search import SearchRequest, SearchResponse, FeedbackRequest
from app.schemas.user import format_short_name
from app.services.hybrid_search import hybrid_search_service
from app.services.embedding import embedding_service
from app.api.deps import get_current_user, require_role

router = APIRouter(prefix="/search", tags=["Гибридный поиск"])

@router.post("", response_model=SearchResponse)
async def search_articles(
    search_in: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    query_text = search_in.query.strip()
    if not query_text:
        return SearchResponse(
            search_id=0,
            query="",
            search_mode=search_in.search_mode,
            results_count=0,
            execution_time_ms=0.0,
            results=[]
        )

    # 1. Execute hybrid search
    search_data = await hybrid_search_service.search(
        db=db,
        query=query_text,
        search_mode=search_in.search_mode,
        top_k=search_in.top_k,
        category_id=search_in.category_id
    )

    results = search_data["results"]
    results_count = search_data["total_found"]
    exec_time = search_data["execution_time_ms"]
    text_count = search_data.get("text_count", 0)
    semantic_count = search_data.get("semantic_count", 0)
    hybrid_count = search_data.get("hybrid_count", 0)

    # 2. Compute query embedding for gap analysis and logging
    query_emb = embedding_service.encode(query_text, normalize=True).tolist()

    # 3. Create SearchLog entry ONLY if all 3 algorithms returned 0 results
    # If even ONE algorithm has results > 0, do NOT automatically add as a gap!
    # A gap will only be automatically created if all 3 algorithms found 0 solutions,
    # or if the operator explicitly clicks "Посмотреть темы в очереди на написание" / gives feedback.
    search_log_id = 0
    is_search_gap = False
    all_three_zero = (text_count == 0 and semantic_count == 0 and hybrid_count == 0)

    if all_three_zero:
        log = SearchLog(
            query_text=query_text,
            operator_id=user.id if user else None,
            search_type=search_in.search_mode,
            results_count=0,
            execution_time_ms=exec_time,
            returned_article_ids=[],
            query_embedding=query_emb,
            is_search_gap=True,
            is_helpful=False
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        search_log_id = log.id
        is_search_gap = True

    return SearchResponse(
        search_id=search_log_id,
        query=query_text,
        search_mode=search_in.search_mode,
        results_count=results_count,
        execution_time_ms=exec_time,
        results=results,
        text_count=text_count,
        semantic_count=semantic_count,
        hybrid_count=hybrid_count,
        is_search_gap=is_search_gap
    )

@router.post("/feedback")
async def submit_search_feedback(
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    log = None
    if feedback.search_id and feedback.search_id > 0:
        stmt = select(SearchLog).where(SearchLog.id == feedback.search_id)
        log = (await db.execute(stmt)).scalar_one_or_none()
    
    # If no existing search log, create it now upon explicit operator feedback or queue button click
    if not log:
        q_text = feedback.query or ""
        if not q_text and feedback.clicked_article_id:
            art_stmt = select(Article.title).where(Article.id == feedback.clicked_article_id)
            q_text = (await db.execute(art_stmt)).scalar() or ""
        
        q_emb = embedding_service.encode(q_text, normalize=True).tolist() if q_text else None
        log = SearchLog(
            query_text=q_text,
            operator_id=user.id if user else None,
            search_type=feedback.search_mode or "hybrid",
            results_count=1 if feedback.clicked_article_id else 0,
            execution_time_ms=25.0,
            clicked_article_id=feedback.clicked_article_id,
            is_helpful=feedback.is_helpful,
            is_search_gap=(not feedback.is_helpful),
            feedback_notes=feedback.feedback_notes,
            query_embedding=q_emb
        )
        db.add(log)
    else:
        if user:
            log.operator_id = user.id
        log.is_helpful = feedback.is_helpful
        log.clicked_article_id = feedback.clicked_article_id
        log.feedback_notes = feedback.feedback_notes
        if feedback.is_helpful is True:
            log.is_search_gap = False
        elif feedback.is_helpful is False:
            log.is_search_gap = True

    # Update article helpfulness stats if an article was evaluated
    if feedback.clicked_article_id:
        art_stmt = select(Article).where(Article.id == feedback.clicked_article_id)
        article = (await db.execute(art_stmt)).scalar_one_or_none()
        if article:
            if feedback.is_helpful:
                article.helpful_count += 1
            else:
                article.unhelpful_count += 1

    await db.commit()
    await db.refresh(log)
    return {
        "search_id": log.id,
        "is_search_gap": log.is_search_gap,
        "message": "Отзыв успешно зарегистрирован"
    }

@router.get("/logs")
async def list_search_logs(
    is_gap: Optional[bool] = None,
    query: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = (
        select(
            SearchLog,
            Article.title.label("article_title"),
            SearchGapCluster.title.label("cluster_title"),
            User.full_name.label("operator_full_name"),
            User.username.label("operator_username"),
            User.position.label("operator_position")
        )
        .outerjoin(Article, SearchLog.clicked_article_id == Article.id)
        .outerjoin(SearchGapCluster, SearchLog.cluster_id == SearchGapCluster.id)
        .outerjoin(User, SearchLog.operator_id == User.id)
    )
    # Never return abandoned/empty queries that have no feedback and are not gaps
    from sqlalchemy import or_
    stmt = stmt.where(or_(SearchLog.is_helpful.is_not(None), SearchLog.is_search_gap == True))
    if is_gap is not None:
        stmt = stmt.where(SearchLog.is_search_gap == is_gap)
    if query:
        stmt = stmt.where(SearchLog.query_text.ilike(f"%{query}%"))
        
    stmt = stmt.order_by(desc(SearchLog.timestamp)).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).all()
    
    return [
        {
            "id": row[0].id,
            "query_text": row[0].query_text,
            "search_type": row[0].search_type,
            "results_count": row[0].results_count,
            "execution_time_ms": row[0].execution_time_ms,
            "is_search_gap": row[0].is_search_gap,
            "is_helpful": row[0].is_helpful,
            "clicked_article_id": row[0].clicked_article_id,
            "clicked_article_title": row[1],
            "cluster_id": row[0].cluster_id,
            "cluster_title": row[2],
            "operator_id": row[0].operator_id,
            "operator_name": format_short_name(row[3], row[4] or "Оператор"),
            "operator_full_name": row[3],
            "operator_position": row[5],
            "timestamp": row[0].timestamp.isoformat() if row[0].timestamp else None
        }
        for row in rows
    ]

@router.delete("/logs/{log_id}")
async def delete_search_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.ADMIN]))
):
    stmt = select(SearchLog).where(SearchLog.id == log_id)
    log = (await db.execute(stmt)).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Запись поискового запроса не найдена")
    
    await db.delete(log)
    await db.commit()
    return {"status": "ok", "deleted_id": log_id, "message": "Запись запроса успешно удалена"}
