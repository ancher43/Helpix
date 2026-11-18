import psycopg2

def clean_db(port):
    try:
        conn = psycopg2.connect(dbname="vkr_knowledge_base", user="postgres", password="123", host="localhost", port=port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO postgres;
            GRANT ALL ON SCHEMA public TO public;
        """)
        print(f"Port {port}: Database schema refreshed cleanly.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Port {port} error:", e)

if __name__ == "__main__":
    clean_db(5433)
    clean_db(5432)
