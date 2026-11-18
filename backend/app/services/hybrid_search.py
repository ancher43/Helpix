import re
import time
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.models.article import Article, Category
from app.services.embedding import embedding_service
from app.core.config import settings

class HybridSearchService:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    @staticmethod
    def _create_snippet(content: str, query: str, max_length: int = 180) -> str:
        """Create a highlightable snippet containing query terms or start of content."""
        if not content:
            return ""
        
        # Clean markdown characters
        clean_text = re.sub(r'[#*`_\[\]]', ' ', content).strip()
        words = [w for w in re.split(r'\W+', query.lower()) if len(w) > 2]
        
        if not words:
            return clean_text[:max_length] + ("..." if len(clean_text) > max_length else "")
        
        # Look for first occurrence of any keyword
        lower_content = clean_text.lower()
        earliest_pos = -1
        for w in words:
            pos = lower_content.find(w)
            if pos != -1 and (earliest_pos == -1 or pos < earliest_pos):
                earliest_pos = pos
        
        if earliest_pos == -1:
            return clean_text[:max_length] + ("..." if len(clean_text) > max_length else "")
        
        start = max(0, earliest_pos - 40)
        end = min(len(clean_text), start + max_length)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(clean_text) else ""
        return prefix + clean_text[start:end].strip() + suffix

    async def search(
        self,
        db: AsyncSession,
        query: str,
        search_mode: str = "hybrid",
        top_k: int = 10,
        category_id: Optional[int] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes hybrid search combining lexical (text) and semantic (vector) rankings
        using Reciprocal Rank Fusion (RRF).
        """
        start_time = time.time()
        query = query.strip()
        if not query:
            return {
                "results": [],
                "total_found": 0,
                "execution_time_ms": 0.0
            }

        # Fetch active published articles
        stmt = select(Article, Category.name.label("category_name")).outerjoin(Category, Article.category_id == Category.id).where(Article.is_published == True)
        if category_id:
            stmt = stmt.where(Article.category_id == category_id)
        if language:
            stmt = stmt.where(Article.language == language)
            
        result = await db.execute(stmt)
        rows = result.all()
        
        if not rows:
            return {
                "results": [],
                "total_found": 0,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        articles_data = []
        for row in rows:
            art = row[0]
            cat_name = row[1]
            articles_data.append({
                "article": art,
                "category_name": cat_name,
                "embedding": art.embedding
            })

        # 1. Lexical / Keyword Scoring
        # Match against title, tags, summary, and content
        query_terms = [t.lower() for t in re.split(r'\s+', query) if len(t) > 1]
        text_scored_items = []
        
        for item in articles_data:
            art = item["article"]
            title_lower = art.title.lower()
            tags_lower = (art.tags or "").lower()
            summary_lower = (art.summary or "").lower()
            content_lower = art.content.lower()
            
            score = 0.0
            exact_match = 0
            
            # Full phrase match bonus
            if query.lower() in title_lower:
                score += 15.0
            if query.lower() in content_lower:
                score += 5.0

            # Term frequency & field weights
            for term in query_terms:
                if term in title_lower:
                    score += 5.0
                    exact_match += 1
                if term in tags_lower:
                    score += 4.0
                    exact_match += 1
                if term in summary_lower:
                    score += 2.0
                if term in content_lower:
                    # Count occurrences with diminishing returns
                    count = content_lower.count(term)
                    score += min(count * 0.5, 3.0)
                    exact_match += 1

            if score > 0:
                text_scored_items.append((item, score))

        # Sort text results descending by score
        text_scored_items.sort(key=lambda x: x[1], reverse=True)
        text_rank_map = {}
        for rank, (item, _) in enumerate(text_scored_items, start=1):
            text_rank_map[item["article"].id] = rank

        # 2. Semantic / Dense Vector Scoring
        query_vec = embedding_service.encode(query, normalize=True)
        semantic_scored_items = []
        semantic_sim_map = {}
        
        for item in articles_data:
            art_embedding = item["embedding"]
            if art_embedding is not None and len(art_embedding) > 0:
                doc_vec = np.array(art_embedding, dtype=np.float32)
                sim = float(np.dot(query_vec, doc_vec))  # cosine similarity as vectors are normalized
            else:
                sim = 0.0
            
            semantic_sim_map[item["article"].id] = sim
            # Include if similarity is meaningful (> 0.20 threshold)
            if sim > 0.18:
                semantic_scored_items.append((item, sim))

        semantic_scored_items.sort(key=lambda x: x[1], reverse=True)
        semantic_rank_map = {}
        for rank, (item, _) in enumerate(semantic_scored_items, start=1):
            semantic_rank_map[item["article"].id] = rank

        # 3. Mode Handling & Reciprocal Rank Fusion (RRF)
        # RRF formula: Score(d) = sum(1 / (k + rank))
        combined_candidates = {}
        
        if search_mode == "text":
            for item, _ in text_scored_items:
                art_id = item["article"].id
                combined_candidates[art_id] = {
                    "item": item,
                    "rrf_score": 1.0 / (self.rrf_k + text_rank_map[art_id]),
                    "text_rank": text_rank_map.get(art_id),
                    "semantic_rank": semantic_rank_map.get(art_id),
                    "similarity": semantic_sim_map.get(art_id, 0.0)
                }
        elif search_mode == "semantic":
            for item, _ in semantic_scored_items:
                art_id = item["article"].id
                combined_candidates[art_id] = {
                    "item": item,
                    "rrf_score": 1.0 / (self.rrf_k + semantic_rank_map[art_id]),
                    "text_rank": text_rank_map.get(art_id),
                    "semantic_rank": semantic_rank_map.get(art_id),
                    "similarity": semantic_sim_map.get(art_id, 0.0)
                }
        else:  # hybrid
            # Union of candidates from text and semantic
            all_candidate_ids = set(text_rank_map.keys()).union(set(semantic_rank_map.keys()))
            
            # Map id to item
            id_to_item = {item["article"].id: item for item in articles_data}
            
            for art_id in all_candidate_ids:
                item = id_to_item[art_id]
                rrf_score = 0.0
                
                if art_id in text_rank_map:
                    rrf_score += 1.0 / (self.rrf_k + text_rank_map[art_id])
                if art_id in semantic_rank_map:
                    rrf_score += 1.0 / (self.rrf_k + semantic_rank_map[art_id])
                
                combined_candidates[art_id] = {
                    "item": item,
                    "rrf_score": rrf_score,
                    "text_rank": text_rank_map.get(art_id),
                    "semantic_rank": semantic_rank_map.get(art_id),
                    "similarity": round(semantic_sim_map.get(art_id, 0.0), 4)
                }

        # Sort merged results by RRF score descending
        sorted_results = sorted(combined_candidates.values(), key=lambda x: x["rrf_score"], reverse=True)
        top_results = sorted_results[:top_k]

        # Format output items
        output_items = []
        for r in top_results:
            art = r["item"]["article"]
            cat_name = r["item"]["category_name"]
            snippet = self._create_snippet(art.content, query)
            
            output_items.append({
                "id": art.id,
                "title": art.title,
                "summary": art.summary,
                "content_snippet": snippet,
                "category_name": cat_name,
                "tags": art.tags,
                "language": art.language,
                "rrf_score": round(r["rrf_score"], 5),
                "text_rank": r["text_rank"],
                "semantic_rank": r["semantic_rank"],
                "semantic_similarity": r["similarity"]
            })

        execution_time = round((time.time() - start_time) * 1000, 2)
        return {
            "results": output_items,
            "total_found": len(output_items),
            "execution_time_ms": execution_time
        }

hybrid_search_service = HybridSearchService(rrf_k=settings.RRF_K)
