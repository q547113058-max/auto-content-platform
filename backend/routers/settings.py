"""
Settings API — 读取/修改 .env 配置
"""
import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.config import settings

router = APIRouter()

# .env 文件路径（项目根目录）
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _mask_key(key: str) -> str:
    """遮蔽 API Key，仅显示前4后4字符"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]


class SettingsResponse(BaseModel):
    """当前配置（API Key 脱敏）"""
    # AI 模型
    ai_provider: str
    ai_api_key: str          # 脱敏后的 key
    ai_api_key_set: bool     # 是否已配置
    ai_api_base: str
    ai_model: str
    ai_temperature: float
    ai_max_tokens: int
    # 图片生成
    image_gen_provider: str
    image_gen_api_key: str
    image_gen_api_key_set: bool
    image_gen_api_base: str
    image_gen_model: str
    # 数据库
    db_type: str
    db_host: str
    db_port: int
    db_name: str


class SettingsUpdate(BaseModel):
    """可更新字段"""
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_api_base: str | None = None
    ai_model: str | None = None
    image_gen_provider: str | None = None
    image_gen_api_key: str | None = None
    image_gen_api_base: str | None = None
    image_gen_model: str | None = None
    db_type: str | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None


def _get_active_api_key() -> str:
    """获取当前 Provider 的 API Key（已脱敏）"""
    provider = settings.AI_PROVIDER
    if provider == "deepseek":
        return _mask_key(settings.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", ""))
    elif provider == "qwen":
        return _mask_key(settings.QWEN_API_KEY or os.getenv("QWEN_API_KEY", ""))
    elif provider == "openai":
        return _mask_key(settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""))
    return ""


def _get_active_api_key_set() -> bool:
    """当前 Provider 的 API Key 是否已配置"""
    provider = settings.AI_PROVIDER
    if provider == "deepseek":
        return bool(settings.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", ""))
    elif provider == "qwen":
        return bool(settings.QWEN_API_KEY or os.getenv("QWEN_API_KEY", ""))
    elif provider == "openai":
        return bool(settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""))
    return False


def _get_active_api_base() -> str:
    provider = settings.AI_PROVIDER
    if provider == "deepseek":
        return settings.DEEPSEEK_API_BASE
    elif provider == "qwen":
        return settings.QWEN_API_BASE
    elif provider == "openai":
        return settings.OPENAI_API_BASE
    return ""


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """读取当前配置（API Key 脱敏）"""
    return SettingsResponse(
        ai_provider=settings.AI_PROVIDER,
        ai_api_key=_get_active_api_key(),
        ai_api_key_set=_get_active_api_key_set(),
        ai_api_base=_get_active_api_base(),
        ai_model=settings.AI_MODEL,
        ai_temperature=settings.AI_TEMPERATURE,
        ai_max_tokens=settings.AI_MAX_TOKENS,
        image_gen_provider=settings.IMAGE_GEN_PROVIDER,
        image_gen_api_key=_mask_key(settings.IMAGE_GEN_API_KEY or ""),
        image_gen_api_key_set=bool(settings.IMAGE_GEN_API_KEY),
        image_gen_api_base=settings.IMAGE_GEN_API_BASE,
        image_gen_model=settings.IMAGE_GEN_MODEL,
        db_type=settings.DB_TYPE,
        db_host=settings.DB_HOST,
        db_port=settings.DB_PORT,
        db_name=settings.DB_NAME,
    )


@router.put("")
async def update_settings(data: SettingsUpdate):
    """更新 .env 配置（需要重启后端生效）"""
    if not ENV_PATH.exists():
        raise HTTPException(status_code=500, detail=".env 文件不存在")

    content = ENV_PATH.read_text(encoding="utf-8")
    updated_fields: list[str] = []

    def _replace(key: str, value: str):
        nonlocal content
        pattern = rf'^{key}\s*=\s*.*$'
        replacement = f"{key}={value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content += f"\n{replacement}\n"

    # AI 模型
    if data.ai_provider is not None:
        _replace("AI_PROVIDER", data.ai_provider)
        updated_fields.append("AI_PROVIDER")
    if data.ai_api_key is not None and data.ai_api_key.strip():
        provider_val = data.ai_provider or settings.AI_PROVIDER
        key_map = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "QWEN_API_KEY", "openai": "OPENAI_API_KEY"}
        key_name = key_map.get(provider_val, "DEEPSEEK_API_KEY")
        _replace(key_name, data.ai_api_key.strip())
        updated_fields.append(key_name)
    if data.ai_api_base is not None:
        provider_val = data.ai_provider or settings.AI_PROVIDER
        base_map = {"deepseek": "DEEPSEEK_API_BASE", "qwen": "QWEN_API_BASE", "openai": "OPENAI_API_BASE"}
        base_name = base_map.get(provider_val, "DEEPSEEK_API_BASE")
        _replace(base_name, data.ai_api_base)
        updated_fields.append(base_name)
    if data.ai_model is not None:
        _replace("AI_MODEL", data.ai_model)
        updated_fields.append("AI_MODEL")

    # 图片生成
    if data.image_gen_provider is not None:
        _replace("IMAGE_GEN_PROVIDER", data.image_gen_provider)
        updated_fields.append("IMAGE_GEN_PROVIDER")
    if data.image_gen_api_key is not None and data.image_gen_api_key.strip():
        _replace("IMAGE_GEN_API_KEY", data.image_gen_api_key.strip())
        updated_fields.append("IMAGE_GEN_API_KEY")
    if data.image_gen_api_base is not None:
        _replace("IMAGE_GEN_API_BASE", data.image_gen_api_base)
        updated_fields.append("IMAGE_GEN_API_BASE")
    if data.image_gen_model is not None:
        _replace("IMAGE_GEN_MODEL", data.image_gen_model)
        updated_fields.append("IMAGE_GEN_MODEL")

    # 数据库
    if data.db_type is not None:
        _replace("DB_TYPE", data.db_type)
        updated_fields.append("DB_TYPE")
    if data.db_host is not None:
        _replace("DB_HOST", data.db_host)
        updated_fields.append("DB_HOST")
    if data.db_port is not None:
        _replace("DB_PORT", str(data.db_port))
        updated_fields.append("DB_PORT")
    if data.db_name is not None:
        _replace("DB_NAME", data.db_name)
        updated_fields.append("DB_NAME")

    ENV_PATH.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "message": f"已更新 {len(updated_fields)} 项配置 ({', '.join(updated_fields)})，请重启后端服务生效。",
        "updated_fields": updated_fields,
    }
