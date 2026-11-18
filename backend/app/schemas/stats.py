from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class TopQueryItem(BaseModel):
    query: str
    count: int
    is_gap: bool

class TopArticleItem(BaseModel):
    id: int
    title: str
    views_count: int
    helpful_count: int
    unhelpful_count: int
    helpfulness_rate: float

class DailySearchStat(BaseModel):
    date: str
    total_searches: int
    gaps_count: int

class SearchGapLogItem(BaseModel):
    id: int
    query_text: str
    timestamp: datetime
    results_count: int
    is_helpful: Optional[bool]
    cluster_title: Optional[str] = None

class ModeratorDashboardStats(BaseModel):
    total_articles: int
    total_searches: int
    total_gaps: int
    gap_rate: float  # Percentage of searches that were gaps
    active_clusters_count: int
    resolved_clusters_count: int
    top_queries: List[TopQueryItem]
    top_articles: List[TopArticleItem]
    recent_gaps: List[SearchGapLogItem]
    daily_stats: List[DailySearchStat]
