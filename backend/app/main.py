import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import Base, get_engine, get_sessionmaker
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.api import auth, articles, search, gaps, stats
from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check database and fallback if PostgreSQL credentials not yet configured
    from app.core.database import check_db_connection_and_fallback, get_engine, get_sessionmaker
    await check_db_connection_and_fallback()
    
    engine = get_engine()
    # Startup: ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = get_sessionmaker()
    # Create default admin and operator if database is empty
    async with session_maker() as session:
        result = await session.execute(select(User).limit(1))
        if not result.scalar_one_or_none():
            admin_user = User(
                email="admin@helpdesk.local",
                username="admin",
                full_name="Администратор Системы",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN
            )
            moderator_user = User(
                email="moderator@helpdesk.local",
                username="moderator",
                full_name="Модератор Базы Знаний",
                hashed_password=get_password_hash("moderator123"),
                role=UserRole.MODERATOR
            )
            operator_user = User(
                email="operator@helpdesk.local",
                username="operator",
                full_name="Оператор 1-й Линии",
                hashed_password=get_password_hash("operator123"),
                role=UserRole.OPERATOR
            )
            session.add_all([admin_user, moderator_user, operator_user])
            await session.commit()
            print(">>> Default users created: admin/admin123, moderator/moderator123, operator/operator123")
    
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Информационная система управления базой знаний службы технической поддержки с гибридным поиском и кластеризацией пробелов.",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(articles.router, prefix=settings.API_V1_STR)
app.include_router(search.router, prefix=settings.API_V1_STR)
app.include_router(gaps.router, prefix=settings.API_V1_STR)
app.include_router(stats.router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

from fastapi.responses import FileResponse, Response
from pathlib import Path

# Resolve root D:\VKR directory (3 levels up from app/main.py)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dir = ROOT_DIR / "frontend"
frontend_dist = frontend_dir / "dist"
target_static = frontend_dist if frontend_dist.exists() else frontend_dir

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = target_static / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), headers=NO_CACHE_HEADERS)
    return {"error": "Frontend index.html not found", "looked_in": str(index_file)}

@app.get("/app.js", include_in_schema=False)
async def serve_js():
    js_file = target_static / "app.js"
    if js_file.exists():
        return FileResponse(str(js_file), media_type="application/javascript", headers=NO_CACHE_HEADERS)
    return {"error": "Frontend app.js not found", "looked_in": str(js_file)}

@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    svg_file = target_static / "favicon.svg"
    if svg_file.exists():
        return FileResponse(str(svg_file), media_type="image/svg+xml")
    ico_file = target_static / "favicon.ico"
    if ico_file.exists():
        return FileResponse(str(ico_file), media_type="image/x-icon")
    return Response(status_code=204)

if target_static.exists():
    app.mount("/static", StaticFiles(directory=str(target_static)), name="static")
