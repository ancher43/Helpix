from typing import Optional, List
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query: str
    search_mode: str = "hybrid"  # "hybrid", "text", "semantic"
    top_k: int = 10
    category_id: Optional[int] = None

class SearchResultItem(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    content_snippet: Optional[str] = None
    category_name: Optional[str] = None
    tags: Optional[str] = None
    
    # RRF Scoring details (very useful for thesis evaluation & explanation!)
    rrf_score: float
    text_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    semantic_similarity: Optional[float] = None

class SearchResponse(BaseModel):
    search_id: Optional[int] = 0
    query: str
    search_mode: str
    results_count: int
    execution_time_ms: float
    results: List[SearchResultItem]
    text_count: int = 0
    semantic_count: int = 0
    hybrid_count: int = 0
    is_search_gap: bool = False

class FeedbackRequest(BaseModel):
    search_id: Optional[int] = 0
    query: Optional[str] = None
    search_mode: Optional[str] = "hybrid"
    clicked_article_id: Optional[int] = None
    is_helpful: bool  # True: helped, False: did not help / gap
    feedback_notes: Optional[str] = None
