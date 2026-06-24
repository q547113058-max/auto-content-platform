"""数据分析 API — 支持可视化图表数据"""
from typing import List, Optional
from datetime import datetime, timedelta
from backend.utils.timezone_utils import now_shanghai
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_
from backend.models.database import get_db
from backend.models.models import ContentMetric, PublishRecord, Content, Product
from backend.schemas.schemas import ContentMetricResponse, MetricSummary, APIResponse
from loguru import logger

router = APIRouter()


@router.get("/content/{publish_record_id}", response_model=List[ContentMetricResponse])
async def get_content_metrics(
    publish_record_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单篇内容的时序数据"""
    query = (
        select(ContentMetric)
        .where(ContentMetric.publish_record_id == publish_record_id)
        .order_by(ContentMetric.scraped_at.desc())
        .limit(30)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary/{product_id}", response_model=List[MetricSummary])
async def get_metrics_summary(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取某产品在各平台的最新数据摘要"""
    query = text("""
        SELECT
            pr.platform,
            cm.views,
            cm.likes,
            cm.comments,
            cm.shares,
            cm.collects,
            pr.id as record_id
        FROM content_metrics cm
        JOIN publish_records pr ON cm.publish_record_id = pr.id
        JOIN contents c ON pr.content_id = c.id
        WHERE c.product_id = :product_id
        AND cm.id IN (
            SELECT MAX(id) FROM content_metrics
            GROUP BY publish_record_id
        )
    """)
    result = await db.execute(query, {"product_id": product_id})
    rows = result.all()

    platform_data = defaultdict(lambda: {
        "total_views": 0, "total_likes": 0, "total_comments": 0,
        "total_shares": 0, "total_collects": 0, "content_count": 0,
    })

    for row in rows:
        p = platform_data[row.platform]
        p["total_views"] += row.views or 0
        p["total_likes"] += row.likes or 0
        p["total_comments"] += row.comments or 0
        p["total_shares"] += row.shares or 0
        p["total_collects"] += row.collects or 0
        p["content_count"] += 1

    summaries = []
    for platform, data in platform_data.items():
        total_interactions = data["total_likes"] + data["total_comments"] + data["total_shares"] + data["total_collects"]
        engagement_rate = (total_interactions / data["total_views"] * 100) if data["total_views"] > 0 else 0
        summaries.append(MetricSummary(
            platform=platform,
            total_views=data["total_views"],
            total_likes=data["total_likes"],
            total_comments=data["total_comments"],
            total_shares=data["total_shares"],
            total_collects=data["total_collects"],
            avg_engagement_rate=round(engagement_rate, 2),
            content_count=data["content_count"],
        ))

    return summaries


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
):
    """获取全局数据概览 — Dashboard 使用"""
    # 产品总数
    product_count = await db.scalar(select(func.count(Product.id)))
    # 内容总数
    content_count = await db.scalar(select(func.count(Content.id)))
    # 已发布内容数
    published_count = await db.scalar(
        select(func.count(PublishRecord.id)).where(PublishRecord.status == "success")
    )

    # 总数据指标
    latest_metrics_query = text("""
        SELECT COALESCE(SUM(cm.views), 0) as total_views,
               COALESCE(SUM(cm.likes), 0) as total_likes,
               COALESCE(SUM(cm.comments), 0) as total_comments,
               COALESCE(SUM(cm.shares), 0) as total_shares,
               COALESCE(SUM(cm.collects), 0) as total_collects
        FROM content_metrics cm
        WHERE cm.id IN (SELECT MAX(id) FROM content_metrics GROUP BY publish_record_id)
    """)
    result = await db.execute(latest_metrics_query)
    row = result.first()

    return {
        "product_count": product_count or 0,
        "content_count": content_count or 0,
        "published_count": published_count or 0,
        "total_views": row.total_views or 0,
        "total_likes": row.total_likes or 0,
        "total_comments": row.total_comments or 0,
        "total_shares": row.total_shares or 0,
        "total_collects": row.total_collects or 0,
    }


@router.get("/trends/{product_id}")
async def get_trends(
    product_id: int,
    days: int = Query(default=30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    """获取某产品的数据趋势 — 折线图使用"""
    cutoff = now_shanghai() - timedelta(days=days)

    query = text("""
        SELECT
            DATE(cm.scraped_at) as date,
            pr.platform,
            SUM(cm.views) as views,
            SUM(cm.likes) as likes,
            SUM(cm.comments) as comments,
            SUM(cm.shares) as shares
        FROM content_metrics cm
        JOIN publish_records pr ON cm.publish_record_id = pr.id
        JOIN contents c ON pr.content_id = c.id
        WHERE c.product_id = :product_id
          AND cm.scraped_at >= :cutoff
        GROUP BY DATE(cm.scraped_at), pr.platform
        ORDER BY date ASC
    """)
    result = await db.execute(query, {"product_id": product_id, "cutoff": cutoff})
    rows = result.all()

    # 组织为前端友好的格式
    dates = []
    date_set = set()
    platform_series = defaultdict(list)

    for row in rows:
        date_str = str(row.date)
        if date_str not in date_set:
            dates.append(date_str)
            date_set.add(date_str)
        platform_series[row.platform].append({
            "date": str(row.date),
            "views": row.views or 0,
            "likes": row.likes or 0,
            "comments": row.comments or 0,
            "shares": row.shares or 0,
        })

    return {
        "dates": dates,
        "series": {k: v for k, v in platform_series.items()},
    }


@router.get("/platform-distribution")
async def get_platform_distribution(
    db: AsyncSession = Depends(get_db),
):
    """获取平台内容分布 — 饼图使用"""
    query = text("""
        SELECT pr.platform,
               COUNT(DISTINCT c.id) as content_count,
               COALESCE(SUM(latest.views), 0) as total_views,
               COALESCE(SUM(latest.likes), 0) as total_likes
        FROM publish_records pr
        JOIN contents c ON pr.content_id = c.id
        LEFT JOIN (
            SELECT publish_record_id, views, likes
            FROM content_metrics
            WHERE id IN (SELECT MAX(id) FROM content_metrics GROUP BY publish_record_id)
        ) latest ON latest.publish_record_id = pr.id
        WHERE pr.status = 'success'
        GROUP BY pr.platform
    """)
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "platform": row.platform,
            "content_count": row.content_count,
            "total_views": row.total_views or 0,
            "total_likes": row.total_likes or 0,
        }
        for row in rows
    ]


@router.get("/top-contents")
async def get_top_contents(
    limit: int = Query(default=10, ge=1, le=50),
    sort_by: str = Query(default="views", regex="^(views|likes|comments|shares|engagement)$"),
    db: AsyncSession = Depends(get_db),
):
    """获取效果最好的内容排行"""
    order_map = {
        "views": "cm.views DESC",
        "likes": "cm.likes DESC",
        "comments": "cm.comments DESC",
        "shares": "cm.shares DESC",
        "engagement": "CASE WHEN cm.views > 0 THEN (cm.likes + cm.comments + cm.shares + cm.collects) * 1.0 / cm.views ELSE 0 END DESC",
    }
    order_clause = order_map.get(sort_by, "cm.views DESC")

    query = text(f"""
        SELECT c.id, c.title, c.platform, pr.publish_time,
               cm.views, cm.likes, cm.comments, cm.shares, cm.collects,
               CASE WHEN COALESCE(cm.views, 0) > 0
                    THEN ROUND((COALESCE(cm.likes,0) + COALESCE(cm.comments,0) + COALESCE(cm.shares,0) + COALESCE(cm.collects,0)) * 100.0 / cm.views, 2)
                    ELSE 0 END as engagement_rate
        FROM content_metrics cm
        JOIN publish_records pr ON cm.publish_record_id = pr.id
        JOIN contents c ON pr.content_id = c.id
        WHERE cm.id IN (SELECT MAX(id) FROM content_metrics GROUP BY publish_record_id)
        ORDER BY {order_clause}
        LIMIT :limit
    """)
    result = await db.execute(query, {"limit": limit})
    rows = result.all()

    return [
        {
            "content_id": row.id,
            "title": row.title[:100] if row.title else "",
            "platform": row.platform,
            "publish_time": str(row.publish_time) if row.publish_time else None,
            "views": row.views or 0,
            "likes": row.likes or 0,
            "comments": row.comments or 0,
            "shares": row.shares or 0,
            "collects": row.collects or 0,
            "engagement_rate": float(row.engagement_rate) if row.engagement_rate else 0,
        }
        for row in rows
    ]


@router.post("/scrape/{publish_record_id}", response_model=APIResponse)
async def trigger_scrape(
    publish_record_id: int,
    db: AsyncSession = Depends(get_db),
):
    """手动触发单篇内容数据采集"""
    result = await db.execute(
        select(PublishRecord).where(PublishRecord.id == publish_record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="发布记录不存在")

    from backend.services.scraper import scraper
    data = await scraper.scrape_single(record)

    if data:
        metric = ContentMetric(
            publish_record_id=publish_record_id,
            views=data.get("views", 0),
            likes=data.get("likes", 0),
            comments=data.get("comments", 0),
            shares=data.get("shares", 0),
            collects=data.get("collects", 0),
            followers_delta=data.get("followers_delta", 0),
            raw_data=data.get("raw_data", {}),
        )
        db.add(metric)
        await db.commit()

    return APIResponse(success=bool(data), message="数据采集完成", data=data)


@router.post("/scrape-all", response_model=APIResponse)
async def trigger_scrape_all(
    db: AsyncSession = Depends(get_db),
):
    """手动触发全量数据采集"""
    from backend.services.scraper import scraper
    result = await scraper.scrape_all_pending(db)
    return APIResponse(
        success=True,
        message=f"采集完成: {result['scraped']}/{result['total']}",
        data=result,
    )


@router.post("/scrape-product/{product_id}", response_model=APIResponse)
async def trigger_scrape_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """手动触发指定产品的数据采集"""
    from backend.services.scraper import scraper
    result = await scraper.scrape_product_all(product_id, db)
    return APIResponse(
        success=True,
        message=f"产品 {product_id} 采集完成: {result['scraped']}/{result['total']}",
        data=result,
    )
