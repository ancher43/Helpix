from typing import List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.search_log import SearchLog
from app.models.cluster import SearchGapCluster, ClusterStatus
from app.schemas.stats import (
    ModeratorDashboardStats, TopQueryItem, TopArticleItem,
    DailySearchStat, SearchGapLogItem
)
from app.api.deps import require_role

router = APIRouter(prefix="/stats", tags=["Аналитика и Статистика модератора"])

@router.get("/dashboard", response_model=ModeratorDashboardStats)
async def get_moderator_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    # 1. Total articles
    total_articles = (await db.execute(select(func.count(Article.id)).where(Article.is_published == True))).scalar() or 0

    # 2. Total searches & gaps
    total_searches = (await db.execute(select(func.count(SearchLog.id)))).scalar() or 0
    total_gaps = (await db.execute(select(func.count(SearchLog.id)).where(SearchLog.is_search_gap == True))).scalar() or 0
    gap_rate = round((total_gaps / total_searches * 100), 1) if total_searches > 0 else 0.0

    # 3. Clusters status counts
    active_clusters = (await db.execute(
        select(func.count(SearchGapCluster.id)).where(SearchGapCluster.status.in_([ClusterStatus.NEW, ClusterStatus.IN_PROGRESS]))
    )).scalar() or 0

    resolved_clusters = (await db.execute(
        select(func.count(SearchGapCluster.id)).where(SearchGapCluster.status == ClusterStatus.RESOLVED)
    )).scalar() or 0

    # 4. Top Queries
    from sqlalchemy import case, Integer
    gap_int = case((SearchLog.is_search_gap == True, 1), else_=0)
    top_q_stmt = select(
        SearchLog.query_text,
        func.count(SearchLog.id).label("cnt"),
        func.max(gap_int).label("is_gap")
    ).group_by(SearchLog.query_text).order_by(desc("cnt")).limit(10)
    
    top_q_rows = (await db.execute(top_q_stmt)).all()
    top_queries = [
        TopQueryItem(query=row[0], count=row[1], is_gap=bool(row[2]))
        for row in top_q_rows
    ]

    # 5. Top Articles
    top_art_stmt = select(Article).where(Article.is_published == True).order_by(desc(Article.views_count)).limit(10)
    top_art_rows = (await db.execute(top_art_stmt)).scalars().all()
    
    top_articles = []
    for a in top_art_rows:
        total_rated = a.helpful_count + a.unhelpful_count
        rate = round((a.helpful_count / total_rated * 100), 1) if total_rated > 0 else 100.0
        top_articles.append(TopArticleItem(
            id=a.id,
            title=a.title,
            views_count=a.views_count,
            helpful_count=a.helpful_count,
            unhelpful_count=a.unhelpful_count,
            helpfulness_rate=rate
        ))

    # 6. Recent Gaps with cluster title
    recent_gaps_stmt = select(
        SearchLog,
        SearchGapCluster.title.label("cluster_title")
    ).outerjoin(
        SearchGapCluster, SearchLog.cluster_id == SearchGapCluster.id
    ).where(SearchLog.is_search_gap == True).order_by(desc(SearchLog.timestamp)).limit(15)
    
    recent_gaps_rows = (await db.execute(recent_gaps_stmt)).all()
    recent_gaps = [
        SearchGapLogItem(
            id=row[0].id,
            query_text=row[0].query_text,
            timestamp=row[0].timestamp,
            results_count=row[0].results_count,
            is_helpful=row[0].is_helpful,
            cluster_title=row[1]
        )
        for row in recent_gaps_rows
    ]

    # 7. Daily search statistics (last 7 days)
    now = datetime.now(timezone.utc)
    daily_stats = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_total = (await db.execute(
            select(func.count(SearchLog.id)).where(and_(SearchLog.timestamp >= day_start, SearchLog.timestamp < day_end))
        )).scalar() or 0
        
        day_gaps = (await db.execute(
            select(func.count(SearchLog.id)).where(and_(
                SearchLog.timestamp >= day_start,
                SearchLog.timestamp < day_end,
                SearchLog.is_search_gap == True
            ))
        )).scalar() or 0

        daily_stats.append(DailySearchStat(
            date=day_start.strftime("%d.%m"),
            total_searches=day_total,
            gaps_count=day_gaps
        ))

    return ModeratorDashboardStats(
        total_articles=total_articles,
        total_searches=total_searches,
        total_gaps=total_gaps,
        gap_rate=gap_rate,
        active_clusters_count=active_clusters,
        resolved_clusters_count=resolved_clusters,
        top_queries=top_queries,
        top_articles=top_articles,
        recent_gaps=recent_gaps,
        daily_stats=daily_stats
    )
