import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add parent directory to path so app modules can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from app.core.database import Base
from app.models.user import User, UserRole
from app.models.article import Category, Article
from app.models.search_log import SearchLog
from app.models.cluster import SearchGapCluster
from app.core.security import get_password_hash
from app.services.embedding import embedding_service

# ==============================================================================
# ТЕМАТИКА: СЛУЖБА ТЕХНИЧЕСКОЙ ПОДДЕРЖКИ ТЕЛЕКОММУНИКАЦИОННОЙ КОМПАНИИ (ИНТЕРНЕТ-ПРОВАЙДЕРА)
# ==============================================================================

CATEGORIES_DATA = [
    {
        "name": "ШПД и Абонентские линии",
        "slug": "broadband-access",
        "description": "Техподдержка широкополосного доступа: витая пара, оптические терминалы GPON/ONT, протоколы PPPoE/IPoE и ошибки ОС."
    },
    {
        "name": "Абонентское оборудование и Wi-Fi",
        "slug": "cpe-routers",
        "description": "Настройка и диагностика домашних Wi-Fi роутеров (Keenetic, TP-Link, MikroTik, Eltex), частоты 2.4/5 ГГц, MTU и режим Bridge."
    },
    {
        "name": "Интерактивное ТВ и IPTV",
        "slug": "iptv-media",
        "description": "Телевещание, мультикаст-потоки IGMP Snooping, настройка ТВ-приставок (STB / Android TV), портал телевидения."
    },
    {
        "name": "IP-телефония и ВАТС",
        "slug": "voip-telephony",
        "description": "Протокол SIP, регистрация IP-телефонов и голосовых шлюзов, односторонняя слышимость (RTP/SIP ALG), Виртуальная АТС."
    },
    {
        "name": "Биллинг, Авторизация и Услуги",
        "slug": "billing-access",
        "description": "Привязка и смена MAC-адреса, Option 82 DHCP, сброс сессий RADIUS/BRAS, финансовые блокировки, статический IP."
    },
    {
        "name": "Магистральная сеть и Коммутаторы (NOC)",
        "slug": "infrastructure-noc",
        "description": "2-я линия ТП и мониторинг: L2-коммутаторы доступа, штормы трафика, Loopback Detection (петли), обрывы оптики и питание узлов."
    }
]

from scripts.populate_50_articles import ARTICLES as ARTICLES_DATA

# ==============================================================================
# СИМУЛЯЦИЯ ПОИСКОВЫХ ЗАПРОСОВ (ДЛЯ ДАШБОРДА, МЕТРИК И АНАЛИЗА ПРОБЕЛОВ)
# ==============================================================================

SUCCESSFUL_QUERIES = [
    # 1. Кабель витая пара / TDR
    ("сетевой кабель не подключен что делать", "Диагностика ошибки «Сетевой кабель не подключен» и проверка витой пары на порту коммутатора"),
    ("проверить витую пару тестером tdr eltex d-link", "Диагностика ошибки «Сетевой кабель не подключен» и проверка витой пары на порту коммутатора"),
    ("нет линка на порту коммутатора обрыв витой пары", "Диагностика ошибки «Сетевой кабель не подключен» и проверка витой пары на порту коммутатора"),

    # 2. Ошибка 651 PPPoE
    ("ошибка 651 модем сообщил об ошибке pppoe windows", "Устранение ошибки 651 («Модем или другое устройство связи сообщило об ошибке») при подключении PPPoE"),
    ("сброс tcp ip netsh winsock reset pppoe 651", "Устранение ошибки 651 («Модем или другое устройство связи сообщило об ошибке») при подключении PPPoE"),
    ("не удается подключиться pppoe ошибка 651 raspppoe", "Устранение ошибки 651 («Модем или другое устройство связи сообщило об ошибке») при подключении PPPoE"),

    # 3. Ошибка 691 / BRAS
    ("ошибка 691 доступ запрещен неверный логин", "Диагностика ошибки 691 («Доступ запрещен») и сброс зависшей сессии абонента на BRAS/BNG"),
    ("сбросить зависшую сессию radius bras clear pppoe", "Диагностика ошибки 691 («Доступ запрещен») и сброс зависшей сессии абонента на BRAS/BNG"),
    ("auth reject access reject simultaneous use limit exceeded", "Диагностика ошибки 691 («Доступ запрещен») и сброс зависшей сессии абонента на BRAS/BNG"),

    # 4. Оптический сигнал GPON / LOS / PON
    ("мигает красным индикатор los на роутере gpon", "Контроль оптического сигнала на абонентском терминале GPON/ONT (индикаторы PON и LOS)"),
    ("нормальный уровень сигнала gpon dbm rx power", "Контроль оптического сигнала на абонентском терминале GPON/ONT (индикаторы PON и LOS)"),
    ("моргает индикатор pon нет интернета оптика затухание", "Контроль оптического сигнала на абонентском терминале GPON/ONT (индикаторы PON и LOS)"),

    # 5. Настройка роутера IPoE / DHCP
    ("как настроить роутер keenetic ipoe dhcp", "Настройка абонентского маршрутизатора (Keenetic, TP-Link, MikroTik) для подключения по IPoE (DHCP)"),
    ("настройка tp-link динамический ip dynamic ip wan", "Настройка абонентского маршрутизатора (Keenetic, TP-Link, MikroTik) для подключения по IPoE (DHCP)"),
    ("mikrotik dhcp client на wan интерфейсе настройка", "Настройка абонентского маршрутизатора (Keenetic, TP-Link, MikroTik) для подключения по IPoE (DHCP)"),

    # 6. Wi-Fi помехи 2.4 / 5 ГГц
    ("медленно работает интернет по wifi помехи 2.4 ггц", "Оптимизация скорости домашнего Wi-Fi: выбор каналов и устранение помех на частотах 2.4 и 5 ГГц"),
    ("выбор свободного канала wifi 5 ггц ширина 80 мгц", "Оптимизация скорости домашнего Wi-Fi: выбор каналов и устранение помех на частотах 2.4 и 5 ГГц"),
    ("почему падает скорость интернета через вай фай в квартире", "Оптимизация скорости домашнего Wi-Fi: выбор каналов и устранение помех на частотах 2.4 и 5 ГГц"),

    # 7. MTU / MSS Clamping
    ("не открываются сайты госуслуг размер mtu pppoe", "Устранение проблем с открытием части сайтов из-за размера MTU и фрагментации пакетов (MSS Clamping)"),
    ("команда ping f l 1464 ya ru проверка фрагментации", "Устранение проблем с открытием части сайтов из-за размера MTU и фрагментации пакетов (MSS Clamping)"),
    ("сайты бесконечно грузятся mss clamping размер пакета", "Устранение проблем с открытием части сайтов из-за размера MTU и фрагментации пакетов (MSS Clamping)"),

    # 8. ONT в режим Bridge / Мост
    ("перевести терминал gpon ont в мост bridge для mikrotik", "Перевод оптического терминала GPON ONT в режим прозрачного моста (Bridge) для стороннего роутера"),
    ("eltex ntp-rg отключить nat перевести в бридж", "Перевод оптического терминала GPON ONT в режим прозрачного моста (Bridge) для стороннего роутера"),
    ("двойной nat как обойти подключить свой роутер к ont", "Перевод оптического терминала GPON ONT в режим прозрачного моста (Bridge) для стороннего роутера"),

    # 9. Зависание IPTV 10 секунд / IGMP
    ("зависает iptv через 10 секунд igmp snooping proxy", "Зависание каналов IPTV через 10 секунд и рассыпание картинки (настройка IGMP Snooping / Proxy)"),
    ("рассыпается картинка тв мультикаст igmp membership query", "Зависание каналов IPTV через 10 секунд и рассыпание картинки (настройка IGMP Snooping / Proxy)"),
    ("настройка igmp proxy на домашнем роутере каналы зависают", "Зависание каналов IPTV через 10 секунд и рассыпание картинки (настройка IGMP Snooping / Proxy)"),

    # 10. Приставка STB / Нет сигнала
    ("ошибка авторизации на тв приставке stb нет сигнала", "Диагностика ошибки «Нет сигнала / Ошибка авторизации» на ТВ-приставке (STB / Android TV)"),
    ("android tv приставка оператора сброс кэша factory reset", "Диагностика ошибки «Нет сигнала / Ошибка авторизации» на ТВ-приставке (STB / Android TV)"),
    ("превышен лимит устройств интерактивного телевидения", "Диагностика ошибки «Нет сигнала / Ошибка авторизации» на ТВ-приставке (STB / Android TV)"),

    # 11. Выделенный порт под ТВ / VLAN
    ("настройка vlan iptv порт 4 роутер мост", "Настройка выделенного LAN-порта под ТВ-приставку на абонентском роутере (VLAN ID / Bridge)"),
    ("выделенный порт под приставку custom vlan id tp-link", "Настройка выделенного LAN-порта под ТВ-приставку на абонентском роутере (VLAN ID / Bridge)"),
    ("как подключить тв приставку через роутер в отдельный lan", "Настройка выделенного LAN-порта под ТВ-приставку на абонентском роутере (VLAN ID / Bridge)"),

    # 12. Односторонняя слышимость / SIP ALG / RTP
    ("односторонняя слышимость в телефоне отключить sip alg", "Односторонняя слышимость и отсутствие звука в IP-телефонии (отключение SIP ALG и проброс RTP)"),
    ("нет звука при звонке тишина в трубке rtp порты", "Односторонняя слышимость и отсутствие звука в IP-телефонии (отключение SIP ALG и проброс RTP)"),
    ("отключить sip alg keenetic mikrotik voip", "Односторонняя слышимость и отсутствие звука в IP-телефонии (отключение SIP ALG и проброс RTP)"),

    # 13. Ошибки SIP 403 / 408
    ("ошибка sip 403 forbidden yealink регистрация", "Устранение ошибок SIP 403 Forbidden и SIP 408 Request Timeout при регистрации IP-телефона"),
    ("sip 408 request timeout таймаут регистрации телефона", "Устранение ошибок SIP 403 Forbidden и SIP 408 Request Timeout при регистрации IP-телефона"),
    ("ip телефон grandstream ошибка авторизации sip сервер", "Устранение ошибок SIP 403 Forbidden и SIP 408 Request Timeout при регистрации IP-телефона"),

    # 14. Виртуальная АТС / IVR / Переадресация
    ("как настроить голосовое меню ivr виртуальная атс", "Настройка сценариев переадресации, очередей вызовов и IVR в Виртуальной АТС (ВАТС)"),
    ("переадресация звонков в нерабочее время на сотовый ватс", "Настройка сценариев переадресации, очередей вызовов и IVR в Виртуальной АТС (ВАТС)"),
    ("настройка очереди входящих вызовов многоканальный номер", "Настройка сценариев переадресации, очередей вызовов и IVR в Виртуальной АТС (ВАТС)"),

    # 15. Смена роутера / MAC / Option 82
    ("купил новый роутер нет интернета сбросить mac адрес", "Замена роутера абонентом: сброс привязки MAC-адреса и особенности авторизации по Option 82"),
    ("авторизация option 82 dhcp snooping привязка к порту", "Замена роутера абонентом: сброс привязки MAC-адреса и особенности авторизации по Option 82"),
    ("как обновить mac адрес в биллинге после замены оборудования", "Замена роутера абонентом: сброс привязки MAC-адреса и особенности авторизации по Option 82"),

    # 16. Обещанный платеж / Captive Portal
    ("подключить обещанный платеж финансовая блокировка", "Активация сервиса «Обещанный платеж» и выход из финансовой блокировки (Captive Portal)"),
    ("заглушка пополните баланс captive portal снятие блокировки", "Активация сервиса «Обещанный платеж» и выход из финансовой блокировки (Captive Portal)"),
    ("интернет заблокирован за неуплату как взять доверительный платеж", "Активация сервиса «Обещанный платеж» и выход из финансовой блокировки (Captive Portal)"),

    # 17. Статический белый IP / Проброс портов
    ("как подключить статический белый ip для видеонаблюдения", "Подключение услуги статического белого IP-адреса и настройка проброса портов (Port Forwarding)"),
    ("проброс портов port forwarding роутер серый ip cgnat", "Подключение услуги статического белого IP-адреса и настройка проброса портов (Port Forwarding)"),
    ("доступ к видеорегистратору через интернет внешний белый ip", "Подключение услуги статического белого IP-адреса и настройка проброса портов (Port Forwarding)"),

    # 18. Loopback Detection / Сетевая петля
    ("заблокирован порт петля loopback detection коммутатор", "Блокировка порта коммутатора доступа по Loopback Detection (сетевое кольцо/петля у абонента)"),
    ("состояние err-disable на свитче закольцевали кабель", "Блокировка порта коммутатора доступа по Loopback Detection (сетевое кольцо/петля у абонента)"),
    ("как разблокировать порт после устранения сетевого кольца eltex", "Блокировка порта коммутатора доступа по Loopback Detection (сетевое кольцо/петля у абонента)"),

    # 19. Массовая авария на узле связи / ВОЛС
    ("массовая авария на узле связи нет интернета дом", "Регламент действий при массовой аварии на узле связи: отключение электропитания и обрыв ВОЛС"),
    ("отключение электричества на узле связи переход на ups", "Регламент действий при массовой аварии на узле связи: отключение электропитания и обрыв ВОЛС"),
    ("обрыв оптической магистрали zabbix хосты недоступны", "Регламент действий при массовой аварии на узле связи: отключение электропитания и обрыв ВОЛС"),

    # 20. Широковещательный шторм / Storm Control
    ("широковещательный шторм broadcast storm control на свитче", "Локализация широковещательного шторма (Broadcast Storm) и активация Storm Control на порту доступа"),
    ("загрузка cpu коммутатора 100% флуд мультикаст пакетов", "Локализация широковещательного шторма (Broadcast Storm) и активация Storm Control на порту доступа"),
    ("настройка storm control broadcast kbps 1024 изоляция порта", "Локализация широковещательного шторма (Broadcast Storm) и активация Storm Control на порту доступа")
]

# ТЕМАТИЧЕСКИЕ ПОИСКОВЫЕ ПРОБЕЛЫ (SEARCH GAPS), которых пока НЕТ в базе статей (40 запросов):
# Алгоритм NLP-кластеризации автоматически сгруппирует их по семантике
GAP_CLUSTERS_DATA = [
    # Кластер 1: IPv6 и делегирование префиксов DHCPv6 Prefix Delegation (PD)
    [
        "как включить ipv6 на роутере keenetic провайдер",
        "настройка ipv6 dhcpv6 pd prefix delegation роутер",
        "выдает ли наш провайдер ipv6 адреса для дома",
        "ошибка ipv6 no prefix received wan dhcp6 клиент",
        "поддержка ipv6 в сети оператора как настроить wan ipv6",
        "настройка slaac и dhcpv6 на домашнем оборудовании",
        "маршрутизация ipv6 префикс /56 или /64 в сети провайдера"
    ],
    # Кластер 2: Умный домофон и видеонаблюдение подъезда в мобильном приложении
    [
        "не приходят звонки с умного домофона в приложение на телефон",
        "как подключить второй телефон к домофону провайдера",
        "умный домофон пишет нет связи с камерой подъезда сбой",
        "приложение домофон не открывает дверь с телефона кнопка не работает",
        "настройка мобильного приложения умный дом домофон авторизация",
        "не работает видеокамера на подъездном домофоне черный экран",
        "сброс пароля в приложении умный домофон для жильцов"
    ],
    # Кластер 3: Родительский контроль и фильтрация контента / DNS Безопасный интернет
    [
        "как заблокировать опасные сайты 18+ для ребенка через роутер",
        "подключение услуги детский интернет яндекс dns семейный",
        "родительский контроль на домашнем интернете провайдера включить",
        "фильтрация контента и блокировка сайтов на уровне роутера",
        "как оградить ребенка от нежелательного контента профиль dns",
        "блокировка сайтов по расписанию для детского смартфона",
        "услуга безопасный интернет антивирус на шлюзе провайдера"
    ],
    # Кластер 4: Подключение терминалов оплаты эквайринга и онлайн-касс B2B
    [
        "эквайринг pos терминал сбербанка не может связаться с банком ошибка",
        "настройка онлайн кассы эвотор через ethernet кабель провайдера",
        "банковский терминал оплаты ошибка связи с сервером авторизации",
        "проброс портов для pos терминала оплаты b2b статический ip",
        "сбои в работе кассового аппарата через интернет провайдера таймаут",
        "терминал оплаты картой пишет нет связи с хостом ошибка 4119",
        "настройка vpn туннеля для банкоматов и кассовых узлов"
    ],
    # Кластер 5: Бесшовный Wi-Fi роуминг и Mesh-системы в квартирах
    [
        "как настроить mesh систему в большой квартире провайдер",
        "роутер keenetic mesh wi-fi обрывы при переходе между комнатами",
        "бесшовный роуминг 802.11k 802.11v настройка mesh узлов",
        "почему не переключается телефон на второй роутер в mesh сети",
        "подключение дополнительного репитера wi-fi усилителя сигнала",
        "настройка контроллера mesh wi-fi на домашней сети"
    ],
    # Кластер 6: Удаленное видеонаблюдение через P2P облако без статического IP
    [
        "видеонаблюдение p2p cloud hikvision dahua не в сети",
        "камера пишет статус offline в приложении без белого ip",
        "как настроить удаленный доступ к видеорегистратору через p2p",
        "роутер блокирует p2p соединение облака видеонаблюдения",
        "почему не работает трансляция с камеры через приложение на телефоне",
        "порты для облачного подключения камер cctv cloud connect"
    ]
]

async def seed_database(reset: bool = True):
    print(">>> Инициализация базы данных технической поддержки телеком-провайдера...")
    
    from app.core.database import check_db_connection_and_fallback, get_engine, get_sessionmaker
    await check_db_connection_and_fallback()
    
    engine = get_engine()
    session_maker = get_sessionmaker()
    
    # Создание таблиц при необходимости
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with session_maker() as session:
        if reset:
            print(">>> Полный сброс старых данных для чистой переиндексации...")
            await session.execute(delete(SearchLog))
            await session.execute(delete(SearchGapCluster))
            await session.execute(delete(Article))
            await session.execute(delete(Category))
            await session.commit()

        # 1. Проверка и создание пользователей по умолчанию
        admin_res = await session.execute(select(User).where(User.username == "admin"))
        admin_user = admin_res.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                email="admin@telecom.corp",
                username="admin",
                full_name="Администратор Системы",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN
            )
            moderator_user = User(
                email="moderator@telecom.corp",
                username="moderator",
                full_name="Модератор Базы Знаний",
                hashed_password=get_password_hash("moderator123"),
                role=UserRole.MODERATOR
            )
            operator_user = User(
                email="operator@telecom.corp",
                username="operator",
                full_name="Оператор 1-й Линии",
                hashed_password=get_password_hash("operator123"),
                role=UserRole.OPERATOR
            )
            session.add_all([admin_user, moderator_user, operator_user])
            await session.commit()
            await session.refresh(admin_user)
            print(">>> Созданы системные пользователи: admin, moderator, operator")

        # 2. Создание категорий телеком-провайдера
        category_map = {}
        for cat_info in CATEGORIES_DATA:
            cat = Category(**cat_info)
            session.add(cat)
            await session.flush()
            category_map[cat.slug] = cat.id
        await session.commit()
        print(f">>> Создано категорий телекома: {len(CATEGORIES_DATA)}")

        # 3. Создание 20 статей базы знаний с векторными эмбеддингами
        article_title_map = {}
        print(f">>> Генерация {len(ARTICLES_DATA)} статей техподдержки телекома с векторными эмбеддингами...")
        for idx, a_data in enumerate(ARTICLES_DATA, start=1):
            cat_id = category_map.get(a_data["category_slug"])
            text_to_embed = f"{a_data['title']}. {a_data['summary']} {a_data['content']} {a_data['tags']}"
            emb = embedding_service.encode(text_to_embed, normalize=True).tolist()
            
            art = Article(
                title=a_data["title"],
                summary=a_data["summary"],
                content=a_data["content"],
                tags=a_data["tags"],
                category_id=cat_id,
                created_by_id=admin_user.id,
                is_published=True,
                views_count=random.randint(25, 340),
                helpful_count=random.randint(18, 95),
                unhelpful_count=random.randint(0, 3),
                embedding=emb
            )
            session.add(art)
            await session.flush()
            article_title_map[art.title] = art.id
            print(f"    [{idx:02d}/{len(ARTICLES_DATA)}] Эмбеддинг: {art.title[:50]}...")
        await session.commit()

        # 4. Генерация реалистичных поисковых логов операторов
        print(">>> Генерация истории поисковых запросов и пробелов знаний...")
        now = datetime.now(timezone.utc)

        # 4.1. Успешные поиски (решение найдено и помогло)
        for query_text, art_title in SUCCESSFUL_QUERIES:
            art_id = article_title_map.get(art_title)
            for _ in range(random.randint(3, 6)):
                days_ago = random.randint(0, 6)
                hours_ago = random.randint(1, 23)
                t_stamp = now - timedelta(days=days_ago, hours=hours_ago)
                
                q_emb = embedding_service.encode(query_text, normalize=True).tolist()
                log = SearchLog(
                    query_text=query_text,
                    operator_id=admin_user.id,
                    search_type="hybrid",
                    results_count=random.randint(1, 4),
                    execution_time_ms=round(random.uniform(15.0, 42.0), 1),
                    returned_article_ids=[art_id] if art_id else [],
                    clicked_article_id=art_id,
                    is_helpful=True,
                    is_search_gap=False,
                    query_embedding=q_emb,
                    timestamp=t_stamp
                )
                session.add(log)

        # 4.2. Поисковые пробелы (0 результатов или ответ не помог оператору)
        for cluster_queries in GAP_CLUSTERS_DATA:
            for q_text in cluster_queries:
                for _ in range(random.randint(2, 4)):
                    days_ago = random.randint(0, 5)
                    t_stamp = now - timedelta(days=days_ago, hours=random.randint(1, 20))
                    
                    is_zero_result = random.random() > 0.25
                    results_count = 0 if is_zero_result else random.randint(1, 2)
                    
                    q_emb = embedding_service.encode(q_text, normalize=True).tolist()
                    gap_log = SearchLog(
                        query_text=q_text,
                        operator_id=admin_user.id,
                        search_type="hybrid",
                        results_count=results_count,
                        execution_time_ms=round(random.uniform(12.0, 32.0), 1),
                        returned_article_ids=[] if is_zero_result else [1],
                        clicked_article_id=None if is_zero_result else 1,
                        is_helpful=False,
                        is_search_gap=True,
                        query_embedding=q_emb,
                        timestamp=t_stamp
                    )
                    session.add(gap_log)

        await session.commit()
        print(">>> База знаний телекома успешно засеяна!")

        # 5. Запуск автоматической NLP-кластеризации для формирования карточек пробелов
        print(">>> Запуск автоматической кластеризации поисковых пробелов...")
        from app.services.clustering import clustering_service
        cluster_res = await clustering_service.cluster_unaddressed_gaps(session)
        print(f">>> Кластеризация завершена: {cluster_res['message']} (сформировано кластеров: {cluster_res['clusters_created']}, silhouette: {cluster_res['silhouette_score']})")

if __name__ == "__main__":
    reset_flag = True if "--no-reset" not in sys.argv else False
    asyncio.run(seed_database(reset=reset_flag))
