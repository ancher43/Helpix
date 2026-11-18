from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User
from app.models.article import Article
from app.models.search_log import SearchLog
from app.schemas.search import SearchRequest, SearchResponse, FeedbackRequest
from app.services.hybrid_search import hybrid_search_service
from app.services.embedding import embedding_service
from app.api.deps import get_current_user

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
        category_id=search_in.category_id,
        language=search_in.language
    )

    results = search_data["results"]
    results_count = search_data["total_found"]
    exec_time = search_data["execution_time_ms"]

    # 2. Compute query embedding for gap analysis and logging
    query_emb = embedding_service.encode(query_text, normalize=True).tolist()

    # 3. Create SearchLog entry
    # Automatically flag as search gap if 0 results were found
    is_gap = (results_count == 0)
    
    returned_ids = [r["id"] for r in results]
    log = SearchLog(
        query_text=query_text,
        operator_id=user.id if user else None,
        search_type=search_in.search_mode,
        results_count=results_count,
        execution_time_ms=exec_time,
        returned_article_ids=returned_ids,
        query_embedding=query_emb,
        is_search_gap=is_gap
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return SearchResponse(
        search_id=log.id,
        query=query_text,
        search_mode=search_in.search_mode,
        results_count=results_count,
        execution_time_ms=exec_time,
        results=results
    )

@router.post("/feedback")
async def submit_search_feedback(
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SearchLog).where(SearchLog.id == feedback.search_id)
    log = (await db.execute(stmt)).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Запись поиска не найдена")

    log.is_helpful = feedback.is_helpful
    log.clicked_article_id = feedback.clicked_article_id
    log.feedback_notes = feedback.feedback_notes

    # Requirement #2: If the operator indicates the answer did not help,
    # mark this query as a search gap even if results were > 0!
    if feedback.is_helpful is False:
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
    return {
        "search_id": log.id,
        "is_search_gap": log.is_search_gap,
        "message": "Отзыв успешно зарегистрирован"
    }
