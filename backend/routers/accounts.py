"""平台账号管理 API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import PlatformAccount
from backend.schemas.schemas import (
    PlatformAccountCreate, PlatformAccountUpdate, PlatformAccountResponse, APIResponse,
)
from sqlalchemy import select
from pydantic import BaseModel

router = APIRouter()


class CookieImportRequest(BaseModel):
    cookie_string: str
    platform: Optional[str] = None  # 可选，默认用账号自身 platform


@router.post("/{account_id}/import-cookie", response_model=APIResponse)
async def import_cookie(
    account_id: int,
    body: CookieImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    粘贴浏览器 Cookie 字符串，自动解析为 StorageState JSON 并保存。
    保存路径：{STORAGE_STATES_DIR}/{platform}/{account_id}.json
    """
    from backend.config import settings
    from backend.services.cookie_parser import parse_cookie_string
    from pathlib import Path
    import json

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    platform = body.platform or account.platform
    try:
        storage_state = parse_cookie_string(body.cookie_string, platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 保存到 storage_states 目录
    state_dir = Path(settings.STORAGE_STATES_DIR) / platform
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{account_id}.json"
    state_path.write_text(
        json.dumps(storage_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 更新账号状态
    account.status = "active"
    account.last_check_at = __import__("datetime").datetime.now()
    await db.commit()

    cookie_count = len(storage_state.get("cookies", []))
    return APIResponse(
        success=True,
        message=f"Cookie 已导入（{cookie_count} 条），账号状态已设为 active",
        data={"cookie_count": cookie_count, "state_path": str(state_path)},
    )


@router.get("", response_model=List[PlatformAccountResponse])
async def list_accounts(
    platform: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(PlatformAccount)
    if platform:
        query = query.where(PlatformAccount.platform == platform)
    if status:
        query = query.where(PlatformAccount.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=PlatformAccountResponse)
async def create_account(
    data: PlatformAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    account = PlatformAccount(
        platform=data.platform,
        account_name=data.account_name,
        account_id=data.account_id,
        login_type=data.login_type,
        auth_config=data._parse_auth_config(data.auth_config),
        proxy_ip=data.proxy_ip,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_id}", response_model=PlatformAccountResponse)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return account


@router.put("/{account_id}", response_model=PlatformAccountResponse)
async def update_account(
    account_id: int,
    data: PlatformAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 特殊处理 auth_config：字符串 → dict
    if "auth_config" in update_data:
        update_data["auth_config"] = data._parse_auth_config(update_data["auth_config"])

    for key, value in update_data.items():
        if hasattr(account, key) and value is not None:
            setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", response_model=APIResponse)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return APIResponse(success=True, message="账号已删除")


@router.post("/{account_id}/check", response_model=APIResponse)
async def check_account_session(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """手动触发账号会话检查"""
    from loguru import logger

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    try:
        from backend.services.session_manager import session_manager

        ctx = await session_manager.get_context(
            platform=account.platform,
            account_id=str(account.id),
        )

        if ctx:
            account.status = "active"
            account.last_check_at = __import__("datetime").datetime.now()
            await db.commit()
            return APIResponse(success=True, message="会话有效", data={"status": "active"})
        else:
            account.status = "expired"
            account.last_check_at = __import__("datetime").datetime.now()
            await db.commit()
            return APIResponse(success=False, message="会话已过期，需要重新登录", data={"status": "expired"})
    except Exception as e:
        logger.error(f"会话检查异常 [{account.platform}:{account_id}]: {e}")
        account.status = "error"
        account.last_check_at = __import__("datetime").datetime.now()
        await db.commit()
        return APIResponse(success=False, message=f"会话检查失败: {str(e)}", data={"status": "error"})
