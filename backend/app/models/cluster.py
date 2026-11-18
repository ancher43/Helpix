import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base

class ClusterStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"

class SearchGapCluster(Base):
    __tablename__ = "search_gap_clusters"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    query_count = Column(Integer, default=0, nullable=False)
    sample_queries = Column(JSON, nullable=True)  # List of representative query strings
    keywords = Column(JSON, nullable=True)        # Extracted TF-IDF / key terms
    
    # 2D coordinates for visual representation in moderator dashboard
    pca_x = Column(Float, nullable=True)
    pca_y = Column(Float, nullable=True)
    
    status = Column(Enum(ClusterStatus), default=ClusterStatus.NEW, nullable=False)
    
    # If a new article was created to resolve this gap
    created_article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    queries = relationship("SearchLog", back_populates="cluster")
