# -*- coding: utf-8 -*-
"""
Script to add realistic unassigned search gap queries to both local SQLite and PostgreSQL.
These queries will allow the user to click "Запустить кластеризацию" in the UI
and see the NLP clustering algorithm group them into new knowledge gap topics!
"""
import sys
import os
import json
import sqlite3
import psycopg2
from datetime import datetime, timedelta, timezone
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding import embedding_service

UNASSIGNED_GAPS = [
    # Тема 1: Настройка WireGuard / VPN туннелей на роутерах для удаленщиков (6 запросов)
    "как настроить wireguard vpn на роутере keenetic для удаленки",
    "настройка клиента wireguard на роутере микротик peer handshake timeout",
    "openvpn клиент на роутере tp-link не подключается auth failed",
    "импорт конфигурационного файла wireguard conf в роутер",
    "удаленный доступ к корпоративной сети через wireguard vpn с роутера",
    "настройка маршрутизации трафика через vpn туннель wireguard на keenetic",

    # Тема 2: Проблемы со связью у онлайн-касс и POS-терминалов эквайринга (6 запросов)
    "онлайн касса эвотор пишет нет связи с офд ошибка сети",
    "pos терминал сбербанка ошибка 4119 нет связи с банком",
    "не уходят фискальные чеки в офд первый офд такском через интернет",
    "терминал эквайринга не может связаться с хостом авторизации",
    "кассовый аппарат атол ошибка обмена с офд проверьте кабель или dhcp",
    "настройка статического ip и портов для терминала безналичной оплаты",

    # Тема 3: Облачное видеонаблюдение P2P и сбой подключения камер без белого IP (5 запросов)
    "видеорегистратор hikvision status offline в приложении hik-connect",
    "облачный сервис dahua dmss пишет устройство не в сети p2p",
    "как подключить ip камеру видеонаблюдения к облаку без статического белого ip",
    "почему не работает просмотр камер через приложение xmeye без белого адреса",
    "ошибка подключения к p2p облаку видеонаблюдения ошибка тайм-аута",

    # Тема 4: Оплата через СБП по QR-коду и задержка снятия финансовой блокировки (5 запросов)
    "оплатил интернет через сбп по qr коду деньги списались а интернет заблокирован",
    "почему не включается интернет сразу после оплаты через систему быстрых платежей",
    "сбп платеж прошел успешно чек есть в сбербанке но баланс отрицательный",
    "сколько времени идет зачисление платежа по сбп qr коду в биллинг",
    "автоматическое снятие финансовой блокировки после оплаты по сбп"
]

def main():
    print(f">>> Подготовка {len(UNASSIGNED_GAPS)} поисковых пробелов (неудачных запросов)...")
    now = datetime.now(timezone.utc)
    
    logs_to_insert = []
    for idx, query in enumerate(UNASSIGNED_GAPS):
        emb = embedding_service.encode(query, normalize=True).tolist()
        t_stamp = now - timedelta(hours=random.randint(1, 12), minutes=random.randint(0, 55))
        
        # 80% нулевая выдача, 20% не помогло
        res_count = 0 if idx % 4 != 0 else 2
        
        logs_to_insert.append({
            "query_text": query,
            "operator_id": 3,  # operator user
            "search_type": "hybrid",
            "results_count": res_count,
            "execution_time_ms": round(random.uniform(14.0, 32.0), 2),
            "returned_article_ids": "[]",
            "clicked_article_id": None,
            "is_helpful": False,
            "feedback_notes": "Решение не найдено в базе знаний" if res_count > 0 else None,
            "is_search_gap": True,
            "cluster_id": None,  # Не привязано к кластеру!
            "query_embedding": emb,
            "timestamp": t_stamp
        })

    # 1. Вставка в SQLite
    sqlite_path = "backend/local_vkr.db"
    if os.path.exists(sqlite_path):
        s_conn = sqlite3.connect(sqlite_path)
        s_cur = s_conn.cursor()
        for log in logs_to_insert:
            s_cur.execute("""
                INSERT INTO search_logs (
                    query_text, operator_id, search_type, results_count,
                    execution_time_ms, returned_article_ids, clicked_article_id,
                    is_helpful, feedback_notes, is_search_gap, cluster_id,
                    query_embedding, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log["query_text"], log["operator_id"], log["search_type"],
                log["results_count"], log["execution_time_ms"],
                log["returned_article_ids"], log["clicked_article_id"],
                log["is_helpful"], log["feedback_notes"],
                1 if log["is_search_gap"] else 0,
                None,
                json.dumps(log["query_embedding"]),
                log["timestamp"].isoformat()
            ))
        s_conn.commit()
        s_conn.close()
        print(f"    Успешно добавлено {len(logs_to_insert)} пробелов в SQLite (local_vkr.db)")

    # 2. Вставка в PostgreSQL 5432
    try:
        p_conn = psycopg2.connect(
            dbname="vkr_knowledge_base",
            user="postgres",
            password="123",
            host="localhost",
            port=5432
        )
        p_cur = p_conn.cursor()
        for log in logs_to_insert:
            p_cur.execute("""
                INSERT INTO search_logs (
                    query_text, operator_id, search_type, results_count,
                    execution_time_ms, returned_article_ids, clicked_article_id,
                    is_helpful, feedback_notes, is_search_gap, cluster_id,
                    query_embedding, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                log["query_text"], log["operator_id"], log["search_type"],
                log["results_count"], log["execution_time_ms"],
                log["returned_article_ids"], log["clicked_article_id"],
                log["is_helpful"], log["feedback_notes"],
                log["is_search_gap"],
                None,
                json.dumps(log["query_embedding"]),
                log["timestamp"]
            ))
        p_conn.commit()
        
        p_cur.execute("SELECT count(*) FROM search_logs WHERE is_search_gap = true AND cluster_id IS NULL")
        unassigned_count = p_cur.fetchone()[0]
        p_conn.close()
        print(f"    Успешно добавлено {len(logs_to_insert)} пробелов в PostgreSQL 5432!")
        print(f">>> Всего неразобранных пробелов для кластеризации в БД: {unassigned_count}")
    except Exception as e:
        print(f"    Ошибка подключения к PostgreSQL: {e}")

if __name__ == "__main__":
    main()
