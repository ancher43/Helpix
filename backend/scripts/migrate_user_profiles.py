import sys
import os
import psycopg2

def migrate_postgres(port=5432):
    print(f"--- Migrating PostgreSQL on port {port} ---")
    try:
        conn = psycopg2.connect(dbname="vkr_knowledge_base", user="postgres", password="123", host="localhost", port=port)
        cur = conn.cursor()
        
        # Check and add columns to users table
        user_columns = [
            ("position", "VARCHAR(255)"),
            ("department", "VARCHAR(255)"),
            ("phone", "VARCHAR(50)")
        ]
        for col_name, col_type in user_columns:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='users' AND column_name='{col_name}'
                    ) THEN
                        ALTER TABLE users ADD COLUMN {col_name} {col_type};
                        RAISE NOTICE 'Added column {col_name} to users';
                    END IF;
                END $$;
            """)
        
        # Check and add columns to articles table
        article_columns = [
            ("updated_by_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")
        ]
        for col_name, col_type in article_columns:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='articles' AND column_name='{col_name}'
                    ) THEN
                        ALTER TABLE articles ADD COLUMN {col_name} {col_type};
                        RAISE NOTICE 'Added column {col_name} to articles';
                    END IF;
                END $$;
            """)
            
        conn.commit()
        conn.close()
        print(f"Port {port}: Migration completed successfully.")
    except Exception as e:
        print(f"Port {port} error: {e}")

def migrate_sqlite():
    import sqlite3
    db_path = "backend/local_vkr.db"
    if not os.path.exists(db_path):
        return
    print(f"--- Migrating SQLite at {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check existing columns in users
        cur.execute("PRAGMA table_info(users)")
        existing_cols = [r[1] for r in cur.fetchall()]
        for col in ["position", "department", "phone"]:
            if col not in existing_cols:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(255)")
                print(f"SQLite: Added {col} to users")
                
        # Check existing columns in articles
        cur.execute("PRAGMA table_info(articles)")
        existing_art_cols = [r[1] for r in cur.fetchall()]
        if "updated_by_id" not in existing_art_cols:
            cur.execute("ALTER TABLE articles ADD COLUMN updated_by_id INTEGER")
            print("SQLite: Added updated_by_id to articles")
            
        conn.commit()
        conn.close()
        print("SQLite migration completed.")
    except Exception as e:
        print(f"SQLite error: {e}")

if __name__ == "__main__":
    for p in [5432, 5433]:
        migrate_postgres(p)
    migrate_sqlite()
