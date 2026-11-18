import os
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

PG_URL = settings.async_database_url
SQLITE_URL = "sqlite+aiosqlite:///D:/VKR/backend/local_vkr.db"

class DatabaseManager:
    engine: AsyncEngine = None
    session_maker: async_sessionmaker = None
    is_sqlite: bool = False

    @classmethod
    def init(cls):
        if cls.engine is None:
            cls.engine = create_async_engine(
                PG_URL,
                echo=False,
                future=True,
                pool_pre_ping=True
            )
            cls.session_maker = async_sessionmaker(
                bind=cls.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )

    @classmethod
    async def check_and_fallback(cls):
        cls.init()
        try:
            async with cls.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info(f"Connected to PostgreSQL at {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed ({e}). Switching to local SQLite storage.")
            cls.is_sqlite = True
            cls.engine = create_async_engine(SQLITE_URL, echo=False)
            cls.session_maker = async_sessionmaker(
                bind=cls.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )

DatabaseManager.init()

# Compatibility proxies
def get_engine() -> AsyncEngine:
    return DatabaseManager.engine

def get_sessionmaker() -> async_sessionmaker:
    return DatabaseManager.session_maker

async def check_db_connection_and_fallback():
    await DatabaseManager.check_and_fallback()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with DatabaseManager.session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
