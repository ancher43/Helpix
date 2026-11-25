# -*- coding: utf-8 -*-
import sqlite3
import psycopg2

CLUSTER_TITLE_FIXES = {
    1: "Настройка IPv6 на роутере",
    2: "Умный домофон: звонки в приложении",
    3: "Трансляция с камер видеонаблюдения",
    4: "Родительский контроль и блокировка сайтов",
    5: "Сбои в работе кассовых аппаратов",
    6: "POS-терминалы: ошибка 4119 (хост)",
    7: "Mesh Wi-Fi: бесшовный роуминг",
    8: "P2P видеонаблюдение (Hikvision/Dahua)",
    9: "Оплата по СБП и задержка разблокировки",
    10: "P2P доступ к камерам без белого IP",
    11: "POS-терминалы эквайринга (Сбербанк)"
}

def main():
    # 1. Update SQLite
    try:
        s_conn = sqlite3.connect("backend/local_vkr.db")
        s_cur = s_conn.cursor()
        for cid, title in CLUSTER_TITLE_FIXES.items():
            s_cur.execute("UPDATE search_gap_clusters SET title = ? WHERE id = ?", (title, cid))
        s_conn.commit()
        s_conn.close()
        print("Updated SQLite cluster titles.")
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
        for cid, title in CLUSTER_TITLE_FIXES.items():
            p_cur.execute("UPDATE search_gap_clusters SET title = %s WHERE id = %s", (title, cid))
        p_conn.commit()
        
        p_cur.execute("SELECT id, title FROM search_gap_clusters ORDER BY id")
        for row in p_cur.fetchall():
            print(f"  [{row[0]}] {row[1]}")
        p_conn.close()
        print("Updated PostgreSQL cluster titles successfully.")
    except Exception as e:
        print("PostgreSQL error:", e)

if __name__ == "__main__":
    main()
