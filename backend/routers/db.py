"""通用数据库浏览 API（仅开发用）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.models.database import get_db
from backend.schemas.schemas import APIResponse

router = APIRouter()

ALLOWED_TABLES = {
    "products", "platform_accounts", "contents", "publish_records",
    "content_metrics", "optimization_changes", "prompt_versions",
    "scheduled_tasks", "comment_replies",
}


@router.get("/tables")
async def list_tables():
    return APIResponse(success=True, message="ok", data=list(sorted(ALLOWED_TABLES)))


@router.get("/tables/{table_name}")
async def browse_table(
    table_name: str,
    page_size: int = 100,
    db: AsyncSession = Depends(get_db),
):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"不允许访问表: {table_name}")

    try:
        result = await db.execute(
            text(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT :limit")
            .bindparams(limit=min(page_size, 500))
        )
        rows = [dict(row._mapping) for row in result]
        return APIResponse(success=True, message="ok", data=rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
