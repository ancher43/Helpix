from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.cluster import SearchGapCluster, ClusterStatus
from app.models.search_log import SearchLog
from app.schemas.cluster import ClusterResponse, ClusterUpdate, ClusteringRunResponse
from app.api.deps import require_role
from app.services.clustering import clustering_service

router = APIRouter(prefix="/gaps", tags=["Анализ пробелов и Кластеризация"])

@router.get("/clusters", response_model=List[ClusterResponse])
async def list_clusters(
    status_filter: Optional[ClusterStatus] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = select(SearchGapCluster)
    if status_filter:
        stmt = stmt.where(SearchGapCluster.status == status_filter)
    stmt = stmt.order_by(desc(SearchGapCluster.query_count), desc(SearchGapCluster.created_at))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/clusterize", response_model=ClusteringRunResponse)
async def trigger_clustering(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    """Run NLP clustering on all unaddressed search gap logs."""
    result = await clustering_service.cluster_unaddressed_gaps(db)
    return ClusteringRunResponse(**result)

@router.put("/clusters/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    cluster_in: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = select(SearchGapCluster).where(SearchGapCluster.id == cluster_id)
    cluster = (await db.execute(stmt)).scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    update_data = cluster_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(cluster, field, val)

    await db.commit()
    await db.refresh(cluster)
    return cluster

@router.get("/unassigned-gaps")
async def list_unassigned_gaps(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    stmt = select(SearchLog).where(
        SearchLog.is_search_gap == True,
        SearchLog.cluster_id == None
    ).order_by(desc(SearchLog.timestamp)).limit(limit)
    
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [{
        "id": l.id,
        "query_text": l.query_text,
        "results_count": l.results_count,
        "is_helpful": l.is_helpful,
        "timestamp": l.timestamp
    } for l in logs]
