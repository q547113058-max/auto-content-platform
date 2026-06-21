"""内容管理 API - 含 AI 生成"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import Content, Product, Company
from backend.schemas.schemas import (
    ContentCreate, ContentUpdate, ContentGenerateRequest,
    ContentResponse, ContentListResponse, ContentBatchRequest, APIResponse,
)
from sqlalchemy import select, func

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
            image_paths=content.image_paths,
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
    AI 内容生成 — 三模式统一入口

    content_mode:
      - product : 纯产品文案（须传 product_id）
      - company : 纯公司品牌内容（须传 company_id）
      - mixed   : 公司为主 + 产品辅助（须传 company_id，product_id 可选）
    """
    mode = request.content_mode or "product"

    # 参数校验
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

    from backend.tasks.content_tasks import generate_content_task

    platforms = request.platforms or [
        "xiaohongshu", "zhihu", "weibo", "wechat", "toutiao", "douyin"
    ]

    task_result = await generate_content_task(
        product_id=request.product_id,
        company_id=request.company_id,
        content_mode=mode,
        platforms=platforms,
        override_prompt=request.override_prompt,
        topic_category=request.topic_category,
    )

    if task_result.get("error"):
        return APIResponse(success=False, message=task_result["error"], data=task_result)

    generated_ids = task_result.get("generated_ids", [])
    errors = task_result.get("errors", [])
    mode_label = {"product": "纯产品", "company": "纯公司", "mixed": "混合"}.get(mode, mode)

    return APIResponse(
        success=len(generated_ids) > 0,
        message=f"[{mode_label}模式] 完成：{len(generated_ids)} 篇内容已生成" + (f"，{len(errors)} 个平台失败" if errors else ""),
        data={"generated_ids": generated_ids, "platforms": task_result.get("platforms", []), "errors": errors, "content_mode": mode},
    )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    return content


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
