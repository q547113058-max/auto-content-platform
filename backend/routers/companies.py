"""公司/品牌管理 API"""
import re, time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.models.database import get_db
from backend.models.models import Company, Product, KnowledgeBaseDoc
from backend.schemas.schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, APIResponse
)

router = APIRouter()


def _generate_slug(name: str) -> str:
    """从公司名称自动生成 slug（保留中文，替换特殊字符为连字符）"""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = f"company-{int(time.time())}"
    return slug


@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
):
    """列出所有公司/品牌"""
    result = await db.execute(select(Company).order_by(Company.updated_at.desc()))
    companies = result.scalars().all()

    response_list = []
    for c in companies:
        # 统计产品数
        pcount = await db.scalar(
            select(func.count(Product.id)).where(Product.company_id == c.id)
        )
        # 统计文档数
        dcount = await db.scalar(
            select(func.count(KnowledgeBaseDoc.id)).where(KnowledgeBaseDoc.company_id == c.id)
        )
        resp = CompanyResponse(
            id=c.id, name=c.name, slug=c.slug,
            description=c.description, industry=c.industry, logo=c.logo,
            product_count=pcount or 0, doc_count=dcount or 0,
            created_at=c.created_at, updated_at=c.updated_at,
        )
        response_list.append(resp)

    return response_list


@router.post("", response_model=CompanyResponse)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建公司/品牌"""
    # 自动生成 slug
    slug = data.slug or _generate_slug(data.name)

    # 检查 slug 唯一性
    existing = await db.scalar(select(Company).where(Company.slug == slug))
    if existing:
        # 冲突时加时间戳后缀
        slug = f"{slug}-{int(time.time()) % 10000}"

    company_data = data.model_dump()
    company_data["slug"] = slug
    company = Company(**company_data)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse(
        id=company.id, name=company.name, slug=company.slug,
        description=company.description, industry=company.industry, logo=company.logo,
        product_count=0, doc_count=0,
        created_at=company.created_at, updated_at=company.updated_at,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取公司详情"""
    company = await db.scalar(select(Company).where(Company.id == company_id))
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")

    pcount = await db.scalar(
        select(func.count(Product.id)).where(Product.company_id == company_id)
    )
    dcount = await db.scalar(
        select(func.count(KnowledgeBaseDoc.id)).where(KnowledgeBaseDoc.company_id == company_id)
    )

    return CompanyResponse(
        id=company.id, name=company.name, slug=company.slug,
        description=company.description, industry=company.industry, logo=company.logo,
        product_count=pcount or 0, doc_count=dcount or 0,
        created_at=company.created_at, updated_at=company.updated_at,
    )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新公司信息"""
    company = await db.scalar(select(Company).where(Company.id == company_id))
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")

    dump = data.model_dump(exclude_unset=True)

    # 若名称变更但未提供新 slug，自动重新生成
    if "name" in dump and "slug" not in dump:
        dump["slug"] = _generate_slug(dump["name"])

    # 检查 slug 唯一性
    if "slug" in dump and dump["slug"] != company.slug:
        existing = await db.scalar(select(Company).where(Company.slug == dump["slug"]))
        if existing:
            dump["slug"] = f"{dump['slug']}-{int(time.time()) % 10000}"

    for key, value in dump.items():
        setattr(company, key, value)

    await db.commit()
    await db.refresh(company)

    pcount = await db.scalar(select(func.count(Product.id)).where(Product.company_id == company_id))
    dcount = await db.scalar(select(func.count(KnowledgeBaseDoc.id)).where(KnowledgeBaseDoc.company_id == company_id))

    return CompanyResponse(
        id=company.id, name=company.name, slug=company.slug,
        description=company.description, industry=company.industry, logo=company.logo,
        product_count=pcount or 0, doc_count=dcount or 0,
        created_at=company.created_at, updated_at=company.updated_at,
    )


@router.delete("/{company_id}", response_model=APIResponse)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除公司（关联产品 company_id 置空，关联文档级联删除）"""
    company = await db.scalar(select(Company).where(Company.id == company_id))
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")

    await db.delete(company)
    await db.commit()
    return APIResponse(success=True, message="公司已删除")
