import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

for port in [5432, 5433]:
    try:
        conn = psycopg2.connect(dbname="postgres", user="postgres", password="123", host="localhost", port=port)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version_str = cur.fetchone()[0]
        cur.execute("SELECT 1 FROM pg_database WHERE datname='vkr_knowledge_base'")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE vkr_knowledge_base")
            print(f"Port {port} ({version_str[:25]}): Created 'vkr_knowledge_base'")
        else:
            print(f"Port {port} ({version_str[:25]}): 'vkr_knowledge_base' exists")
        conn.close()
    except Exception as e:
        print(f"Port {port} error: {e}")
