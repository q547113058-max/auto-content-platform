"""优化学习 API - 改动记录 + 去重 + 自动闭环"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import OptimizationChange, Content, ContentMetric, PublishRecord
from backend.schemas.schemas import (
    OptimizationChangeCreate, OptimizationChangeResponse, APIResponse,
)
from sqlalchemy import select

router = APIRouter()


@router.get("/changes", response_model=List[OptimizationChangeResponse])
async def list_changes(
    product_id: int = None,
    platform: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(OptimizationChange).order_by(OptimizationChange.created_at.desc())
    if product_id:
        query = query.where(OptimizationChange.product_id == product_id)
    if platform:
        query = query.where(OptimizationChange.platform == platform)
    if status:
        query = query.where(OptimizationChange.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/changes", response_model=OptimizationChangeResponse)
async def create_change(
    data: OptimizationChangeCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建改动记录（自动做语义去重检查）"""
    from backend.services.optimizer import optimizer

    change = OptimizationChange(**data.model_dump())

    # AI 语义去重检查
    is_dup, similar_id = await optimizer.check_duplicate(change, db)
    if is_dup:
        change.is_duplicate = True
        change.similar_to_change_id = similar_id

    db.add(change)
    await db.commit()
    await db.refresh(change)
    return change


@router.put("/changes/{change_id}/status", response_model=OptimizationChangeResponse)
async def update_change_status(
    change_id: int,
    status: str,
    approved_by: str = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OptimizationChange).where(OptimizationChange.id == change_id)
    )
    change = result.scalar_one_or_none()
    if not change:
        raise HTTPException(status_code=404, detail="改动记录不存在")

    change.status = status
    if approved_by:
        change.approved_by = approved_by
    await db.commit()
    await db.refresh(change)
    return change


@router.post("/analyze/{product_id}", response_model=APIResponse)
async def analyze_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """对产品进行全平台数据分析并生成优化建议"""
    from backend.services.optimizer import optimizer

    suggestions = await optimizer.analyze_and_optimize(product_id, db)
    return APIResponse(
        success=True,
        message=f"分析完成，生成 {len(suggestions)} 条优化建议",
        data={"suggestions": suggestions},
    )


@router.get("/changes/{change_id}/verify", response_model=APIResponse)
async def verify_change_effect(
    change_id: int,
    db: AsyncSession = Depends(get_db),
):
    """验证改动效果（对比改动前后的数据）"""
    result = await db.execute(
        select(OptimizationChange).where(OptimizationChange.id == change_id)
    )
    change = result.scalar_one_or_none()
    if not change:
        raise HTTPException(status_code=404, detail="改动记录不存在")

    if not change.next_publish_id:
        return APIResponse(success=False, message="该改动尚无关联的新发布内容")

    # 获取改动前后的数据
    effect = await _compare_before_after(change, db)
    change.effect_verified = True
    change.effect_result = str(effect)
    await db.commit()

    return APIResponse(success=True, message="效果验证完成", data=effect)


@router.post("/auto-loop", response_model=APIResponse)
async def trigger_auto_loop(
    db: AsyncSession = Depends(get_db),
):
    """手动触发一次完整的自动优化闭环
    流程：抓取最新数据 → 筛选活跃产品 → 分析效果 → 生成优化建议
    """
    from backend.services.scheduler import job_auto_optimize_loop
    result = await job_auto_optimize_loop()
    return APIResponse(
        success=result.get("status") != "error",
        message=f"闭环完成: {result.get('new_suggestions', 0)} 新建议",
        data=result,
    )


@router.post("/analyze-all", response_model=APIResponse)
async def analyze_all_products(
    db: AsyncSession = Depends(get_db),
):
    """对全部产品执行优化分析"""
    from backend.services.scheduler import job_analyze_all
    await job_analyze_all()
    return APIResponse(success=True, message="全产品分析已触发")


@router.get("/stats")
async def get_optimization_stats(
    product_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """优化学习统计 — 展示改动效果概览"""
    from sqlalchemy import func, case

    base_query = select(
        OptimizationChange.status,
        func.count(OptimizationChange.id).label("count"),
    )

    if product_id:
        base_query = base_query.where(OptimizationChange.product_id == product_id)

    base_query = base_query.group_by(OptimizationChange.status)
    result = await db.execute(base_query)
    rows = result.all()

    status_counts = {row.status: row.count for row in rows}

    # 已验证有效的改动数
    verified_query = select(func.count(OptimizationChange.id)).where(
        OptimizationChange.effect_verified == True
    )
    if product_id:
        verified_query = verified_query.where(OptimizationChange.product_id == product_id)
    verified_count = await db.scalar(verified_query)

    # 去重数
    dup_query = select(func.count(OptimizationChange.id)).where(
        OptimizationChange.is_duplicate == True
    )
    if product_id:
        dup_query = dup_query.where(OptimizationChange.product_id == product_id)
    dup_count = await db.scalar(dup_query)

    return {
        "total": sum(status_counts.values()),
        "by_status": status_counts,
        "verified": verified_count or 0,
        "duplicates": dup_count or 0,
        "unique_changes": sum(status_counts.values()) - (dup_count or 0),
    }


@router.get("/suggestions/{product_id}")
async def get_product_suggestions(
    product_id: int,
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """获取某产品的优化建议历史"""
    query = (
        select(OptimizationChange)
        .where(OptimizationChange.product_id == product_id)
        .order_by(OptimizationChange.created_at.desc())
    )
    if status:
        query = query.where(OptimizationChange.status == status)
    result = await db.execute(query)
    changes = result.scalars().all()

    return [
        {
            "id": c.id,
            "change_type": c.change_type,
            "platform": c.platform,
            "issue": c.issue_description,
            "hypothesis": c.hypothesis,
            "action": c.action_taken,
            "status": c.status,
            "is_duplicate": c.is_duplicate,
            "effect_verified": c.effect_verified,
            "created_at": str(c.created_at) if c.created_at else None,
        }
        for c in changes
    ]


async def _compare_before_after(change: OptimizationChange, db: AsyncSession):
    """对比改动前后的指标变化"""
    # 改动前的数据：related_content_ids 对应的指标
    before_metrics = []
    if change.related_content_ids:
        for cid in change.related_content_ids:
            result = await db.execute(
                select(ContentMetric)
                .join(PublishRecord)
                .where(PublishRecord.content_id == cid)
                .order_by(ContentMetric.scraped_at.desc())
                .limit(1)
            )
            metric = result.scalar_one_or_none()
            if metric:
                before_metrics.append(metric)

    # 改动后的数据
    after_metrics = []
    if change.next_publish_id:
        result = await db.execute(
            select(ContentMetric)
            .where(ContentMetric.publish_record_id == change.next_publish_id)
            .order_by(ContentMetric.scraped_at.desc())
            .limit(1)
        )
        metric = result.scalar_one_or_none()
        if metric:
            after_metrics.append(metric)

    def avg(lst, attr):
        vals = [getattr(m, attr, 0) for m in lst if m]
        return sum(vals) / len(vals) if vals else 0

    return {
        "before_avg_views": avg(before_metrics, "views"),
        "after_avg_views": avg(after_metrics, "views"),
        "before_avg_likes": avg(before_metrics, "likes"),
        "after_avg_likes": avg(after_metrics, "likes"),
        "before_avg_engagement": (
            avg(before_metrics, "likes") + avg(before_metrics, "comments")
        ) / max(avg(before_metrics, "views"), 1) * 100,
        "after_avg_engagement": (
            avg(after_metrics, "likes") + avg(after_metrics, "comments")
        ) / max(avg(after_metrics, "views"), 1) * 100,
        "samples_before": len(before_metrics),
        "samples_after": len(after_metrics),
    }
