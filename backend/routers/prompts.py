"""提示词版本管理 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import PromptVersion
from backend.schemas.schemas import (
    PromptVersionCreate, PromptVersionResponse, APIResponse,
)
from sqlalchemy import select, update, delete

router = APIRouter()


@router.get("", response_model=List[PromptVersionResponse])
async def list_prompt_versions(
    platform: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(PromptVersion).order_by(PromptVersion.created_at.desc())
    if platform:
        query = query.where(PromptVersion.platform == platform)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/active/{platform}", response_model=PromptVersionResponse)
async def get_active_prompt(
    platform: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.platform == platform, PromptVersion.is_active == True)
        .order_by(PromptVersion.created_at.desc())
        .limit(1)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"平台 {platform} 无活跃提示词")
    return prompt


@router.post("", response_model=PromptVersionResponse)
async def create_prompt_version(
    data: PromptVersionCreate,
    db: AsyncSession = Depends(get_db),
):
    prompt = PromptVersion(**data.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.post("/{prompt_id}/activate", response_model=APIResponse)
async def activate_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
):
    """激活某个版���的提示词（同平台停用其他版本）"""
    result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词版本不存在")

    # 停用同平台其他版本
    await db.execute(
        update(PromptVersion)
        .where(PromptVersion.platform == prompt.platform, PromptVersion.id != prompt_id)
        .values(is_active=False)
    )

    # 激活当前版本
    prompt.is_active = True
    await db.commit()

    return APIResponse(success=True, message=f"已激活 {prompt.platform} v{prompt.version} 提示词")


@router.put("/{prompt_id}", response_model=PromptVersionResponse)
async def update_prompt(
    prompt_id: int,
    data: PromptVersionCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词版本不存在")
    for key, value in data.model_dump().items():
        if hasattr(prompt, key):
            setattr(prompt, key, value)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}", response_model=APIResponse)
async def delete_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == prompt_id)
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词版本不存在")
    await db.delete(prompt)
    await db.commit()
    return APIResponse(success=True, message="提示词已删除")
