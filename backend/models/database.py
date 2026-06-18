"""
数据库连接管理 — 支持 PostgreSQL 和 SQLite
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from backend.config import settings
from backend.models.models import Base

# 确保 SQLite 目录存在
if settings.DB_TYPE == "sqlite":
    os.makedirs(os.path.dirname(settings.SQLITE_PATH), exist_ok=True)


def _get_connect_args():
    """根据数据库类型返回连接参数"""
    if settings.DB_TYPE == "sqlite":
        return {"check_same_thread": False}
    return {}


def _get_engine_kwargs(is_async: bool = False):
    """根据数据库类型返回引擎参数"""
    kwargs = {"echo": settings.DEBUG}
    if settings.DB_TYPE == "sqlite":
        kwargs["connect_args"] = _get_connect_args()
    else:
        kwargs["pool_size"] = 20
        kwargs["max_overflow"] = 10
        kwargs["pool_pre_ping"] = True
    return kwargs


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 优化：开启 WAL 模式 + 外键"""
    if settings.DB_TYPE == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# 异步引擎（FastAPI 使用）
async_engine = create_async_engine(
    settings.DATABASE_URL,
    **_get_engine_kwargs(is_async=True),
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 同步引擎（Celery / Alembic 使用）
_sync_kwargs = _get_engine_kwargs(is_async=False)
if settings.DB_TYPE == "sqlite":
    _sync_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _sync_kwargs["pool_size"] = 10
    _sync_kwargs["max_overflow"] = 5

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    **_sync_kwargs,
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await async_engine.dispose()
