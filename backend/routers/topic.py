"""选题策划 API"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import Product
from backend.schemas.schemas import APIResponse
from backend.services.topic_planner import topic_planner
from backend.topic_config import TOPIC_MAP, FISHERY_TOPICS
from sqlalchemy import select

router = APIRouter()


@router.get("/categories", response_model=APIResponse)
async def list_categories():
    """获取全部选题类别"""
    return APIResponse(
        success=True,
        message="选题类别列表",
        data=[t.to_dict() for t in FISHERY_TOPICS],
    )


@router.get("/platforms/{platform}", response_model=APIResponse)
async def platform_topics(platform: str):
    """获取某平台推荐的选题列表"""
    return APIResponse(
        success=True,
        message=f"{platform} 平台选题推荐",
        data={
            "platform": platform,
            "topics": topic_planner.get_platform_topics(platform),
        },
    )


@router.post("/suggest", response_model=APIResponse)
async def suggest_topic(
    product_id: int = Query(..., description="产品ID"),
    platform: str = Query(..., description="目标平台"),
    force_topic: Optional[str] = Query(None, description="强制选用（跳过调度器）"),
    db: AsyncSession = Depends(get_db),
):
    """为产品+平台推荐下一个选题方向"""
    if force_topic:
        if force_topic not in TOPIC_MAP:
            raise HTTPException(status_code=400, detail=f"无效选题: {force_topic}")
        return APIResponse(
            success=True,
            message=f"手动指定选题: {force_topic}",
            data={"topic_category": force_topic, "phase": "manual", "topic_name": TOPIC_MAP[force_topic].name},
        )

    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    rotation = product.topic_rotation or {}
    topic_id, phase, debug = await topic_planner.suggest(
        product_id, platform, db, rotation,
    )

    # 回写 rotation 到产品（JSON 列需显式 UPDATE）
    from sqlalchemy import update
    import json as _json
    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(topic_rotation=rotation)
    )
    await db.commit()

    return APIResponse(
        success=True,
        message=f"推荐选题: {TOPIC_MAP[topic_id].name} (阶段: {phase})",
        data={
            "topic_category": topic_id,
            "topic_name": TOPIC_MAP[topic_id].name,
            "topic_subtitle": TOPIC_MAP[topic_id].subtitle,
            "phase": phase,
            "prompt_injection": TOPIC_MAP[topic_id].prompt_injection,
            "debug": debug,
        },
    )


@router.get("/history/{product_id}", response_model=APIResponse)
async def topic_history(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取某产品最近的选题使用历史（用于去重展示）"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    rotation = product.topic_rotation or {}
    history = await topic_planner.get_history(product_id, db)

    # 补充 topic_name
    for h in history:
        tc = h.get("topic_category")
        h["topic_name"] = TOPIC_MAP[tc].name if tc and tc in TOPIC_MAP else "未知"

    return APIResponse(
        success=True,
        message="选题使用历史",
        data={
            "phase": rotation.get("phase", "explore"),
            "topic_stats": rotation.get("topic_stats", {}),
            "history": history,
        },
    )


@router.post("/record", response_model=APIResponse)
async def record_engagement(
    product_id: int = Query(...),
    topic_category: str = Query(...),
    views: int = Query(0),
    likes: int = Query(0),
    comments: int = Query(0),
    shares: int = Query(0),
    collects: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """记录一篇内容的互动数据，更新选题统计（由数据采集流程调用）"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    rotation = product.topic_rotation or {}
    new_rotation = topic_planner.record_engagement(
        rotation, topic_category, views, likes, comments, shares, collects,
    )
    product.topic_rotation = new_rotation
    await db.commit()

    stats = new_rotation.get("topic_stats", {}).get(topic_category, {})
    return APIResponse(
        success=True,
        message=f"选题统计已更新: {topic_category}",
        data={
            "topic_category": topic_category,
            "phase": new_rotation.get("phase"),
            "stats": stats,
        },
    )
