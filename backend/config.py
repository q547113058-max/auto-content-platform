"""
全局配置模块
环境变量优先级: .env > 系统环境变量 > 默认值
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # --- 应用 ---
    APP_NAME: str = "AutoContentPlatform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    API_PREFIX: str = "/api/v1"

    # --- 数据库 ---
    DB_TYPE: str = "sqlite"  # sqlite / postgresql（优先 PG，失败自动降级 SQLite）
    DB_HOST: str = "192.168.0.170"
    DB_PORT: int = 5433
    DB_USER: str = "ai_ugc"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ai_ugc"
    SQLITE_PATH: str = str(BASE_DIR / "data" / "auto_content_platform.db")

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL.replace("redis://", "redis://") + "?broker_use_ssl=False"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # --- MinIO (对象存储) ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "auto-content-platform"
    MINIO_SECURE: bool = False

    # --- Playwright ---
    PLAYWRIGHT_CDP_URL: str = "http://localhost:9222"
    PLAYWRIGHT_HEADLESS: bool = True
    # 反检测模式：playwright / patchright
    PLAYWRIGHT_MODE: str = "playwright"

    # --- AI 模型 ---
    AI_PROVIDER: str = "deepseek"  # deepseek / qwen / openai
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    QWEN_API_KEY: Optional[str] = None
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    AI_MODEL: str = "deepseek-chat"  # 默认模型
    AI_TEMPERATURE: float = 0.7
    AI_MAX_TOKENS: int = 4096

    # --- AI 图片生成 ---
    IMAGE_GEN_PROVIDER: str = "agnes"  # agnes / seedream / tongyi-wanxiang
    IMAGE_GEN_API_KEY: Optional[str] = None
    IMAGE_GEN_API_BASE: str = "https://apihub.agnes-ai.com/v1"
    IMAGE_GEN_MODEL: str = "agnes-image-2.1-flash"  # Agnes 图片模型

    # --- 代理 IP ---
    PROXY_ENABLED: bool = False
    PROXY_PROVIDER: str = ""  # kuaidaili / zhimadaili
    PROXY_API_URL: str = ""
    PROXY_USERNAME: str = ""
    PROXY_PASSWORD: str = ""

    # --- 存储路径 ---
    STORAGE_STATES_DIR: str = str(BASE_DIR / "storage_states")
    SCREENSHOTS_DIR: str = str(BASE_DIR / "screenshots")
    ERROR_SCREENSHOTS_DIR: str = str(BASE_DIR / "error_screenshots")
    PROMPTS_DIR: str = str(BASE_DIR / "backend" / "prompts")

    # --- 发布限频 ---
    RATE_LIMITS: dict = {
        "xiaohongshu": {"max_per_day": 5, "min_interval_minutes": 30},
        "zhihu": {"max_per_day": 3, "min_interval_minutes": 60},
        "weibo": {"max_per_day": 10, "min_interval_minutes": 15},
        "wechat": {"max_per_day": 1, "min_interval_minutes": 0},
        "toutiao": {"max_per_day": 5, "min_interval_minutes": 30},
        "douyin": {"max_per_day": 3, "min_interval_minutes": 60},
    }

    # --- 会话管理 ---
    SESSION_CHECK_INTERVAL_HOURS: int = 6
    SESSION_COOKIE_EXPIRY_DAYS: int = 30

    # --- 数据采集 ---
    SCRAPE_INTERVAL_HOURS: int = 6
    SCRAPE_RETENTION_DAYS: int = 90

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
