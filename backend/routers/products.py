"""产品管理 API"""
import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import Product, Company, KnowledgeBaseDoc
from backend.schemas.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, APIResponse
)
from sqlalchemy import select, func

router = APIRouter()


def _build_product_kwargs(data: ProductCreate | ProductUpdate) -> dict:
    """将前端字段名映射到数据库字段名，处理类型转换"""
    dump = data.model_dump(exclude_unset=True)
    kwargs = {}

    if "name" in dump:
        kwargs["name"] = dump["name"]
    if "category" in dump:
        kwargs["category"] = dump["category"]
    if "company_id" in dump:
        kwargs["company_id"] = dump["company_id"]
    if "image" in dump and dump["image"] is not None:
        kwargs["image"] = dump["image"]

    # tone → tone_config: 字符串 → dict
    if "tone" in dump and dump["tone"] is not None:
        kwargs["tone_config"] = {"style": dump["tone"]}

    # sensitive_words → forbidden_words: 逗号分隔字符串 → list
    if "sensitive_words" in dump and dump["sensitive_words"] is not None:
        words = [w.strip() for w in dump["sensitive_words"].split(",") if w.strip()]
        kwargs["forbidden_words"] = words

    return kwargs


@router.get("", response_model=List[ProductResponse])
async def list_products(
    category: str = None,
    company_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).order_by(Product.updated_at.desc())
    if category:
        query = query.where(Product.category == category)
    if company_id is not None:
        query = query.where(Product.company_id == company_id)
    result = await db.execute(query)
    products = result.scalars().all()

    # 批量获取公司名
    company_ids = {p.company_id for p in products if p.company_id}
    company_map = {}
    if company_ids:
        cresult = await db.execute(select(Company).where(Company.id.in_(company_ids)))
        for c in cresult.scalars().all():
            company_map[c.id] = c.name

    # 批量获取知识库文档数（用 text() 展开 IN 参数，避免 SQLAlchemy 缓存 IN? 语法问题）
    product_ids = [p.id for p in products]
    doc_counts = {}
    if product_ids:
        from sqlalchemy import text as sa_text
        placeholders = ",".join(f":pid{i}" for i in range(len(product_ids)))
        params = {f"pid{i}": pid for i, pid in enumerate(product_ids)}
        count_result = await db.execute(
            sa_text(
                f"SELECT product_id, COUNT(*) AS cnt FROM knowledge_base_docs "
                f"WHERE product_id IN ({placeholders}) GROUP BY product_id"
            ),
            params,
        )
        for row in count_result:
            doc_counts[row[0]] = row[1]

    # 组装响应
    resp_list = []
    for p in products:
        resp_dict = {
            "id": p.id, "name": p.name, "category": p.category,
            "company_id": p.company_id,
            "company_name": company_map.get(p.company_id),
            "image": p.image,
            "tone_config": p.tone_config,
            "forbidden_words": p.forbidden_words,
            "kb_doc_count": doc_counts.get(p.id, 0),
            "created_at": p.created_at, "updated_at": p.updated_at,
        }
        resp_list.append(ProductResponse(**resp_dict))
    return resp_list


@router.post("", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    kwargs = _build_product_kwargs(data)
    product = Product(**kwargs)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


# ========== 图片上传 ==========

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "products"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/upload-image", response_model=APIResponse)
async def upload_product_image(file: UploadFile = File(...)):
    """上传产品图片，返回图片URL"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件")

    if file.content_type and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP/GIF 格式")

    # 校验大小 5MB
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")

    # 生成唯一文件名
    ext = Path(file.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP/GIF 格式")

    filename = f"{uuid.uuid4().hex}{ext}"

    # 保存到 uploads/products/
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    url = f"/uploads/products/{filename}"
    return APIResponse(success=True, message="上传成功", data={"url": url, "filename": filename})


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    company_name = None
    if product.company_id:
        c = await db.scalar(select(Company.name).where(Company.id == product.company_id))
        company_name = c

    # 知识库文档数
    from sqlalchemy import text
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM knowledge_base_docs WHERE product_id = :pid"),
        {"pid": product_id}
    )
    kb_doc_count = count_result.scalar() or 0

    return ProductResponse(
        id=product.id, name=product.name, category=product.category,
        company_id=product.company_id, company_name=company_name,
        image=product.image,
        tone_config=product.tone_config, forbidden_words=product.forbidden_words,
        kb_doc_count=kb_doc_count,
        created_at=product.created_at, updated_at=product.updated_at,
    )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    kwargs = _build_product_kwargs(data)
    for key, value in kwargs.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", response_model=APIResponse)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    await db.delete(product)
    await db.commit()
    return APIResponse(success=True, message="产品已删除")
