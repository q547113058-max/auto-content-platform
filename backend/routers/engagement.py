"""
互动管理 API — 评论自动回复
"""
from typing import Optional
from fastapi import APIRouter, Query, BackgroundTasks
from backend.services.engagement import engagement_engine, ENGAGEMENT_CONFIGS
from backend.schemas.schemas import APIResponse

router = APIRouter()


@router.get("/platforms")
async def list_platforms():
    """列出支持的互动平台"""
    return APIResponse(
        success=True,
        message="ok",
        data={
            p: {
                "name": c["name"],
                "reply_method": "playwright",
                "features": ["评论抓取", "AI 生成回复", "自动回复", "去重"],
            }
            for p, c in ENGAGEMENT_CONFIGS.items()
        },
    )


@router.get("/stats")
async def get_stats(platform: Optional[str] = Query(None)):
    """获取互动统计"""
    stats = await engagement_engine.get_stats(platform)
    return APIResponse(success=True, message="ok", data=stats)


@router.get("/history")
async def get_history(
    platform: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取回复历史"""
    data = await engagement_engine.get_reply_history(
        platform, account_id, status, limit, offset
    )
    return APIResponse(success=True, message="ok", data=data, meta={"total": len(data), "limit": limit, "offset": offset})


@router.post("/run")
async def trigger_engagement(
    platform: str = Query(..., description="平台: zhihu/toutiao"),
    account_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    limit_per_content: int = Query(10, ge=1, le=50),
    max_contents: int = Query(5, ge=1, le=20),
    background_tasks: BackgroundTasks = None,
):
    """手动触发评论互动"""
    result = await engagement_engine.engage_platform(
        platform=platform,
        account_id=account_id,
        product_id=product_id,
        limit_per_content=limit_per_content,
        max_contents=max_contents,
    )

    if "error" in result:
        return APIResponse(success=False, message=result["error"])

    return APIResponse(
        success=True,
        message=f"已回复 {result['total_replied']} 条，失败 {result['total_failed']} 条",
        data={
            "platform": result["platform"],
            "platform_name": result["platform_name"],
            "total_replied": result["total_replied"],
            "total_failed": result["total_failed"],
            "total_skipped": result["total_skipped"],
            "total_found": result["total_found"],
            "contents_processed": result["contents_processed"],
            "details": result["results"],
        },
    )


@router.post("/run-all")
async def trigger_all_platforms(
    limit_per_content: int = Query(10),
    max_contents: int = Query(5),
):
    """对所有支持平台执行互动"""
    platforms = list(ENGAGEMENT_CONFIGS.keys())
    all_results = {}

    for platform in platforms:
        result = await engagement_engine.engage_platform(
            platform=platform,
            limit_per_content=limit_per_content,
            max_contents=max_contents,
        )
        all_results[platform] = result

    total_replied = sum(
        r.get("total_replied", 0) for r in all_results.values() if "total_replied" in r
    )
    return APIResponse(
        success=True,
        message=f"全平台互动完成，共回复 {total_replied} 条",
        data={
            "total_replied": total_replied,
            "by_platform": all_results,
        },
    )
