import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.search_log import SearchLog
from app.models.cluster import SearchGapCluster, ClusterStatus
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)

class SearchGapClusteringService:
    def __init__(self, min_cluster_size: int = 2):
        self.min_cluster_size = min_cluster_size

    @staticmethod
    def _extract_cluster_keywords(queries: List[str], top_n: int = 4) -> List[str]:
        """Extract key distinctive words from cluster queries using TF-IDF."""
        if not queries:
            return []
        try:
            # Custom stop words in Russian and English
            custom_stops = {
                "как", "что", "где", "почему", "для", "или", "если", "при", "ошибка",
                "error", "how", "what", "where", "why", "the", "and", "is", "in", "to",
                "не", "на", "с", "по", "в", "от", "до", "из", "за"
            }
            vectorizer = TfidfVectorizer(
                max_features=25,
                stop_words=list(custom_stops),
                token_pattern=r'(?u)\b\w{3,}\b'
            )
            tfidf_matrix = vectorizer.fit_transform(queries)
            feature_names = vectorizer.get_feature_names_out()
            scores = np.asarray(tfidf_matrix.sum(axis=0)).ravel()
            top_indices = scores.argsort()[::-1][:top_n]
            return [feature_names[i] for i in top_indices if scores[i] > 0]
        except Exception:
            # Fallback simple frequency
            words = []
            for q in queries:
                words.extend([w.lower() for w in q.split() if len(w) > 3])
            from collections import Counter
            return [w for w, _ in Counter(words).most_common(top_n)]

    @staticmethod
    def _find_medoid_query(queries: List[str], embeddings: np.ndarray) -> str:
        """Find the query closest to the centroid of the cluster."""
        if len(queries) == 1:
            return queries[0]
        centroid = np.mean(embeddings, axis=0, keepdims=True)
        # Cosine distance to centroid
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = embeddings / norms
        
        c_norm = np.linalg.norm(centroid)
        if c_norm == 0:
            return queries[0]
        c_normed = centroid / c_norm
        
        sims = np.dot(normalized, c_normed.T).ravel()
        best_idx = int(np.argmax(sims))
        return queries[best_idx]

    async def cluster_unaddressed_gaps(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Runs clustering on search logs that are identified as search gaps
        (results_count == 0 OR is_helpful == False) and not yet assigned to an active cluster.
        """
        # Fetch gap search logs
        stmt = select(SearchLog).where(
            SearchLog.is_search_gap == True,
            SearchLog.cluster_id == None
        )
        result = await db.execute(stmt)
        gap_logs = result.scalars().all()

        if len(gap_logs) < 2:
            return {
                "clusters_created": 0,
                "total_gaps_processed": len(gap_logs),
                "algorithm": "AgglomerativeClustering",
                "silhouette_score": None,
                "message": f"Недостаточно запросов с пробелами для кластеризации (найдено: {len(gap_logs)}, минимум: 2)."
            }

        # Prepare queries and embeddings
        queries = [log.query_text for log in gap_logs]
        embeddings = []
        for log in gap_logs:
            if log.query_embedding:
                embeddings.append(log.query_embedding)
            else:
                emb = embedding_service.encode(log.query_text, normalize=True).tolist()
                log.query_embedding = emb
                embeddings.append(emb)

        X = np.array(embeddings, dtype=np.float32)

        # Dimensionality reduction for visualization (2D PCA)
        pca = PCA(n_components=2, random_state=42)
        X_2d = pca.fit_transform(X) if len(queries) >= 2 else np.zeros((len(queries), 2))

        # Dynamic number of clusters (heuristic: sqrt(N / 2) bounded between 2 and 10)
        n_samples = len(queries)
        n_clusters = max(2, min(int(np.sqrt(n_samples / 1.5)), 10))
        if n_clusters >= n_samples:
            n_clusters = max(1, n_samples - 1)

        # Clustering algorithm: Agglomerative with cosine metric or KMeans
        if n_samples > n_clusters and n_clusters > 1:
            clusterer = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='cosine',
                linkage='average'
            )
            labels = clusterer.fit_predict(X)
            try:
                sil_score = round(float(silhouette_score(X, labels, metric='cosine')), 3)
            except Exception:
                sil_score = None
        else:
            labels = np.zeros(n_samples, dtype=int)
            sil_score = None

        # Group by cluster label
        cluster_groups: Dict[int, List[int]] = {}
        for idx, lbl in enumerate(labels):
            cluster_groups.setdefault(lbl, []).append(idx)

        created_clusters_count = 0

        # Create SearchGapCluster records and link logs
        for lbl, member_indices in cluster_groups.items():
            member_queries = [queries[i] for i in member_indices]
            member_embeddings = X[member_indices]
            member_logs = [gap_logs[i] for i in member_indices]

            # Generate cluster title from medoid query and keywords
            medoid_query = self._find_medoid_query(member_queries, member_embeddings)
            keywords = self._extract_cluster_keywords(member_queries, top_n=5)
            
            # Capitalize medoid for title
            cluster_title = medoid_query.strip().capitalize()
            if len(cluster_title) > 60:
                cluster_title = cluster_title[:57] + "..."

            # Center coordinates for visualization
            center_x = float(np.mean(X_2d[member_indices, 0]))
            center_y = float(np.mean(X_2d[member_indices, 1]))

            # Unique sample queries
            unique_samples = list(dict.fromkeys(member_queries))[:8]

            new_cluster = SearchGapCluster(
                title=cluster_title,
                description=f"Тема выявлена на основе анализа {len(member_queries)} похожих запросов операторов.",
                query_count=len(member_queries),
                sample_queries=unique_samples,
                keywords=keywords,
                pca_x=round(center_x, 3),
                pca_y=round(center_y, 3),
                status=ClusterStatus.NEW
            )
            db.add(new_cluster)
            await db.flush()  # Obtain new_cluster.id

            # Link logs to this cluster
            for log in member_logs:
                log.cluster_id = new_cluster.id
            
            created_clusters_count += 1

        await db.commit()

        return {
            "clusters_created": created_clusters_count,
            "total_gaps_processed": n_samples,
            "algorithm": "AgglomerativeClustering (Cosine Linkage)",
            "silhouette_score": sil_score,
            "message": f"Успешно сформировано {created_clusters_count} кластеров пробелов знаний (обработано {n_samples} запросов)."
        }

clustering_service = SearchGapClusteringService()
