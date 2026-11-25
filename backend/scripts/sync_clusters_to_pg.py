import sys
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

sys.path.insert(0, 'backend')
from app.models.cluster import SearchGapCluster, ClusterStatus
from app.models.search_log import SearchLog

async def sync():
    sqlite_engine = create_async_engine("sqlite+aiosqlite:///backend/local_vkr.db")
    pg_engine = create_async_engine("postgresql+asyncpg://postgres:123@localhost:5432/vkr_knowledge_base")

    async_sqlite = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    async_pg = async_sessionmaker(pg_engine, expire_on_commit=False)

    async with async_sqlite() as s_db:
        res_c = await s_db.execute(select(SearchGapCluster))
        sqlite_clusters = res_c.scalars().all()

        res_l = await s_db.execute(select(SearchLog).where(SearchLog.cluster_id.is_not(None)))
        sqlite_logs = res_l.scalars().all()

    print(f"Read from SQLite: {len(sqlite_clusters)} clusters, {len(sqlite_logs)} clustered logs.")

    async with async_pg() as p_db:
        for c in sqlite_clusters:
            # Check if exists
            existing = (await p_db.execute(select(SearchGapCluster).where(SearchGapCluster.id == c.id))).scalar_one_or_none()
            if not existing:
                new_c = SearchGapCluster(
                    id=c.id,
                    title=c.title,
                    description=c.description,
                    query_count=c.query_count,
                    sample_queries=c.sample_queries,
                    keywords=c.keywords,
                    pca_x=c.pca_x,
                    pca_y=c.pca_y,
                    pca_z=c.pca_z,
                    status=c.status,
                    created_article_id=c.created_article_id,
                    created_at=c.created_at,
                    updated_at=c.updated_at
                )
                p_db.add(new_c)
            else:
                existing.title = c.title
                existing.pca_x = c.pca_x
                existing.pca_y = c.pca_y
                existing.pca_z = c.pca_z
                existing.sample_queries = c.sample_queries
                existing.keywords = c.keywords

        await p_db.commit()

        # Update logs
        for l in sqlite_logs:
            pg_log = (await p_db.execute(select(SearchLog).where(SearchLog.id == l.id))).scalar_one_or_none()
            if pg_log:
                pg_log.cluster_id = l.cluster_id
                pg_log.query_embedding = l.query_embedding
                pg_log.is_search_gap = l.is_search_gap
            else:
                new_log = SearchLog(
                    id=l.id,
                    query_text=l.query_text,
                    operator_id=l.operator_id,
                    search_type=l.search_type,
                    results_count=l.results_count,
                    execution_time_ms=l.execution_time_ms,
                    returned_article_ids=l.returned_article_ids,
                    clicked_article_id=l.clicked_article_id,
                    is_helpful=l.is_helpful,
                    feedback_notes=l.feedback_notes,
                    is_search_gap=l.is_search_gap,
                    cluster_id=l.cluster_id,
                    query_embedding=l.query_embedding,
                    timestamp=l.timestamp
                )
                p_db.add(new_log)

        await p_db.commit()
        print("Successfully synced clusters and logs to PostgreSQL!")

if __name__ == "__main__":
    asyncio.run(sync())
