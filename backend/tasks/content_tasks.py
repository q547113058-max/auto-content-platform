"""
异步任务模块
Celery 延迟初始化 — 本地无 Redis 时直接调用 async 函数
"""
import asyncio
from loguru import logger
from backend.config import settings
from backend.models.database import AsyncSessionLocal
from backend.models.models import (
    Content, Product, Company, OptimizationChange, KnowledgeBaseDoc
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


# ==================== 三模式知识库构建辅助函数 ====================

async def _build_product_info(db, product_id: int, company_id: int = None, content_mode: str = "product") -> dict:
    """
    按 content_mode 从知识库构建 product_info 字典。

    content_mode:
      - product  : 仅加载产品级知识库（原逻辑）
      - company  : 仅加载公司级知识库，主体信息来自 Company
      - mixed    : 公司知识库为主体 + 产品知识库补充（公司为主，产品为辅）
    """
    from backend.services.kb_parser import parse_knowledge_base

    product = None
    company = None

    # 1. 加载产品和公司基础信息
    if product_id:
        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if product and product.company_id and not company_id:
            company_id = product.company_id

    if company_id:
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

    # 混合模式自动收集的公司产品名（product/company 模式用默认值）
    combined_product_name = ""

    # 2. 按模式合并知识库 Markdown
    kb_parts = []

    if content_mode == "product":
        # ── 纯产品模式：只取产品知识库 ──
        if product_id:
            prod_docs = (await db.execute(
                select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.product_id == product_id)
            )).scalars().all()
            for doc in prod_docs:
                if doc.content:
                    kb_parts.append(f"## {doc.title}\n{doc.content}")

            # 也附加公司级知识库（作为行业背景）
            if product and product.company_id:
                comp_docs = (await db.execute(
                    select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.company_id == product.company_id)
                )).scalars().all()
                for doc in comp_docs:
                    if doc.content:
                        kb_parts.append(f"## [公司背景] {doc.title}\n{doc.content}")

        logger.info(f"[KB:product] product_id={product_id}, 共 {len(kb_parts)} 个文档片段")

    elif content_mode == "company":
        # ── 纯公司模式：只取公司级知识库 ──
        if company_id:
            comp_docs = (await db.execute(
                select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.company_id == company_id)
            )).scalars().all()
            for doc in comp_docs:
                if doc.content:
                    kb_parts.append(f"## {doc.title}\n{doc.content}")

        logger.info(f"[KB:company] company_id={company_id}, 共 {len(kb_parts)} 个文档片段")

    elif content_mode == "mixed":
        # ── 混合模式：先做广告密度决策，再决定是否加载产品知识库 ──
        #    混合模式不需要用户选产品——系统自动拉取该公司所有产品
        from backend.services.ad_ratio_analyzer import ad_ratio_analyzer, AdRatioDecision
        from backend.models.models import Product as ProductModel

        # 自动查询该公司旗下所有产品
        company_products: list = []
        if company_id:
            prod_result = await db.execute(
                select(ProductModel).where(ProductModel.company_id == company_id)
            )
            company_products = prod_result.scalars().all()

        # 用公司所有产品名做广告密度关键词匹配
        all_product_names = [p.name for p in company_products if p.name] if company_products else []
        combined_product_name = "、".join(all_product_names) if all_product_names else ""

        # 自主分析近期文章广告密度（不由用户控制）
        ad_decision: AdRatioDecision = await ad_ratio_analyzer.analyze(
            db=db,
            company_id=company_id,
            product_id=None,  # 混合模式不限定单个产品
            product_name=combined_product_name,  # 用所有产品名匹配
        )
        logger.info(
            f"[AdRatio:mixed] 公司产品={all_product_names} | "
            f"决策=include_product:{ad_decision.include_product} "
            f"suppress:{ad_decision.suppress_product_name} | {ad_decision.reason}"
        )

        # 公司知识库始终加载（公司永远是主体）
        if company_id:
            comp_docs = (await db.execute(
                select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.company_id == company_id)
            )).scalars().all()
            for doc in comp_docs:
                if doc.content:
                    kb_parts.append(f"## [公司主体] {doc.title}\n{doc.content}")

        # 仅当决策允许时才加载所有公司产品的知识库
        if ad_decision.include_product and company_products:
            for prod in company_products:
                prod_docs = (await db.execute(
                    select(KnowledgeBaseDoc).where(KnowledgeBaseDoc.product_id == prod.id)
                )).scalars().all()
                for doc in prod_docs:
                    if doc.content:
                        kb_parts.append(f"## [产品补充-{prod.name}] {doc.title}\n{doc.content}")

        logger.info(
            f"[KB:mixed] company_id={company_id}, 公司产品={len(company_products)}个, "
            f"加载产品KB={ad_decision.include_product and bool(company_products)}, "
            f"共 {len(kb_parts)} 个文档片段"
        )

    # 3. 解析结构化字段
    merged_raw = "\n\n".join(kb_parts)
    category = ""
    if product:
        category = product.category or ""
    elif company:
        category = company.industry or ""

    kb_structured = parse_knowledge_base(merged_raw, category)

    # 4. 品牌调性
    tone = ""
    if product and product.tone_config:
        tone = product.tone_config.get("style", "")
    if not tone and product:
        cat = product.category or ""
        tone_map = {
            "渔业设备": "专业可靠、科技赋能养殖、降本增效",
            "农业设备": "精准种植、智慧农业、省时省力",
        }
        tone = tone_map.get(cat, "")

    # 5. 确定主体名称和分类
    if content_mode == "company":
        main_name = company.name if company else "品牌"
        main_category = company.industry or category
    elif content_mode == "mixed":
        # 公司为主体，产品作为辅助提及
        main_name = company.name if company else (product.name if product else "品牌")
        main_category = company.industry or category
    else:  # product
        main_name = product.name if product else "产品"
        main_category = category

    # 6. 构建 product_info（兼容现有 prompt 模板的占位符）
    #    mixed 模式：若决策不引入产品，则产品相关字段清空，避免 AI 凭字段内容写出产品推销
    _include_product_fields = True
    if content_mode == "mixed":
        # ad_decision 在上面的 elif 块中已赋值，此处通过局部变量传递
        try:
            _include_product_fields = ad_decision.include_product  # type: ignore[name-defined]
        except NameError:
            _include_product_fields = True  # 兜底

    product_info = {
        "name": main_name,
        "category": main_category,
        "price": kb_structured.get("price", "") if _include_product_fields else "",
        "key_ingredients": kb_structured.get("key_ingredients", "") if _include_product_fields else "",
        "claims": kb_structured.get("claims", "") if _include_product_fields else "",
        "key_points": kb_structured.get("key_points", "") if _include_product_fields else "",
        "target_audience": kb_structured.get("target_audience", ""),
        "industry_context": kb_structured.get("industry_context", ""),
        "tone_keywords": tone,
        # 额外字段（可在 prompt 模板中引用）
        "company_name": company.name if company else "",
        # 产品名：非混合模式用 product.name；混合模式用公司所有产品名
        "product_name": (
            (product.name if product else "")
            if content_mode != "mixed"
            else (combined_product_name if _include_product_fields else "")
        ),
        "content_mode": content_mode,
    }

    # 7. 混合/公司模式时，在 system_prompt 追加额外指令
    mode_instruction = ""
    if content_mode == "company":
        mode_instruction = (
            f"\n\n【生成模式：纯公司品牌内容】\n"
            f"本次内容以「{main_name}」公司/品牌为主体，重点展示品牌形象、行业地位、"
            f"企业文化、技术实力等，不专注于单一产品推介。"
        )
    elif content_mode == "mixed":
        prod_name = combined_product_name or "旗下产品"
        try:
            _ad = ad_decision  # type: ignore[name-defined]
        except NameError:
            from backend.services.ad_ratio_analyzer import AdRatioDecision
            _ad = AdRatioDecision(
                include_product=True, ad_ratio=0.0, sample_count=0,
                reason="无历史数据", product_articles=0, suppress_product_name=False
            )

        if not _ad.include_product:
            # 广告过多 → 彻底不引入产品，指令等同纯公司
            mode_instruction = (
                f"\n\n【生成模式：混合（本篇纯公司）】\n"
                f"系统检测到近期内容中产品/广告比例过高（{_ad.ad_ratio:.0%}），"
                f"本篇内容以「{main_name}」品牌为主体，"
                f"不提及具体产品名称和产品功能，专注品牌形象、行业见解、企业文化等主题。\n"
                f"禁止出现任何产品推销、购买引导、产品参数介绍等内容。"
            )
        elif _ad.suppress_product_name:
            # 中间区间 → 允许引入但严格控制产品比重
            mode_instruction = (
                f"\n\n【生成模式：混合（产品轻描述）】\n"
                f"系统检测到近期产品内容占比适中（{_ad.ad_ratio:.0%}），"
                f"本篇以「{main_name}」品牌为主体（不少于全文 80%），"
                f"可在结尾处轻描述旗下产品「{prod_name}」一次（不超过 50 字），"
                f"严禁出现购买引导、价格、促销等广告语。"
            )
        else:
            # 广告稀少 → 正常混合，可以自然引入产品
            mode_instruction = (
                f"\n\n【生成模式：混合（正常）】\n"
                f"本篇以「{main_name}」品牌为主体（占内容 70%+），"
                f"可自然带出旗下产品「{prod_name}」作为佐证（不超过全文 30%）。"
                f"重心在于展示品牌综合实力，产品信息仅做自然引用，不做重点推销。"
            )

    # 将广告密度决策附加到返回值（供 generate_content_task 写入 generation_params）
    ad_decision_meta = None
    if content_mode == "mixed":
        try:
            ad_decision_meta = {   # type: ignore[name-defined]
                "include_product": _ad.include_product,
                "suppress_product_name": _ad.suppress_product_name,
                "ad_ratio": round(_ad.ad_ratio, 3),
                "sample_count": _ad.sample_count,
                "product_articles": _ad.product_articles,
                "reason": _ad.reason,
            }
        except NameError:
            pass

    return {
        "product_info": product_info,
        "mode_instruction": mode_instruction,
        "product": product,
        "company": company,
        "ad_decision_meta": ad_decision_meta,
    }


# ==================== 主任务函数（直接调用） ====================

async def generate_content_task(
    product_id: int = None,
    company_id: int = None,
    content_mode: str = "product",
    platforms: list = None,
    override_prompt: str = None,
    topic_category: str = None,
):
    """
    AI 内容生成 — 三模式统一调度

    content_mode:
      product  → 以产品为主体（须传 product_id）
      company  → 以公司为主体（须传 company_id）
      mixed    → 公司为主 + 产品辅助（须传 company_id，product_id 可选）
    """
    logger.info(
        f"[Task] 生成内容: mode={content_mode}, product_id={product_id}, "
        f"company_id={company_id}, platforms={platforms}, topic={topic_category}"
    )

    # 参数校验
    if content_mode == "product" and not product_id:
        return {"error": "纯产品模式必须传 product_id"}
    if content_mode in ("company", "mixed") and not company_id:
        return {"error": f"{content_mode} 模式必须传 company_id"}

    async with AsyncSessionLocal() as db:
        # ── 构建知识库 & product_info ──
        ctx = await _build_product_info(db, product_id, company_id, content_mode)
        product_info = ctx["product_info"]
        mode_instruction = ctx["mode_instruction"]
        product = ctx["product"]
        company = ctx["company"]
        ad_decision_meta = ctx.get("ad_decision_meta")  # 混合模式广告密度决策元数据

        # 注入模式指令到 override_prompt
        effective_override = override_prompt or ""
        if mode_instruction:
            effective_override = (effective_override + mode_instruction).strip() or None

        # ── 选题调度 ──
        from backend.services.topic_planner import topic_planner
        from backend.topic_config import TOPIC_MAP

        # 以产品为调度主体（纯公司模式也允许选题轮询，但用公司ID兜底）
        rotation_holder = product  # 仅 product 模式有意义
        topic_per_platform = {}

        if platforms is None:
            platforms = ["xiaohongshu", "zhihu", "weibo", "wechat", "toutiao", "douyin"]

        if topic_category and topic_category in TOPIC_MAP:
            topic_per_platform = {p: topic_category for p in platforms}
        else:
            if rotation_holder:
                rotation = rotation_holder.topic_rotation or {}
                for p in platforms:
                    tid, phase, _debug = await topic_planner.suggest(product_id, p, db, rotation)
                    topic_per_platform[p] = tid
                rotation_holder.topic_rotation = rotation
            else:
                # 公司模式：无产品，使用固定选题或全量轮询
                for p in platforms:
                    topic_per_platform[p] = "industry_trend"  # 公司模式默认行业趋势

        # ── 注入 topic 指令 ──
        from backend.services.ai_generator import ai_generator
        topic_prompt_map = {}
        topic_name_map = {}
        for p in platforms:
            tid = topic_per_platform.get(p, "tech_explanation")
            tc = TOPIC_MAP.get(tid)
            if tc:
                topic_prompt_map[p] = tc.prompt_injection
                topic_name_map[p] = tc.name
                if p in tc.platform_specific:
                    topic_prompt_map[p] += "\n" + tc.platform_specific[p]

        # ── AI 生成 ──
        results = await ai_generator.generate_for_all_platforms(
            product_info, platforms, effective_override or None, topic_prompt_map, topic_name_map
        )

        # ── 配图生成 ──
        from backend.services.image_generator import image_generator

        generated_ids = []
        errors = []

        for platform, data in results.items():
            if "error" in data:
                logger.warning(f"[{platform}] 生成失败: {data['error']}")
                errors.append({"platform": platform, "error": data["error"]})
                continue

            image_markers = data.get("image_markers", [])
            image_descs = data.get("image_descriptions", [])
            if not image_markers and image_descs:
                image_markers = [(len(data.get("body", "").split("\n")), d) for d in image_descs]

            image_urls = []
            body = data.get("body", "")

            if image_markers and image_generator.is_configured:
                descs_for_gen = [m[1] for m in image_markers if m[1]]
                enhanced_prompts = [
                    f"{product_info['name']} — {desc}，{product_info.get('category', '')}相关，商业摄影风格，高清"
                    for desc in descs_for_gen
                ]
                logger.info(f"[{platform}] 开始生成配图: {len(enhanced_prompts)} 张")
                generated_urls = await image_generator.generate_batch(enhanced_prompts, size="2k")
                generated_urls = [u for u in generated_urls if u]
                logger.info(f"[{platform}] 配图生成完成: {len(generated_urls)}/{len(descs_for_gen)} 张")

                body_lines = body.split("\n")
                url_idx = 0
                for marker_pos, _marker_desc in sorted(image_markers, key=lambda x: x[0], reverse=True):
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
                enhanced_descs = [
                    f"{product_info['name']} — {desc}，{product_info.get('category', '')}相关，商业摄影风格"
                    for desc in image_descs
                ]
                gen_urls = await image_generator.generate_batch(enhanced_descs, size="2k")
                image_urls = [u for u in gen_urls if u]
                if image_urls:
                    body += "\n\n" + "\n".join(f"[配图:{u}]" for u in image_urls)

            content = Content(
                product_id=product_id,
                company_id=company_id or (product.company_id if product else None),
                content_mode=content_mode,
                platform=platform,
                title=data.get("title", ""),
                body=body,
                tags=data.get("tags", []),
                image_paths=image_urls,
                topic_category=topic_per_platform.get(platform),
                prompt_version="1.0",
                generation_params={
                    "raw": data.get("raw_generated", ""),
                    "image_descriptions": image_descs,
                    "image_urls": image_urls,
                    "image_markers": [(p, d) for p, d in image_markers],
                    "content_mode": content_mode,
                    # 混合模式广告密度决策记录（便于审计和调试）
                    "ad_ratio_decision": ad_decision_meta,
                },
                status="draft",
            )
            db.add(content)
            await db.flush()
            generated_ids.append(content.id)

        await db.commit()
        logger.info(f"[Task] 生成完成: mode={content_mode}, {len(generated_ids)} 篇, errors={len(errors)}")
        return {
            "generated_ids": generated_ids,
            "platforms": list(results.keys()),
            "topics": topic_per_platform,
            "errors": errors,
            "content_mode": content_mode,
        }


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
