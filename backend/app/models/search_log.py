from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.core.database import Base

class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(String(500), index=True, nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    search_type = Column(String(50), default="hybrid")  # hybrid, text, semantic
    results_count = Column(Integer, default=0, nullable=False)
    execution_time_ms = Column(Float, default=0.0)
    
    # Store IDs of returned articles and their fusion scores
    returned_article_ids = Column(JSON, nullable=True)
    
    # User interaction
    clicked_article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    
    # Feedback: True = helped, False = did not help, None = no feedback yet
    is_helpful = Column(Boolean, nullable=True)
    feedback_notes = Column(Text, nullable=True)
    
    # Gap detection flag: True if results_count == 0 OR is_helpful == False
    is_search_gap = Column(Boolean, default=False, index=True)
    cluster_id = Column(Integer, ForeignKey("search_gap_clusters.id", ondelete="SET NULL"), nullable=True)
    
    # Query embedding (JSON array of floats) for fast gap clustering
    query_embedding = Column(JSON, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    operator = relationship("User", back_populates="search_logs")
    cluster = relationship("SearchGapCluster", back_populates="queries")
