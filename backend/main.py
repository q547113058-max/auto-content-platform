"""
AutoContentPlatform — FastAPI 主入口
"""
import sys
import asyncio

# Windows 下强制使用 ProactorEventLoop，Playwright subprocess 需要
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from backend.config import settings
from backend.models.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"=== {settings.APP_NAME} v{settings.APP_VERSION} 启动 ===")
    await init_db()
    logger.info("数据库表初始化完成")

    # 启动定时调度器
    try:
        from backend.services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        logger.info("定时调度器已启动")
    except Exception as e:
        logger.warning(f"定时调度器启动失败（非致命）: {e}")

    yield

    # 停止调度器
    try:
        from backend.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    await close_db()
    logger.info("=== 应用关闭 ===")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="多平台图文内容自动化运营系统",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": __import__("datetime").datetime.now().isoformat()}


# ========== 静态文件 ==========
uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# ========== 注册路由 ==========
from backend.routers import products, accounts, contents, publish, metrics, optimizer, prompts, sessions, engagement, db, knowledge, topic, companies

app.include_router(products.router, prefix=f"{settings.API_PREFIX}/products", tags=["产品管理"])
app.include_router(accounts.router, prefix=f"{settings.API_PREFIX}/accounts", tags=["账号管理"])
app.include_router(contents.router, prefix=f"{settings.API_PREFIX}/contents", tags=["内容管理"])
app.include_router(publish.router, prefix=f"{settings.API_PREFIX}/publish", tags=["发布管理"])
app.include_router(metrics.router, prefix=f"{settings.API_PREFIX}/metrics", tags=["数据分析"])
app.include_router(optimizer.router, prefix=f"{settings.API_PREFIX}/optimizer", tags=["优化学习"])
app.include_router(prompts.router, prefix=f"{settings.API_PREFIX}/prompts", tags=["提示词管理"])
app.include_router(sessions.router, prefix=f"{settings.API_PREFIX}/sessions", tags=["会话管理"])
app.include_router(engagement.router, prefix=f"{settings.API_PREFIX}/engagement", tags=["评论互动"])
app.include_router(db.router, prefix=f"{settings.API_PREFIX}/db", tags=["数据库浏览"])
app.include_router(knowledge.router, prefix=f"{settings.API_PREFIX}/knowledge", tags=["知识库"])
app.include_router(companies.router, prefix=f"{settings.API_PREFIX}/companies", tags=["公司管理"])
app.include_router(topic.router, prefix=f"{settings.API_PREFIX}/topics", tags=["选题策划"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
