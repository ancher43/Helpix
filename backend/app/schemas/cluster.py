from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.cluster import ClusterStatus

class ClusterResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    query_count: int
    sample_queries: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    pca_x: Optional[float] = None
    pca_y: Optional[float] = None
    pca_z: Optional[float] = None
    status: ClusterStatus
    created_article_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClusterQueryItem(BaseModel):
    id: int
    query_text: str
    search_type: Optional[str] = "hybrid"
    results_count: int = 0
    is_helpful: Optional[bool] = None
    is_search_gap: bool = False
    execution_time_ms: float = 0.0
    timestamp: datetime
    operator_name: Optional[str] = None

class ClusterDetailResponse(ClusterResponse):
    queries: List[ClusterQueryItem] = []
    created_article_title: Optional[str] = None

class ClusterUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[ClusterStatus] = None
    created_article_id: Optional[int] = None

class ClusteringRunResponse(BaseModel):
    clusters_created: int
    total_gaps_processed: int
    algorithm: str
    silhouette_score: Optional[float] = None
    message: str
