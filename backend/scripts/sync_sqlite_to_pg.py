import sqlite3
import psycopg2
import json

def sync():
    print(">>> Syncing local_vkr.db to PostgreSQL 5432...")
    s_conn = sqlite3.connect("backend/local_vkr.db")
    s_conn.row_factory = sqlite3.Row
    
    p_conn = psycopg2.connect("postgresql://postgres:123@localhost:5432/vkr_knowledge_base")
    p_cur = p_conn.cursor()
    
    # Disable foreign keys temporarily during truncate
    p_cur.execute("TRUNCATE search_logs, search_gap_clusters, articles, categories, users RESTART IDENTITY CASCADE;")
    p_conn.commit()
    
    # 1. Categories
    cat_rows = s_conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    for r in cat_rows:
        p_cur.execute(
            "INSERT INTO categories (id, name, slug, description, created_at) VALUES (%s, %s, %s, %s, %s)",
            (r["id"], r["name"], r["slug"], r["description"], r["created_at"])
        )
    p_conn.commit()
    print(f"    Synced {len(cat_rows)} categories")

    # 2. Users
    user_rows = s_conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    for r in user_rows:
        p_cur.execute(
            "INSERT INTO users (id, email, username, full_name, hashed_password, role, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (r["id"], r["email"], r["username"], r["full_name"], r["hashed_password"], r["role"], bool(r["is_active"]), r["created_at"])
        )
    p_conn.commit()
    print(f"    Synced {len(user_rows)} users")

    # 3. Articles
    art_rows = s_conn.execute("SELECT * FROM articles ORDER BY id").fetchall()
    for r in art_rows:
        p_cur.execute(
            """INSERT INTO articles (id, title, content, summary, tags, category_id, created_by_id, is_published, views_count, helpful_count, unhelpful_count, embedding, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r["id"], r["title"], r["content"], r["summary"], r["tags"], r["category_id"], r["created_by_id"], bool(r["is_published"]), r["views_count"], r["helpful_count"], r["unhelpful_count"], r["embedding"], r["created_at"], r["updated_at"])
        )
    p_conn.commit()
    print(f"    Synced {len(art_rows)} articles")

    # 4. Clusters
    cluster_rows = s_conn.execute("SELECT * FROM search_gap_clusters ORDER BY id").fetchall()
    for r in cluster_rows:
        p_cur.execute(
            """INSERT INTO search_gap_clusters (id, title, description, query_count, sample_queries, keywords, pca_x, pca_y, pca_z, status, created_article_id, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r["id"], r["title"], r["description"], r["query_count"], r["sample_queries"], r["keywords"], r["pca_x"], r["pca_y"], r["pca_z"], r["status"], r["created_article_id"], r["created_at"], r["updated_at"])
        )
    p_conn.commit()
    print(f"    Synced {len(cluster_rows)} clusters")

    # 5. Search logs
    log_rows = s_conn.execute("SELECT * FROM search_logs ORDER BY id").fetchall()
    for r in log_rows:
        p_cur.execute(
            """INSERT INTO search_logs (id, query_text, operator_id, search_type, results_count, execution_time_ms, returned_article_ids, clicked_article_id, is_helpful, feedback_notes, is_search_gap, cluster_id, query_embedding, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r["id"], r["query_text"], r["operator_id"], r["search_type"], r["results_count"], r["execution_time_ms"], r["returned_article_ids"], r["clicked_article_id"], bool(r["is_helpful"]), r["feedback_notes"], bool(r["is_search_gap"]), r["cluster_id"], r["query_embedding"], r["timestamp"])
        )
    p_conn.commit()
    print(f"    Synced {len(log_rows)} search logs")

    # Update sequences
    for tbl in ["categories", "users", "articles", "search_gap_clusters", "search_logs"]:
        p_cur.execute(f"SELECT setval('{tbl}_id_seq', (SELECT COALESCE(MAX(id), 1) FROM {tbl}));")
    p_conn.commit()

    s_conn.close()
    p_conn.close()
    print(">>> PostgreSQL 5432 successfully synced with 100% of telecom data!")

if __name__ == "__main__":
    sync()
