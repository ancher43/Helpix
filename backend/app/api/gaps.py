from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update, delete
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.cluster import SearchGapCluster, ClusterStatus
from app.models.search_log import SearchLog
from app.models.article import Article
from app.schemas.cluster import (
    ClusterResponse, 
    ClusterUpdate, 
    ClusteringRunResponse, 
    ClusterDetailResponse, 
    ClusterQueryItem
)
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

    # Only Administrator can set status to 'resolved'
    if cluster_in.status == ClusterStatus.RESOLVED and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, 
            detail="Переводить кластер в статус «Решен» имеет право только Администратор."
        )

    from datetime import datetime, timezone
    update_data = cluster_in.model_dump(exclude_unset=True)

    # Handle resolution date
    if cluster_in.status == ClusterStatus.RESOLVED:
        cluster.resolved_at = datetime.now(timezone.utc)
    elif cluster_in.status is not None and cluster_in.status != ClusterStatus.RESOLVED:
        cluster.resolved_at = None

    for field, val in update_data.items():
        setattr(cluster, field, val)

    await db.commit()
    await db.refresh(cluster)
    return cluster

@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster_detail(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    """Retrieve full details of a cluster, including all member search queries."""
    stmt = select(SearchGapCluster).where(SearchGapCluster.id == cluster_id)
    cluster = (await db.execute(stmt)).scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    # Fetch associated queries from search_logs with operator name
    logs_stmt = (
        select(SearchLog, User.full_name)
        .outerjoin(User, SearchLog.operator_id == User.id)
        .where(SearchLog.cluster_id == cluster_id)
        .order_by(desc(SearchLog.timestamp))
    )
    res_logs = await db.execute(logs_stmt)
    query_items = []
    for log, op_name in res_logs.all():
        query_items.append(ClusterQueryItem(
            id=log.id,
            query_text=log.query_text,
            search_type=log.search_type,
            results_count=log.results_count,
            is_helpful=log.is_helpful,
            is_search_gap=log.is_search_gap,
            execution_time_ms=log.execution_time_ms or 0.0,
            timestamp=log.timestamp,
            operator_name=op_name
        ))

    created_art_title = None
    if cluster.created_article_id:
        art_stmt = select(Article.title).where(Article.id == cluster.created_article_id)
        created_art_title = (await db.execute(art_stmt)).scalar_one_or_none()

    return ClusterDetailResponse(
        id=cluster.id,
        title=cluster.title,
        description=cluster.description,
        query_count=cluster.query_count,
        sample_queries=cluster.sample_queries or [],
        keywords=cluster.keywords or [],
        pca_x=cluster.pca_x,
        pca_y=cluster.pca_y,
        pca_z=cluster.pca_z,
        status=cluster.status,
        created_article_id=cluster.created_article_id,
        resolved_at=cluster.resolved_at,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        queries=query_items,
        created_article_title=created_art_title
    )

@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.ADMIN]))
):
    """Delete a cluster. Only administrators can delete clusters. 
    Linked queries are safely unlinked (cluster_id=NULL) to preserve search history."""
    stmt = select(SearchGapCluster).where(SearchGapCluster.id == cluster_id)
    cluster = (await db.execute(stmt)).scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    cluster_title = cluster.title
    # Unlink logs before deletion so logs remain as historical records
    await db.execute(
        update(SearchLog).where(SearchLog.cluster_id == cluster_id).values(cluster_id=None)
    )
    await db.delete(cluster)
    await db.commit()
    return {"message": f"Кластер «{cluster_title}» успешно удален", "id": cluster_id}

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

@router.get("/visualization/3d")
async def get_3d_cluster_visualization(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([UserRole.MODERATOR, UserRole.ADMIN]))
):
    import numpy as np
    from sklearn.decomposition import PCA
    from app.services.embedding import embedding_service

    # Fetch clusters
    res_clusters = await db.execute(select(SearchGapCluster).order_by(SearchGapCluster.id))
    clusters = res_clusters.scalars().all()
    if not clusters:
        return {"clusters": [], "points": [], "total_points": 0, "explained_variance_ratio": [], "total_variance": 0.0}

    cluster_map = {c.id: c for c in clusters}

    # Fetch clustered gap logs
    res_logs = await db.execute(select(SearchLog).where(SearchLog.cluster_id.is_not(None)))
    logs = res_logs.scalars().all()
    if not logs:
        return {"clusters": [], "points": [], "total_points": 0, "explained_variance_ratio": [], "total_variance": 0.0}

    PALETTE = [
        "#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", 
        "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#06b6d4",
        "#84cc16", "#6366f1"
    ]
    color_map = {c.id: PALETTE[i % len(PALETTE)] for i, c in enumerate(clusters)}

    # Gather embeddings
    embeddings = []
    valid_logs = []
    for log in logs:
        emb = log.query_embedding
        if not emb:
            emb = embedding_service.encode(log.query_text, normalize=True).tolist()
            log.query_embedding = emb
        embeddings.append(emb)
        valid_logs.append(log)

    X = np.array(embeddings, dtype=np.float32)
    n_comp = min(3, len(valid_logs))
    pca = PCA(n_components=n_comp, random_state=42)
    X_reduced = pca.fit_transform(X)

    if X_reduced.shape[1] < 3:
        pad = np.zeros((X_reduced.shape[0], 3 - X_reduced.shape[1]))
        X_3d = np.hstack([X_reduced, pad])
    else:
        X_3d = X_reduced

    var_ratio = [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_]

    # Build points list
    points = []
    cluster_points_grouped = {}
    for idx, log in enumerate(valid_logs):
        c = cluster_map.get(log.cluster_id)
        if not c:
            continue
        px, py, pz = round(float(X_3d[idx, 0]), 3), round(float(X_3d[idx, 1]), 3), round(float(X_3d[idx, 2]), 3)
        points.append({
            "id": log.id,
            "query_text": log.query_text,
            "cluster_id": c.id,
            "cluster_title": c.title,
            "x": px,
            "y": py,
            "z": pz,
            "color": color_map[c.id]
        })
        cluster_points_grouped.setdefault(c.id, []).append((px, py, pz))

    # Build clusters list with accurate 3D centroids
    clusters_data = []
    for c in clusters:
        coords = cluster_points_grouped.get(c.id, [])
        if coords:
            cx = round(float(np.mean([pt[0] for pt in coords])), 3)
            cy = round(float(np.mean([pt[1] for pt in coords])), 3)
            cz = round(float(np.mean([pt[2] for pt in coords])), 3)
        else:
            cx, cy, cz = c.pca_x or 0.0, c.pca_y or 0.0, c.pca_z or 0.0

        clusters_data.append({
            "id": c.id,
            "title": c.title,
            "query_count": len(coords),
            "sample_queries": c.sample_queries or [],
            "keywords": c.keywords or [],
            "status": c.status.value,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "x": cx,
            "y": cy,
            "z": cz,
            "color": color_map[c.id]
        })

    return {
        "clusters": clusters_data,
        "points": points,
        "total_points": len(points),
        "explained_variance_ratio": var_ratio,
        "total_variance": round(sum(var_ratio), 1)
    }
