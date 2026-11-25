# -*- coding: utf-8 -*-
import sqlite3
import psycopg2

SHORT_CLUSTER_TITLES = {
    1: "Настройка IPv6",
    2: "Умный домофон",
    3: "Видеонаблюдение",
    4: "Родительский контроль",
    5: "Онлайн-кассы",
    6: "POS-терминалы",
    7: "Mesh Wi-Fi",
    8: "P2P видеонаблюдение",
    9: "Оплата по СБП",
    10: "P2P камеры",
    11: "Эквайринг"
}

def main():
    # 1. Update SQLite
    try:
        s_conn = sqlite3.connect("backend/local_vkr.db")
        s_cur = s_conn.cursor()
        for cid, title in SHORT_CLUSTER_TITLES.items():
            s_cur.execute("UPDATE search_gap_clusters SET title = ? WHERE id = ?", (title, cid))
        s_conn.commit()
        s_conn.close()
        print("Updated SQLite with short titles.")
    except Exception as e:
        print("SQLite error:", e)

    # 2. Update PostgreSQL
    try:
        p_conn = psycopg2.connect(
            dbname="vkr_knowledge_base",
            user="postgres",
            password="123",
            host="localhost",
            port=5432
        )
        p_cur = p_conn.cursor()
        for cid, title in SHORT_CLUSTER_TITLES.items():
            p_cur.execute("UPDATE search_gap_clusters SET title = %s WHERE id = %s", (title, cid))
        p_conn.commit()
        
        p_cur.execute("SELECT id, title FROM search_gap_clusters ORDER BY id")
        for row in p_cur.fetchall():
            print(f"  [{row[0]}] {row[1]}")
        p_conn.close()
        print("Updated PostgreSQL with short titles.")
    except Exception as e:
        print("PostgreSQL error:", e)

if __name__ == "__main__":
    main()
