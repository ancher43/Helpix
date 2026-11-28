import asyncio
import sys
import os
import random

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.core.database import check_db_connection_and_fallback, get_sessionmaker
from app.models.user import User, UserRole
from app.models.article import Article
from app.models.search_log import SearchLog
from app.core.security import get_password_hash

async def seed():
    await check_db_connection_and_fallback()
    session_maker = get_sessionmaker()
    
    async with session_maker() as session:
        # 1. Update existing admin, moderator, operator
        res = await session.execute(select(User))
        users = {u.username: u for u in res.scalars().all()}
        
        if "admin" in users:
            users["admin"].full_name = "Смирнов Алексей Викторович"
            users["admin"].position = "Главный системный администратор"
            users["admin"].department = "ИТ-департамент и инфраструктура"
            users["admin"].phone = "101"
            users["admin"].email = "admin@telecom.corp"
            
        if "moderator" in users:
            users["moderator"].full_name = "Ковалева Елена Сергеевна"
            users["moderator"].position = "Ведущий инженер / Тимлид базы знаний"
            users["moderator"].department = "Служба экспертной поддержки"
            users["moderator"].phone = "204"
            users["moderator"].email = "moderator@telecom.corp"
            
        if "operator" in users:
            users["operator"].full_name = "Иванов Денис Игоревич"
            users["operator"].position = "Специалист 1-й линии техподдержки"
            users["operator"].department = "Отдел технической поддержки ШПД"
            users["operator"].phone = "312"
            users["operator"].email = "operator@telecom.corp"
            
        # 2. Add extra realistic operators & engineers if not present
        extra_users = [
            {
                "username": "morozov",
                "email": "morozov@telecom.corp",
                "full_name": "Морозов Артем Павлович",
                "position": "Специалист 1-й линии техподдержки",
                "department": "Отдел технической поддержки ШПД",
                "phone": "314",
                "role": UserRole.OPERATOR,
                "password": "operator123"
            },
            {
                "username": "volkova",
                "email": "volkova@telecom.corp",
                "full_name": "Волкова Анастасия Дмитриевна",
                "position": "Специалист 2-й линии (IPTV и ТВ-сервисы)",
                "department": "Сектор цифрового телевидения",
                "phone": "218",
                "role": UserRole.OPERATOR,
                "password": "operator123"
            },
            {
                "username": "fedorov",
                "email": "fedorov@telecom.corp",
                "full_name": "Федоров Михаил Александрович",
                "position": "Инженер сетевой инфраструктуры (NOC)",
                "department": "Группа мониторинга сети",
                "phone": "109",
                "role": UserRole.MODERATOR,
                "password": "moderator123"
            }
        ]
        
        for u_data in extra_users:
            if u_data["username"] not in users:
                new_u = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    full_name=u_data["full_name"],
                    position=u_data["position"],
                    department=u_data["department"],
                    phone=u_data["phone"],
                    role=u_data["role"],
                    hashed_password=get_password_hash(u_data["password"])
                )
                session.add(new_u)
                
        await session.commit()
        
        # Reload all users
        res = await session.execute(select(User))
        all_users = res.scalars().all()
        user_by_role = {}
        for u in all_users:
            user_by_role.setdefault(u.role, []).append(u)
            
        print(f"Users in DB: {len(all_users)}")
        for u in all_users:
            print(f"  [{u.role.value}] {u.username}: {u.full_name} ({u.position})")
            
        # 3. Assign authors to articles
        mod_users = user_by_role.get(UserRole.MODERATOR, [])
        adm_users = user_by_role.get(UserRole.ADMIN, [])
        potential_authors = (mod_users * 3) + adm_users
        
        art_res = await session.execute(select(Article))
        articles = art_res.scalars().all()
        for idx, art in enumerate(articles):
            author = potential_authors[idx % len(potential_authors)]
            art.created_by_id = author.id
            if idx % 3 == 0 and len(potential_authors) > 1:
                editor = potential_authors[(idx + 1) % len(potential_authors)]
                art.updated_by_id = editor.id
        print(f"Assigned authors to {len(articles)} articles.")
        
        # 4. Assign operators to search logs
        op_users = user_by_role.get(UserRole.OPERATOR, []) + mod_users
        log_res = await session.execute(select(SearchLog))
        logs = log_res.scalars().all()
        for idx, l in enumerate(logs):
            op = op_users[idx % len(op_users)]
            l.operator_id = op.id
        print(f"Assigned operators to {len(logs)} search logs.")
        
        await session.commit()
        print(">>> Seeding user profiles and linkages finished successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
