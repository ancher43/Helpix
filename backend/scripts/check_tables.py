import psycopg2

for port in [5432, 5433]:
    print(f"=== CHECKING PORT {port} ===")
    try:
        conn = psycopg2.connect(dbname="vkr_knowledge_base", user="postgres", password="123", host="localhost", port=port)
        cur = conn.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables on port {port}: {tables}")
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            print(f"  -> {t}: {cnt} rows")
        conn.close()
    except Exception as e:
        print(f"Port {port} error: {e}")
