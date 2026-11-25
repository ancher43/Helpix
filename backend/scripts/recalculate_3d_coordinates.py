import sys
import json
import asyncio
import numpy as np
from sklearn.decomposition import PCA
from sqlalchemy import select, update

sys.path.insert(0, 'backend')
from app.core.database import DatabaseManager
from app.models.cluster import SearchGapCluster
from app.models.search_log import SearchLog
from app.services.embedding import embedding_service

async def recalculate():
    await DatabaseManager.check_and_fallback()
    async with DatabaseManager.session_maker() as session:
        # 1. Fetch all clusters
        res = await session.execute(select(SearchGapCluster).order_by(SearchGapCluster.id))
        clusters = res.scalars().all()
        print(f"Found {len(clusters)} clusters.")

        # 2. Fetch all logs assigned to clusters
        res_logs = await session.execute(
            select(SearchLog).where(SearchLog.cluster_id.is_not(None))
        )
        logs = res_logs.scalars().all()
        print(f"Found {len(logs)} clustered gap logs.")

        if not logs:
            print("No logs found.")
            return

        # 3. Extract embeddings
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
        print(f"Embedding matrix shape: {X.shape}")

        # 4. Fit 3D PCA
        pca = PCA(n_components=3, random_state=42)
        X_3d = pca.fit_transform(X)

        var1, var2, var3 = pca.explained_variance_ratio_
        total_var = (var1 + var2 + var3) * 100
        print(f"PCA 3D Explained Variance:")
        print(f"  PC1 (X): {var1*100:.1f}%")
        print(f"  PC2 (Y): {var2*100:.1f}%")
        print(f"  PC3 (Z): {var3*100:.1f}%")
        print(f"  Total Explained Variance: {total_var:.1f}%")

        # 5. Group 3D coordinates by cluster_id
        cluster_coords = {}
        for idx, log in enumerate(valid_logs):
            c_id = log.cluster_id
            cluster_coords.setdefault(c_id, []).append(X_3d[idx])

        # 6. Update cluster centroids in DB
        for c in clusters:
            if c.id in cluster_coords:
                coords = np.array(cluster_coords[c.id])
                mean_x = float(np.mean(coords[:, 0]))
                mean_y = float(np.mean(coords[:, 1]))
                mean_z = float(np.mean(coords[:, 2]))

                c.pca_x = round(mean_x, 3)
                c.pca_y = round(mean_y, 3)
                c.pca_z = round(mean_z, 3)
                print(f"  Cluster #{c.id} '{c.title}': ({c.pca_x}, {c.pca_y}, {c.pca_z}) | Queries: {len(coords)}")

        await session.commit()
        print("Updated all clusters in primary DB successfully!")

if __name__ == "__main__":
    asyncio.run(recalculate())
