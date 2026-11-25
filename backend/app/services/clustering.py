import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
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
    def _format_acronyms(text: str) -> str:
        """Capitalize first letter and format technical abbreviations."""
        import re
        t = text.strip()
        if not t:
            return t
        t = t[0].upper() + t[1:]
        replacements = {
            r'\bipv6\b': 'IPv6',
            r'\bipv4\b': 'IPv4',
            r'\bwi-fi\b': 'Wi-Fi',
            r'\bwifi\b': 'Wi-Fi',
            r'\bp2p\b': 'P2P',
            r'\bpos\b': 'POS',
            r'\bсбп\b': 'СБП',
            r'\бофд\b': 'ОФД',
            r'\bvpn\b': 'VPN',
            r'\bdns\b': 'DNS',
            r'\bdhcp\b': 'DHCP',
            r'\bont\b': 'ONT',
            r'\bgpon\b': 'GPON',
            r'\bkeenetic\b': 'Keenetic',
            r'\bhikvision\b': 'Hikvision',
            r'\bdahua\b': 'Dahua',
            r'\bwireguard\b': 'WireGuard',
        }
        for pat, rep in replacements.items():
            t = re.sub(pat, rep, t, flags=re.IGNORECASE)
        return t

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

        # Dimensionality reduction for visualization (3D PCA)
        n_comp = min(3, len(queries))
        pca = PCA(n_components=n_comp, random_state=42)
        X_reduced = pca.fit_transform(X) if len(queries) >= 2 else np.zeros((len(queries), 3))
        if X_reduced.shape[1] < 3:
            pad = np.zeros((X_reduced.shape[0], 3 - X_reduced.shape[1]))
            X_3d = np.hstack([X_reduced, pad])
        else:
            X_3d = X_reduced

        # Dynamic number of clusters (heuristic: sqrt(N * 2.3) bounded between 3 and 20)
        n_samples = len(queries)
        n_clusters = max(3, min(int(np.sqrt(n_samples * 2.3)), 20))
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

        # If any singleton clusters exist, merge them into the nearest valid cluster centroid
        valid_groups = {lbl: idxs for lbl, idxs in cluster_groups.items() if len(idxs) >= self.min_cluster_size}
        singletons = [i for lbl, idxs in cluster_groups.items() if len(idxs) < self.min_cluster_size for i in idxs]
        if singletons and valid_groups:
            centroids = {lbl: np.mean(X[idxs], axis=0) for lbl, idxs in valid_groups.items()}
            for s_idx in singletons:
                s_emb = X[s_idx]
                best_lbl = max(centroids.keys(), key=lambda l: float(np.dot(s_emb, centroids[l]) / (np.linalg.norm(s_emb) * np.linalg.norm(centroids[l]) + 1e-9)))
                valid_groups[best_lbl].append(s_idx)
            cluster_groups = valid_groups

        created_clusters_count = 0

        # Create SearchGapCluster records and link logs
        for lbl, member_indices in cluster_groups.items():
            member_queries = [queries[i] for i in member_indices]
            member_embeddings = X[member_indices]
            member_logs = [gap_logs[i] for i in member_indices]

            # Generate cluster title from medoid query and keywords
            medoid_query = self._find_medoid_query(member_queries, member_embeddings)
            keywords = self._extract_cluster_keywords(member_queries, top_n=5)
            
            # Capitalize medoid for title, strip common redundant prefixes
            import re
            cleaned_title = re.sub(r'^(как (настроить|включить|подключить|сделать)|почему не (работает|приходят|проходит))\s+', '', medoid_query.strip(), flags=re.IGNORECASE)
            cluster_title = self._format_acronyms(cleaned_title)
            if len(cluster_title) > 250:
                cluster_title = cluster_title[:250].strip()

            # Center coordinates for 3D visualization
            center_x = float(np.mean(X_3d[member_indices, 0]))
            center_y = float(np.mean(X_3d[member_indices, 1]))
            center_z = float(np.mean(X_3d[member_indices, 2]))

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
                pca_z=round(center_z, 3),
                status=ClusterStatus.NEW,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
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
