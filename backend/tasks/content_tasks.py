"""
异步任务模块
Celery 延迟初始化 — 本地无 Redis 时直接调用 async 函数
"""
import asyncio
from loguru import logger
from backend.config import settings
from backend.models.database import AsyncSessionLocal
from backend.models.models import (
    Content, Product, OptimizationChange, KnowledgeBaseDoc
)
from sqlalchemy import select

# Celery 延迟初始化
_celery_app = None


def _get_celery():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from celery import Celery
        _celery_app = Celery(
            "auto_content_platform",
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND,
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="Asia/Shanghai",
            enable_utc=True,
        )
        return _celery_app
    except Exception as e:
        logger.warning(f"Celery 不可用: {e}")
        return None


# ==================== 主任务函数（直接调用） ====================

async def generate_content_task(product_id: int, platforms: list, override_prompt: str = None, topic_category: str = None):
    """AI 内容生成 — 一次输入，全平台适配"""
    logger.info(f"[Task] 生成内容: product_id={product_id}, platforms={platforms}, topic={topic_category}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            logger.error(f"产品 {product_id} 不存在")
            return {"error": "产品不存在"}

        # ===== 知识库合并：公司级 + 产品级 MD 文档 =====
        from backend.services.kb_parser import parse_knowledge_base

        # 收集所有知识库 raw Markdown
        kb_parts = []

        # 1) 产品级 KnowledgeBaseDoc
        prod_docs = (await db.execute(
            select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.product_id == product_id)
        )).scalars().all()
        for doc in prod_docs:
            if doc.content:
                kb_parts.append(f"## {doc.title}\n{doc.content}")

        # 3) 公司级 KnowledgeBaseDoc
        if product.company_id:
            company_docs = (await db.execute(
                select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.company_id == product.company_id)
            )).scalars().all()
            for doc in company_docs:
                if doc.content:
                    kb_parts.append(f"## [公司] {doc.title}\n{doc.content}")

        # 合并为统一的 raw Markdown
        merged_raw = "\n\n".join(kb_parts)
        kb_structured = parse_knowledge_base(merged_raw, product.category or "")
        logger.info(f"[KB] 合并知识库: "
                    f"产品文档={len(prod_docs)}, 公司文档={len(company_docs) if product.company_id else 0}, "
                    f"合并后={len(merged_raw)}字")

        # 品牌调性关键词：优先用 tone_config，fallback 品类关键词
        tone = product.tone_config.get("style", "") if product.tone_config else ""
        if not tone:
            cat = product.category or ""
            tone_map = {
                "渔业设备": "专业可靠、科技赋能养殖、降本增效",
                "农业设备": "精准种植、智慧农业、省时省力",
            }
            tone = tone_map.get(cat, "")

        product_info = {
            "name": product.name,
            "category": product.category or "",
            "price": kb_structured.get("price", ""),
            "key_ingredients": kb_structured.get("key_ingredients", ""),
            "claims": kb_structured.get("claims", ""),
            "key_points": kb_structured.get("key_points", ""),
            "target_audience": kb_structured.get("target_audience", ""),
            "industry_context": kb_structured.get("industry_context", ""),
            "tone_keywords": tone,
        }

        # 选题调度（未指定则自动推荐）
        from backend.services.topic_planner import topic_planner
        from backend.topic_config import TOPIC_MAP, PLATFORM_TOPIC_PRIORITY

        topic_per_platform = {}
        if topic_category and topic_category in TOPIC_MAP:
            # 手动指定，所有平台统一
            topic_per_platform = {p: topic_category for p in platforms}
        else:
            # 自动推荐（每个平台独立推荐）
            rotation = product.topic_rotation or {}
            for p in platforms:
                tid, phase, _debug = await topic_planner.suggest(product_id, p, db, rotation)
                topic_per_platform[p] = tid
            product.topic_rotation = rotation

        # 注入 topic 指令到 override_prompt
        from backend.services.ai_generator import ai_generator
        topic_prompt_map = {}
        topic_name_map = {}
        for p in platforms:
            tid = topic_per_platform.get(p, "tech_explanation")
            tc = TOPIC_MAP.get(tid)
            if tc:
                topic_prompt_map[p] = tc.prompt_injection
                topic_name_map[p] = tc.name
                # 平台特定指令
                if p in tc.platform_specific:
                    topic_prompt_map[p] += "\n" + tc.platform_specific[p]

        results = await ai_generator.generate_for_all_platforms(
            product_info, platforms, override_prompt, topic_prompt_map, topic_name_map
        )

        # ===== 配图生成（Seedream 5.0）+ 内联插入 =====
        from backend.services.image_generator import image_generator

        generated_ids = []
        errors = []
        for platform, data in results.items():
            if "error" in data:
                logger.warning(f"[{platform}] 生成失败: {data['error']}")
                errors.append({"platform": platform, "error": data["error"]})
                continue

            # 用内联 [IMG:...] 标记的配图描述生图
            image_markers = data.get("image_markers", [])
            # 也兼容旧格式 image_descriptions
            image_descs = data.get("image_descriptions", [])
            if not image_markers and image_descs:
                # 旧格式：位置信息缺失，统一插入到正文末尾
                image_markers = [(len(data.get("body", "").split("\n")), d) for d in image_descs]

            image_urls = []
            body = data.get("body", "")

            if image_markers and image_generator.is_configured:
                descs_for_gen = [m[1] for m in image_markers if m[1]]
                # 增强 prompt：加上产品信息，让配图更贴合上下文
                enhanced_prompts = [
                    f"{product_info['name']} — {desc}，{product_info.get('category', '')}相关，商业摄影风格，高清"
                    for desc in descs_for_gen
                ]
                logger.info(f"[{platform}] 开始生成配图: {len(enhanced_prompts)} 张，prompts={[p[:60] for p in enhanced_prompts]}")
                generated_urls = await image_generator.generate_batch(enhanced_prompts, size="2k")
                # 过滤失败的
                generated_urls = [u for u in generated_urls if u]
                logger.info(f"[{platform}] 配图生成完成: {len(generated_urls)}/{len(descs_for_gen)} 张")

                # 将生成的图片 URL 内联插入到正文指定位置
                body_lines = body.split("\n")
                url_idx = 0
                for marker_pos, _marker_desc in sorted(image_markers, key=lambda x: x[0], reverse=True):
                    # reverse order insert so positions don't shift
                    if url_idx < len(generated_urls) and generated_urls[url_idx]:
                        img_line = f"\n[配图:{generated_urls[url_idx]}]\n"
                        if marker_pos < len(body_lines):
                            body_lines.insert(marker_pos, img_line)
                        else:
                            body_lines.append(img_line)
                        image_urls.append(generated_urls[url_idx])
                    url_idx += 1
                body = "\n".join(body_lines)
            elif image_descs and image_generator.is_configured:
                # 旧格式回退：图片加到末尾
                enhanced_descs = [
                    f"{product_info['name']} — {desc}，{product_info.get('category', '')}相关，商业摄影风格"
                    for desc in image_descs
                ]
                logger.info(f"[{platform}] 开始生成配图（旧格式）: {len(enhanced_descs)} 张")
                gen_urls = await image_generator.generate_batch(enhanced_descs, size="2k")
                image_urls = [u for u in gen_urls if u]
                logger.info(f"[{platform}] 配图生成完成: {len(image_urls)}/{len(image_descs)} 张")
                if image_urls:
                    body += "\n\n" + "\n".join(f"[配图:{u}]" for u in image_urls)
            elif image_descs and not image_markers:
                # 有描述但没配置图片生成
                pass

            content = Content(
                product_id=product_id,
                platform=platform,
                title=data.get("title", ""),
                body=body,
                tags=data.get("tags", []),
                image_paths=image_urls,  # ← 真实生成的图片URL
                topic_category=topic_per_platform.get(platform),
                prompt_version="1.0",
                generation_params={
                    "raw": data.get("raw_generated", ""),
                    "image_descriptions": image_descs,
                    "image_urls": image_urls,
                    "image_markers": [(p, d) for p, d in image_markers],  # 可序列化
                },
                status="draft",
            )
            db.add(content)
            await db.flush()
            generated_ids.append(content.id)

        await db.commit()
        logger.info(f"[Task] 生成完成: {len(generated_ids)} 篇, errors={len(errors)}")
        return {"generated_ids": generated_ids, "platforms": list(results.keys()), "topics": topic_per_platform, "errors": errors}


async def scrape_data_task():
    """采集所有平台内容数据"""
    logger.info("[Task] 开始数据采集...")
    async with AsyncSessionLocal() as db:
        from backend.services.scraper import scraper
        result = await scraper.scrape_all_pending(db)
        return result


async def check_sessions_task():
    """检查所有账号会话状态"""
    logger.info("[Task] 开始会话检查...")
    from backend.services.session_manager import session_manager
    report = await session_manager.check_all_sessions()
    total = sum(len(info.get("accounts", [])) for info in report.values())
    expired = sum(
        1 for info in report.values()
        for acc in info.get("accounts", [])
        if not acc.get("valid", True)
    )
    logger.info(f"[Task] 会话检查完成: {total} 个账号, {expired} 个过期")
    return {"total": total, "expired": expired, "report": report}


async def analyze_optimize_task(product_id: int = None):
    """优化分析"""
    logger.info(f"[Task] 优化分析: product_id={product_id}")
    async with AsyncSessionLocal() as db:
        from backend.services.optimizer import optimizer
        if product_id:
            suggestions = await optimizer.analyze_and_optimize(product_id, db)
            for s in suggestions:
                change = OptimizationChange(**s)
                db.add(change)
            await db.commit()
            return {"suggestions_count": len(suggestions)}
        else:
            result = await db.execute(select(Product))
            products = result.scalars().all()
            total = 0
            for p in products:
                suggestions = await optimizer.analyze_and_optimize(p.id, db)
                for s in suggestions:
                    change = OptimizationChange(**s)
                    db.add(change)
                total += len(suggestions)
            await db.commit()
            return {"total_suggestions": total}
