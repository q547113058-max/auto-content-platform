"""内容管理 API - 含 AI 生成"""
from typing import List, Optional
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from backend.models.database import get_db, AsyncSessionLocal
from backend.models.models import Content, Product, Company
from backend.schemas.schemas import (
    ContentCreate, ContentUpdate, ContentGenerateRequest,
    ContentResponse, ContentListResponse, ContentBatchRequest, APIResponse,
)
from sqlalchemy import select, func
from pathlib import Path
import re
from backend.utils.timezone_utils import now_shanghai


# ── 工具函数：把 image_paths 从本地路径/文件名转换成 HTTP URL ──
def _normalize_image_paths(image_paths: list) -> list:
    """
    将 image_paths 字段规范化为 HTTP URL：
    - 绝对本地路径 → 提取文件名 → /generated_images/<filename>
    - 已有 URL（http/https）→ 保留
    - 纯文件名 → /generated_images/<filename>
    """
    if not image_paths:
        return []
    normalized = []
    for p in image_paths:
        if not p:
            continue
        if p.startswith("http://") or p.startswith("https://"):
            normalized.append(p)
        else:
            # 提取文件名（兼容 Windows / Linux 路径）
            filename = p.replace("\\", "/").split("/")[-1]
            if filename:
                normalized.append(f"/generated_images/{filename}")
    return normalized

router = APIRouter()


@router.get("", response_model=ContentListResponse)
async def list_contents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    topic_category: Optional[str] = None,
    status: Optional[str] = None,
    product_id: Optional[int] = None,
    company_id: Optional[int] = None,
    content_mode: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    # 主查询 JOIN Product、Company 获取名称
    query = (
        select(
            Content,
            Product.name.label("product_name"),
            Company.name.label("company_name"),
        )
        .join(Product, Content.product_id == Product.id, isouter=True)
        .join(Company, Content.company_id == Company.id, isouter=True)
    )

    # 筛选条件
    if platform:
        query = query.where(Content.platform == platform)
    if topic_category:
        query = query.where(Content.topic_category == topic_category)
    if status:
        query = query.where(Content.status == status)
    if product_id:
        query = query.where(Content.product_id == product_id)
    if company_id:
        query = query.where(Content.company_id == company_id)
    if content_mode:
        query = query.where(Content.content_mode == content_mode)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            Content.title.ilike(kw) | Content.body.ilike(kw)
        )

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 排序 + 分页
    query = query.order_by(Content.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    # 组装响应
    items = []
    for content, pname, cname in rows:
        item = ContentResponse(
            id=content.id,
            product_id=content.product_id,
            product_name=pname,
            company_id=content.company_id,
            company_name=cname,
            content_mode=content.content_mode or "product",
            platform=content.platform,
            title=content.title,
            body=content.body,
            tags=content.tags,
            image_paths=_normalize_image_paths(content.image_paths),
            prompt_version=content.prompt_version,
            topic_category=content.topic_category,
            status=content.status,
            created_at=content.created_at,
        )
        items.append(item)

    return ContentListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=ContentResponse)
async def create_content(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
):
    content = Content(**data.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.post("/generate", response_model=APIResponse)
async def generate_content(
    request: ContentGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    AI 内容生成 — 异步模式
    立即返回临时 content_ids，后台继续生成，生成完成后替换内容。
    auto_publish：生成完成后自动发布（需先配置平台账号）
    """
    mode = request.content_mode or "product"

    # ── 参数校验（同步，快速失败）──
    if mode == "product":
        if not request.product_id:
            raise HTTPException(status_code=400, detail="纯产品模式必须传 product_id")
        res = await db.execute(select(Product).where(Product.id == request.product_id))
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="产品不存在")

    elif mode in ("company", "mixed"):
        if not request.company_id:
            raise HTTPException(status_code=400, detail=f"{mode} 模式必须传 company_id")
        res = await db.execute(select(Company).where(Company.id == request.company_id))
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="公司不存在")

    from backend.services.ai_generator import ai_generator
    if not ai_generator.is_configured:
        raise HTTPException(
            status_code=400,
            detail="AI 内容生成未配置：缺少 API Key。请在 .env 文件中设置 "
                   f"DEEPSEEK_API_KEY（当前 Provider: {ai_generator._provider_name()}），"
                   "然后重启后端服务。"
        )

    platforms = request.platforms or [
        "xiaohongshu", "zhihu", "weibo", "wechat", "toutiao", "douyin"
    ]

    # ── 预建临时 Content 记录（status=generating）──
    now = now_shanghai()
    temp_contents = []
    for platform in platforms:
        temp = Content(
            product_id=request.product_id,
            company_id=request.company_id or None,
            content_mode=mode,
            platform=platform,
            title="生成中…",
            body="",
            tags=[],
            image_paths=[],
            topic_category=request.topic_category or None,
            status="generating",
            created_at=now,
        )
        db.add(temp)
        temp_contents.append((temp, platform))
    await db.commit()

    # 刷新获取 ID
    content_ids = []
    platform_for_id = {}
    for temp, platform in temp_contents:
        await db.refresh(temp)
        content_ids.append(temp.id)
        platform_for_id[temp.id] = platform

    logger.info(f"[generate] 已创建临时记录 {content_ids}，后台开始生成…")

    # ── 启动后台任务（立即返回）──
    asyncio.create_task(
        _run_generation_task(
            content_ids=content_ids,
            product_id=request.product_id,
            company_id=request.company_id,
            content_mode=mode,
            platforms=platforms,
            override_prompt=request.override_prompt,
            topic_category=request.topic_category,
            auto_publish=request.auto_publish,
        )
    )

    return APIResponse(
        success=True,
        message=f"已提交生成任务，{len(content_ids)} 篇内容生成中…",
        data={
            "content_ids": content_ids,
            "platforms": platforms,
            "auto_publish": request.auto_publish,
        },
    )


# ── 后台任务：真正执行 AI 生成 ──
async def _run_generation_task(
    content_ids: list,
    product_id: int = None,
    company_id: int = None,
    content_mode: str = "product",
    platforms: list = None,
    override_prompt: str = None,
    topic_category: str = None,
    auto_publish: bool = False,
):
    """后台异步执行 AI 生成，完成后更新 Content 记录"""
    from backend.tasks.content_tasks import generate_content_task

    try:
        result = await generate_content_task(
            content_ids=content_ids,
            product_id=product_id,
            company_id=company_id,
            content_mode=content_mode,
            platforms=platforms,
            override_prompt=override_prompt,
            topic_category=topic_category,
            auto_publish=auto_publish,
        )
        logger.info(f"[_run_generation_task] 完成：{result}")

    except Exception as e:
        import traceback
        logger.error(f"[_run_generation_task] 失败: {e}\n{traceback.format_exc()}")
        # 把失败的记录状态改为 draft，标题标记失败
        try:
            from backend.models.database import AsyncSessionLocal
            from sqlalchemy import update
            from backend.models.models import Content
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Content)
                    .where(Content.id.in_(content_ids))
                    .values(status="draft", title=f"生成失败：{str(e)[:100]}")
                )
                await db.commit()
        except Exception:
            pass


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    return ContentResponse(
        id=content.id,
        product_id=content.product_id,
        product_name=None,
        company_id=content.company_id,
        company_name=None,
        content_mode=content.content_mode or "product",
        platform=content.platform,
        title=content.title,
        body=content.body,
        tags=content.tags,
        image_paths=_normalize_image_paths(content.image_paths),
        prompt_version=content.prompt_version,
        topic_category=content.topic_category,
        status=content.status,
        created_at=content.created_at,
    )


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: int,
    data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        if hasattr(content, key):
            setattr(content, key, value)
    await db.commit()
    await db.refresh(content)
    return content


@router.put("/{content_id}/status", response_model=ContentResponse)
async def update_content_status(
    content_id: int,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")

    content.status = status
    await db.commit()
    await db.refresh(content)
    return content


@router.delete("/{content_id}", response_model=APIResponse)
async def delete_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    await db.delete(content)
    await db.commit()
    return APIResponse(success=True, message="内容已删除")


# ==================== 批量操作 ====================

@router.post("/batch-delete", response_model=APIResponse)
async def batch_delete_contents(
    data: ContentBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    if not data.ids:
        raise HTTPException(status_code=400, detail="请选择至少一条内容")
    result = await db.execute(
        select(Content).where(Content.id.in_(data.ids))
    )
    rows = result.scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return APIResponse(success=True, message=f"已删除 {len(rows)} 条内容")


@router.post("/batch-status", response_model=APIResponse)
async def batch_update_status(
    data: ContentBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    if not data.ids or not data.status:
        raise HTTPException(status_code=400, detail="请选择内容并指定状态")
    result = await db.execute(
        select(Content).where(Content.id.in_(data.ids))
    )
    rows = result.scalars().all()
    for row in rows:
        row.status = data.status
    await db.commit()
    return APIResponse(success=True, message=f"已更新 {len(rows)} 条状态为 {data.status}")
