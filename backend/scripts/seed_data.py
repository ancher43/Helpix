import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone

# Add parent directory to path so app modules can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import Base
from app.models.user import User, UserRole
from app.models.article import Category, Article
from app.models.search_log import SearchLog
from app.models.cluster import SearchGapCluster
from app.core.security import get_password_hash
from app.services.embedding import embedding_service

# Predefined categories
CATEGORIES_DATA = [
    {"name": "Сетевые подключения и VPN", "slug": "network-vpn", "description": "Настройка корпоративного VPN, Wi-Fi, DNS, прокси и маршрутизации."},
    {"name": "Учётные записи и Доступ", "slug": "auth-access", "description": "Active Directory, сброс паролей, 2FA, права доступа и роли."},
    {"name": "Рабочие станции и ПО", "slug": "workstations-software", "description": "Операционные системы Windows/Linux, офисные пакеты, корпоративный софт."},
    {"name": "Периферия и Оргтехника", "slug": "hardware-printers", "description": "Сетевые принтеры, МФУ, сканеры, мониторы, гарнитуры."},
    {"name": "Базы данных и Серверы", "slug": "servers-databases", "description": "PostgreSQL, Linux-серверы, резервное копирование, права в СУБД."}
]

ARTICLES_DATA = [
    # Network & VPN (RU)
    {
        "title": "Настройка подключения к корпоративному VPN (OpenVPN/WireGuard)",
        "summary": "Инструкция по установке конфигурационного файла и первому подключению к офисной сети.",
        "category_slug": "network-vpn",
        "language": "ru",
        "tags": "vpn, openvpn, wireguard, сеть, удаленка, подключение",
        "content": """### Инструкция по настройке VPN
1. Скачайте официальный клиент OpenVPN Connect или WireGuard с корпоративного портала.
2. Получите конфигурационный файл (.ovpn или .conf) у вашего системного администратора.
3. Импортируйте профиль в программу.
4. Введите учетные данные домена (логин без @domain и корпоративный пароль).
5. При включенной двухфакторной аутентификации введите код из приложения Authenticator.
6. В случае ошибки 'TLS handshake failed' проверьте дату и время на компьютере."""
    },
    {
        "title": "Устранение ошибки 'DNS_PROBE_FINISHED_NO_INTERNET' при работе через корпоративный прокси",
        "summary": "Пошаговый чек-лист решения сетевых сбоев разрешения доменных имен.",
        "category_slug": "network-vpn",
        "language": "ru",
        "tags": "dns, сеть, интернет, прокси, ipconfig, flushdns",
        "content": """### Решение проблемы с DNS:
1. Откройте командную строку (cmd) от имени администратора.
2. Выполните команду очистки кэша DNS:
   `ipconfig /flushdns`
3. Сбросьте сетевой стек:
   `netsh winsock reset`
4. Проверьте адрес корпоративного DNS-сервера в свойствах сетевого адаптера (должен стоять 10.0.0.2 или авто).
5. Перезагрузите сетевой адаптер."""
    },
    # Network & VPN (EN)
    {
        "title": "Corporate Wi-Fi Certificate Installation and Troubleshooting",
        "summary": "How to install the enterprise root CA certificate to access the secure 802.1X corporate Wi-Fi.",
        "category_slug": "network-vpn",
        "language": "en",
        "tags": "wifi, network, certificate, 802.1x, ssl, wpa2-enterprise",
        "content": """### Wi-Fi Configuration Guide:
1. Connect to the temporary 'Guest-Onboarding' network.
2. Download the corporate root certificate 'CorpRootCA.crt'.
3. Double-click the certificate, click 'Install Certificate', select 'Local Machine'.
4. Place it in 'Trusted Root Certification Authorities'.
5. Now select the 'Corp-Secure' Wi-Fi, enter your domain credentials and accept the server certificate."""
    },

    # Auth & Access (RU)
    {
        "title": "Самостоятельный сброс пароля доменной учетной записи через SSPR",
        "summary": "Порядок действий при блокировке пароля Active Directory или истечении срока его действия.",
        "category_slug": "auth-access",
        "language": "ru",
        "tags": "пароль, active directory, sspr, блокировка, доступ, учетка",
        "content": """### Инструкция по сбросу пароля:
1. Перейдите на портал самообслуживания https://password.corp.local.
2. Введите ваш корпоративный логин (имя пользователя).
3. Подтвердите личность через SMS-код или звонок на привязанный рабочий телефон.
4. Задайте новый пароль (минимум 12 символов, включая заглавные буквы, цифры и спецсимволы).
5. Обратите внимание: пароль не должен совпадать с предыдущими 5 паролями.
6. После смены пароля обновите учетные данные в Outlook и Teams."""
    },
    {
        "title": "Настройка двухфакторной аутентификации (2FA) через мобильное приложение",
        "summary": "Привязка корпоративного аккаунта к Google Authenticator или Microsoft Authenticator.",
        "category_slug": "auth-access",
        "language": "ru",
        "tags": "2fa, mfa, токен, аутентификация, безопасность, authenticator",
        "content": """### Настройка 2FA:
1. Установите приложение Microsoft Authenticator или Google Authenticator на смартфон.
2. Зайдите в личный кабинет сотрудника на странице https://auth.corp.local/setup.
3. Отсканируйте отобразившийся QR-код камерой приложения.
4. Введите 6-значный одноразовый код проверки.
5. Обязательно сохраните резервные коды восстановления в надежном месте."""
    },
    # Auth & Access (EN)
    {
        "title": "How to Request Temporary Privileged Access via PAM Portal",
        "summary": "Standard procedure for engineers to obtain temporary elevated administrator rights.",
        "category_slug": "auth-access",
        "language": "en",
        "tags": "pam, access, permissions, admin, privilege, cyberark",
        "content": """### Requesting Elevated Rights:
1. Open the PAM portal at https://pam.corp.local.
2. Select target server/system and required role.
3. Provide valid Jira ticket ID and business justification.
4. Once manager approves, check out the one-time session credentials.
5. Max session duration is 4 hours, all actions are audited."""
    },

    # Workstations & Software (RU)
    {
        "title": "Очистка кэша Microsoft Teams при зависании и сбоях звонков",
        "summary": "Инструкция по полному сбросу временных файлов Teams на Windows 10/11.",
        "category_slug": "workstations-software",
        "language": "ru",
        "tags": "teams, звонки, кэш, зависание, глюк, microsoft",
        "content": """### Сброс кэша Teams:
1. Закройте Teams (кликните правой кнопкой по значку в трее -> Выход).
2. Нажмите Win + R, введите:
   `%appdata%\\Microsoft\\Teams`
3. Удалите содержимое папок: `application cache`, `blob_storage`, `Cache`, `databases`, `GPUCache`, `IndexedDB`.
4. Перезапустите Teams и выполните повторный вход."""
    },
    {
        "title": "Исправление ошибки запуска Outlook 'Не удается открыть набор папок'",
        "summary": "Восстановление поврежденного профиля почты и файла данных .ost.",
        "category_slug": "workstations-software",
        "language": "ru",
        "tags": "outlook, почта, ost, ошибка, сбой, папки, office",
        "content": """### Восстановление профиля Outlook:
1. Закройте Outlook.
2. Откройте 'Панель управления' -> 'Mail (Microsoft Outlook)'.
3. Нажмите 'Показать профили' -> 'Добавить'.
4. Введите имя нового профиля и следуйте мастеру автоматической настройки учетной записи.
5. Установите созданный профиль в качестве профиля по умолчанию.
6. При повреждении файла .ost его можно удалить из `%localappdata%\\Microsoft\\Outlook`, он скачается заново с Exchange."""
    },
    {
        "title": "Установка и лицензирование корпоративного антивируса Kaspersky / Dr.Web",
        "summary": "Порядок развертывания антивирусного агента через централизованную консоль.",
        "category_slug": "workstations-software",
        "language": "ru",
        "tags": "антивирус, kaspersky, drweb, безопасность, лицензия",
        "content": """### Установка антивируса:
1. Скачайте сетевой установщик из каталога общего доступа `\\\\corp-fs\\soft\\antivirus`.
2. Запустите инсталлятор с правами администратора.
3. Программа автоматически подключится к Security Center (10.0.1.50) и подтянет лицензионный ключ.
4. Дождитесь завершения первоначального сканирования системы."""
    },
    # Workstations & Software (EN)
    {
        "title": "Resolving Windows Blue Screen of Death (BSOD) Driver Verifier Errors",
        "summary": "Diagnostic guide to analyze minidump files and locate faulty hardware drivers.",
        "category_slug": "workstations-software",
        "language": "en",
        "tags": "bsod, crash, windows, minidump, driver, blue screen",
        "content": """### BSOD Troubleshooting:
1. Check the Stop Code shown on the crash screen (e.g., DRIVER_IRQL_NOT_LESS_OR_EQUAL).
2. Use BlueScreenView or WinDbg to open minidumps located in `C:\\Windows\\Minidump`.
3. Identify the faulty sys driver.
4. Boot into Safe Mode and roll back or update the flagged driver in Device Manager."""
    },

    # Hardware & Printers (RU)
    {
        "title": "Подключение сетевого принтера/МФУ по IP-адресу в офисе",
        "summary": "Добавление офисного принтера через панель управления Windows без вызова инженера.",
        "category_slug": "hardware-printers",
        "language": "ru",
        "tags": "принтер, печать, мфу, драйвер, сканер, ip",
        "content": """### Добавление сетевого принтера:
1. Узнайте IP-адрес принтера (наклейка на корпусе или отчет о конфигурации).
2. Откройте 'Параметры Windows' -> 'Устройства' -> 'Принтеры и сканеры'.
3. Нажмите 'Добавить принтер или сканер', затем 'Необходимый принтер отсутствует в списке'.
4. Выберите 'Добавить принтер по TCP/IP-адресу' и введите IP принтера.
5. Выберите драйвер 'Generic PCL6' или укажите путь к корпоративному хранилищу драйверов.
6. Распечатайте пробную страницу."""
    },
    {
        "title": "Решение проблемы 'Очередь печати зависла' (Spooler error)",
        "summary": "Сброс службы очереди печати Print Spooler и удаление зависших заданий.",
        "category_slug": "hardware-printers",
        "language": "ru",
        "tags": "принтер, печать, зависла, spooler, спулер, очередь",
        "content": """### Очистка очереди печати:
1. Запустите командную строку от имени администратора.
2. Остановите службу печати:
   `net stop spooler`
3. Удалите зависшие файлы из папки:
   `del /Q /F %systemroot%\\System32\\Spool\\Printers\\*`
4. Запустите службу печати:
   `net start spooler`
5. Повторите отправку документа на печать."""
    },
    # Hardware & Printers (EN)
    {
        "title": "Polycom and Jabra Headset Audio Configuration for Video Calls",
        "summary": "Setting default audio input/output devices and resolving microphone mute state.",
        "category_slug": "hardware-printers",
        "language": "en",
        "tags": "audio, headset, mic, microphone, sound, jabra, polycom",
        "content": """### Audio Troubleshooting:
1. Ensure the USB dongle or cable is plugged directly into the PC, not an unpowered hub.
2. Open Windows Sound Settings and verify the headset is set as Default Communication Device.
3. In Teams/Zoom Settings -> Audio, manually select the device instead of 'System Default'.
4. Check physical mute button and boom mic position."""
    },

    # Infrastructure & Databases (RU)
    {
        "title": "Подключение к PostgreSQL через pgAdmin и устранение ошибки 'FATAL: password authentication failed'",
        "summary": "Диагностика учетных записей СУБД, файла pg_hba.conf и разрешений сети.",
        "category_slug": "servers-databases",
        "language": "ru",
        "tags": "postgresql, pgadmin, sql, база данных, пароль, ошибка, psql",
        "content": """### Решение ошибки авторизации PostgreSQL:
1. Проверьте правильность порта (по умолчанию 5432, тестовые инстансы могут быть на 5433).
2. Убедитесь, что логин и пароль вводятся с учетом регистра.
3. Проверьте настройки файла `pg_hba.conf`: метод аутентификации должен быть scram-sha-256 или md5.
4. Если пароль утерян, смените его через консоль суперпользователя:
   `ALTER USER postgres WITH PASSWORD 'новый_пароль';`
5. Перезагрузите службу сервера PostgreSQL."""
    },
    {
        "title": "Создание и восстановление резервных копий баз данных PostgreSQL (pg_dump / pg_restore)",
        "summary": "Шпаргалка по созданию дампов БД в различных форматах и аварийному восстановлению.",
        "category_slug": "servers-databases",
        "language": "ru",
        "tags": "резервная копия, бэкап, pg_dump, pg_restore, sql, дамп",
        "content": """### Создание дампа базы данных:
`pg_dump -U postgres -h localhost -F c -b -v -f "backup.dump" dbname`
### Восстановление из дампа:
`pg_restore -U postgres -h localhost -d dbname -v "backup.dump"`"""
    },
    # Infrastructure & Databases (EN)
    {
        "title": "SSH Key Pair Generation and Bastion Host Access Configuration",
        "summary": "How to generate ED25519 SSH keys and configure SSH config for jumpserver authentication.",
        "category_slug": "servers-databases",
        "language": "en",
        "tags": "ssh, linux, server, bastion, ed25519, terminal, key",
        "content": """### SSH Setup Guide:
1. Generate key: `ssh-keygen -t ed25519 -C "user@corp"`
2. Add public key to ~/.ssh/authorized_keys on the bastion host.
3. Configure `~/.ssh/config`:
   Host bastion
     HostName 198.51.100.1
     User developer
     IdentityFile ~/.ssh/id_ed25519"""
    }
]

# SIMULATED SEARCH QUERIES
# Category 1: Successful queries (results found, helped = True)
SUCCESSFUL_QUERIES = [
    ("как настроить vpn openvpn", "Настройка подключения к корпоративному VPN (OpenVPN/WireGuard)"),
    ("подключение к офисной сети wireguard", "Настройка подключения к корпоративному VPN (OpenVPN/WireGuard)"),
    ("ошибка dns_probe_finished_no_internet", "Устранение ошибки 'DNS_PROBE_FINISHED_NO_INTERNET' при работе через корпоративный прокси"),
    ("как очистить кэш dns ipconfig flushdns", "Устранение ошибки 'DNS_PROBE_FINISHED_NO_INTERNET' при работе через корпоративный прокси"),
    ("how to install wifi certificate", "Corporate Wi-Fi Certificate Installation and Troubleshooting"),
    ("забыл пароль от учетной записи active directory", "Самостоятельный сброс пароля доменной учетной записи через SSPR"),
    ("сбросить пароль sspr", "Самостоятельный сброс пароля доменной учетной записи через SSPR"),
    ("двухфакторная аутентификация google authenticator", "Настройка двухфакторной аутентификации (2FA) через мобильное приложение"),
    ("завис teams очистить кэш", "Очистка кэша Microsoft Teams при зависании и сбоях звонков"),
    ("не удается открыть набор папок outlook ost", "Исправление ошибки запуска Outlook 'Не удается открыть набор папок'"),
    ("как подключить сетевой принтер по ip", "Подключение сетевого принтера/МФУ по IP-адресу в офисе"),
    ("очередь печати зависла print spooler", "Решение проблемы 'Очередь печати зависла' (Spooler error)"),
    ("ошибка авторизации postgresql pgadmin fatal password", "Подключение к PostgreSQL через pgAdmin и устранение ошибки 'FATAL: password authentication failed'"),
    ("how to make database backup pg_dump", "Создание и восстановление резервных копий баз данных PostgreSQL (pg_dump / pg_restore)")
]

# Category 2: SEARCH GAPS (Topics NOT covered in KB, 0 results or answer did not help!)
# We formulate realistic groups of queries that should naturally cluster together:
GAP_CLUSTERS_DATA = [
    # Cluster A: Docker WSL2 Daemon issues (RU & EN)
    [
        "Ошибка docker daemon не запускается в wsl2",
        "docker Desktop wsl error failed to start daemon",
        "wsl2 docker daemon is not running can not connect",
        "не стартует служба докер в подсистеме wsl",
        "Docker Desktop stopped unexpectedly WSL error",
        "wsl --shutdown не помогает запустить docker daemon",
        "Docker daemon crash in Windows 11 WSL2"
    ],
    # Cluster B: Rutoken / Smart Card CryptoPro digital signature issues (RU)
    [
        "Сброс пин-кода Rutoken ЭЦП",
        "Ошибка сертификата криптопро 0x80090016",
        "Заблокирован смарт-токен JaCarta пин код пользователя",
        "Рутокен ЭЦП не определяется в системе плагин госуслуг",
        "КриптоПро CSP не видит сертификат на флешке токена",
        "Пин-код администратора Rutoken по умолчанию",
        "Ошибка 0x80090016 при подписании документа криптопро"
    ],
    # Cluster C: Multiple monitors via Type-C Hub / DisplayPort (RU & EN)
    [
        "Как подключить второй монитор через DisplayPort type-c",
        "type-c hub external display not detected black screen",
        "Ноутбук не видит второй монитор через док-станцию usb-c",
        "Type-c dock station hdmi no signal on second monitor",
        "Мерцает монитор подключенный через переходник thunderbolt",
        "DisplayPort over USB-C monitor signal lost"
    ],
    # Cluster D: Git LFS / Large files rejection on push (RU & EN)
    [
        "Git push rejected file exceeds 100mb limit git-lfs",
        "Ошибка git lfs при пуше большого файла в репозиторий",
        "how to migrate existing large files to git lfs",
        "Git remote reject file size larger than 100MB",
        "Как настроить git-lfs на рабочем компьютере"
    ]
]

async def seed_database():
    print(">>> Starting database seeding...")
    
    from app.core.database import check_db_connection_and_fallback, get_engine, get_sessionmaker
    await check_db_connection_and_fallback()
    
    engine = get_engine()
    session_maker = get_sessionmaker()
    
    # 1. Create tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with session_maker() as session:
        # Check existing categories
        cat_result = await session.execute(select(Category))
        categories = cat_result.scalars().all()
        
        category_map = {}
        if not categories:
            print(">>> Creating categories...")
            for cat_info in CATEGORIES_DATA:
                c = Category(**cat_info)
                session.add(c)
                await session.flush()
                category_map[c.slug] = c.id
            await session.commit()
        else:
            for c in categories:
                category_map[c.slug] = c.id

        # 2. Check existing articles
        art_result = await session.execute(select(Article))
        articles = art_result.scalars().all()
        article_title_map = {}

        if not articles:
            print(f">>> Creating {len(ARTICLES_DATA)} articles with embeddings (multilingual)...")
            for idx, a_data in enumerate(ARTICLES_DATA, start=1):
                cat_id = category_map.get(a_data["category_slug"])
                text_to_embed = f"{a_data['title']}. {a_data['summary']} {a_data['content']} {a_data['tags']}"
                emb = embedding_service.encode(text_to_embed, normalize=True).tolist()
                
                art = Article(
                    title=a_data["title"],
                    summary=a_data["summary"],
                    content=a_data["content"],
                    tags=a_data["tags"],
                    language=a_data["language"],
                    category_id=cat_id,
                    is_published=True,
                    views_count=random.randint(15, 240),
                    helpful_count=random.randint(10, 85),
                    unhelpful_count=random.randint(0, 4),
                    embedding=emb
                )
                session.add(art)
                await session.flush()
                article_title_map[art.title] = art.id
                print(f"    [{idx}/{len(ARTICLES_DATA)}] Embedded article: {art.title[:45]}...")
            await session.commit()
        else:
            for a in articles:
                article_title_map[a.title] = a.id

        # 3. Create realistic search logs (successful + search gaps)
        log_count_res = await session.execute(select(SearchLog))
        if len(log_count_res.scalars().all()) < 20:
            print(">>> Generating simulated search query logs and search gaps...")
            now = datetime.now(timezone.utc)

            # Generate successful searches
            for query_text, art_title in SUCCESSFUL_QUERIES:
                art_id = article_title_map.get(art_title)
                for _ in range(random.randint(3, 7)):
                    days_ago = random.randint(0, 6)
                    hours_ago = random.randint(1, 23)
                    t_stamp = now - timedelta(days=days_ago, hours=hours_ago)
                    
                    q_emb = embedding_service.encode(query_text, normalize=True).tolist()
                    log = SearchLog(
                        query_text=query_text,
                        search_type="hybrid",
                        results_count=random.randint(1, 4),
                        execution_time_ms=round(random.uniform(18.0, 45.0), 1),
                        returned_article_ids=[art_id] if art_id else [],
                        clicked_article_id=art_id,
                        is_helpful=True,
                        is_search_gap=False,
                        query_embedding=q_emb,
                        timestamp=t_stamp
                    )
                    session.add(log)

            # Generate GAP searches (0 results OR operator marked 'Answer didn't help')
            for cluster_queries in GAP_CLUSTERS_DATA:
                for q_text in cluster_queries:
                    for _ in range(random.randint(2, 4)):
                        days_ago = random.randint(0, 5)
                        t_stamp = now - timedelta(days=days_ago, hours=random.randint(1, 20))
                        
                        # 70% chance of 0 results, 30% chance of results > 0 with is_helpful = False
                        is_zero_result = random.random() > 0.3
                        results_count = 0 if is_zero_result else random.randint(1, 2)
                        
                        q_emb = embedding_service.encode(q_text, normalize=True).tolist()
                        gap_log = SearchLog(
                            query_text=q_text,
                            search_type="hybrid",
                            results_count=results_count,
                            execution_time_ms=round(random.uniform(15.0, 35.0), 1),
                            returned_article_ids=[] if is_zero_result else [1],
                            clicked_article_id=None if is_zero_result else 1,
                            is_helpful=False,  # Operator explicitly flagged 'Didn't help' or no results
                            is_search_gap=True,
                            query_embedding=q_emb,
                            timestamp=t_stamp
                        )
                        session.add(gap_log)

            await session.commit()
            print(">>> Seed data created successfully: Categories, Articles, Embeddings, Search Logs, Search Gaps!")
        else:
            print(">>> Database already contains search logs, skipping log generation.")

if __name__ == "__main__":
    asyncio.run(seed_database())
