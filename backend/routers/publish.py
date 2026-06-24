"""发布管理 API — v2: 返回内容标题 + 字段名对齐前端"""
import sys
print(f"=== LOADING publish.py: {__file__} ===", file=sys.stderr)
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, join
from backend.models.database import get_db
from backend.models.models import PublishRecord, Content, PlatformAccount
from backend.schemas.schemas import (
    PublishRequest, PublishResponse, APIResponse,
)
from datetime import datetime
from backend.utils.timezone_utils import now_shanghai

router = APIRouter()


def _build_record_dict(record: PublishRecord, content_title: Optional[str]) -> dict:
    """将 ORM 对象转为前端期望的字段名"""
    return {
        "id": record.id,
        "content_id": record.content_id,
        "content_title": content_title or "",
        "platform": record.platform,
        "status": record.status,
        "external_id": record.external_content_id,   # 模型字段名 → 前端 prop 名
        "published_at": record.publish_time,          # 模型字段名 → 前端 prop 名
        "error_message": record.error_message,
        "publish_strategy": record.publish_strategy,
    }


@router.get("/records", response_model=List[PublishResponse])
async def list_publish_records(
    platform: str = None,
    status: str = None,
    content_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """发布记录列表（JOIN Content 获取标题）"""
    query = (
        select(PublishRecord, Content.title)
        .outerjoin(Content, PublishRecord.content_id == Content.id)
        .order_by(PublishRecord.created_at.desc())
    )
    if platform:
        query = query.where(PublishRecord.platform == platform)
    if status:
        query = query.where(PublishRecord.status == status)
    if content_id:
        query = query.where(PublishRecord.content_id == content_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        _build_record_dict(record, title)
        for record, title in rows
    ]


@router.post("", response_model=APIResponse)
async def publish_content(
    request: PublishRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """提交发布任务"""
    import sys
    print(f"=== PUBLISH_CONTENT CALLED: content_id={request.content_id}, account_id={request.account_id} ===", file=sys.stderr)
    sys.stderr.flush()
    result = await db.execute(select(Content).where(Content.id == request.content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    if content.status == "published":
        raise HTTPException(status_code=400, detail="该内容已发布，不允许重复发布")
    if content.status == "archived":
        raise HTTPException(status_code=400, detail="该内容已归档，不可发布")

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == request.account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if account.status != "active":
        raise HTTPException(status_code=400, detail="账号状态异常，请先检查会话")
    if account.platform != content.platform:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"PLATFORM MISMATCH: content.platform={content.platform}, account.platform={account.platform}")
        raise HTTPException(
            status_code=400,
            detail=f"平台不匹配：内容平台为 {content.platform}，账号平台为 {account.platform}"
        )

    record = PublishRecord(
        content_id=request.content_id,
        account_id=request.account_id,
        platform=content.platform,
        publish_strategy=request.publish_strategy or (
            "api" if content.platform == "wechat" else "playwright"
        ),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    background_tasks.add_task(_execute_publish, record_id=record.id)

    return APIResponse(success=True, message="发布任务已提交", data={"record_id": record.id})


async def _execute_publish(record_id: int):
    """后台执行发布逻辑"""
    from backend.services.publisher_base import Publisher
    from backend.models.database import AsyncSessionLocal
    from loguru import logger

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishRecord).where(PublishRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return

        result = await db.execute(
            select(Content).where(Content.id == record.content_id)
        )
        content = result.scalar_one_or_none()

        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.id == record.account_id)
        )
        account = result.scalar_one_or_none()

        record.status = "pending"
        await db.commit()

        try:
            publisher = Publisher()
            result = await publisher.publish(
                platform=record.platform,
                account_id=str(account.id),
                content={
                    "title": content.title,
                    "body": content.body,
                    "tags": content.tags or [],
                    "image_paths": content.image_paths or [],
                },
                strategy=record.publish_strategy,
            )

            if result.get("success"):
                record.status = "success"
                record.external_content_id = str(result.get("content_id", ""))
                record.publish_time = now_shanghai()
                content.status = "published"
                logger.info(f"[{record.platform}] 发布成功: {record.id}")
            else:
                record.status = "failed"
                err = result.get("error") or result.get("message") or "未知错误（平台未返回错误信息）"
                record.error_message = err
                logger.error(f"[{record.platform}] 发布失败: {err}")

        except Exception as e:
            import traceback
            record.status = "failed"
            err_msg = repr(e) if not str(e) else str(e)
            if not err_msg or err_msg in ("None", ""):
                err_msg = f"{type(e).__name__}: (无详细信息)\n{traceback.format_exc()[-500:]}"
            record.error_message = err_msg
            logger.error(f"[{record.platform}] 发布异常 ({type(e).__name__}): {e}\n{traceback.format_exc()}")

        await db.commit()


@router.get("/records/{record_id}", response_model=PublishResponse)
async def get_publish_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PublishRecord, Content.title)
        .outerjoin(Content, PublishRecord.content_id == Content.id)
        .where(PublishRecord.id == record_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="发布记录不存在")
    record, content_title = row
    return _build_record_dict(record, content_title)


@router.post("/records/{record_id}/retry", response_model=APIResponse)
async def retry_publish(
    record_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """重试失败的发布记录"""
    result = await db.execute(
        select(PublishRecord).where(PublishRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="发布记录不存在")
    if record.status not in ("failed", "pending"):
        raise HTTPException(status_code=400, detail=f"当前状态 [{record.status}] 不可重试")

    # 重置状态
    record.status = "pending"
    record.error_message = None
    await db.commit()

    background_tasks.add_task(_execute_publish, record_id=record.id)
    return APIResponse(success=True, message="已重新提交发布任务", data={"record_id": record.id})
