"""
定时任务调度器 — APScheduler 集成
负责自动串联数据抓取→分析→优化→建议生成的完整闭环
"""
import asyncio
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """获取或创建调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,       # 合并错过的任务
                "max_instances": 1,     # 同一任务同时最多1个实例
                "misfire_grace_time": 300,  # 错过 5 分钟内仍执行
            },
        )
    return _scheduler


# ==================== 闭环任务函数 ====================

async def job_scrape_data():
    """定时任务1：数据抓取 — 每 6 小时"""
    logger.info("[调度器] 开始定时数据抓取...")
    try:
        from backend.models.database import AsyncSessionLocal
        from backend.services.scraper import scraper
        async with AsyncSessionLocal() as db:
            result = await scraper.scrape_all_pending(db)
        logger.info(f"[调度器] 数据抓取完成: {result}")
    except Exception as e:
        logger.error(f"[调度器] 数据抓取失败: {e}")


async def job_analyze_all():
    """定时任务2：全产品优化分析 — 每日"""
    logger.info("[调度器] 开始全产品优化分析...")
    try:
        from backend.models.database import AsyncSessionLocal
        from backend.services.optimizer import optimizer
        from backend.models.models import Product, OptimizationChange
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Product))
            products = result.scalars().all()

            total_suggestions = 0
            for product in products:
                try:
                    suggestions = await optimizer.analyze_and_optimize(product.id, db)
                    for s in suggestions:
                        change = OptimizationChange(**s)
                        db.add(change)
                    total_suggestions += len(suggestions)
                except Exception as e:
                    logger.error(f"[调度器] 产品 {product.id} 分析失败: {e}")

            await db.commit()
            logger.info(f"[调度器] 优化分析完成: {len(products)} 产品, {total_suggestions} 建议")
    except Exception as e:
        logger.error(f"[调度器] 优化分析失败: {e}")


async def job_check_sessions():
    """定时任务3：会话健康检查 — 每 12 小时"""
    logger.info("[调度器] 开始会话健康检查...")
    try:
        from backend.services.session_manager import session_manager
        report = await session_manager.check_all_sessions()
        total = sum(len(info.get("accounts", [])) for info in report.values()) if isinstance(report, dict) else 0
        logger.info(f"[调度器] 会话检查完成: {total} 个账号")
    except Exception as e:
        logger.error(f"[调度器] 会话检查失败: {e}")


async def job_auto_optimize_loop():
    """
    定时任务4：自动优化闭环 — 每日执行一次完整闭环
    抓取最新数据 → 分析效果 → 生成优化建议 → 标记待审核
    """
    logger.info("[调度器] 开始自动优化闭环...")
    try:
        from backend.models.database import AsyncSessionLocal
        from backend.services.scraper import scraper
        from backend.services.optimizer import optimizer
        from backend.models.models import Product, OptimizationChange, Content
        from sqlalchemy import select, func, and_

        async with AsyncSessionLocal() as db:
            # Step 1: 抓取最新数据
            logger.info("[闭环] Step 1/4: 抓取最新数据...")
            scrape_result = await scraper.scrape_all_pending(db)
            logger.info(f"[闭环] 数据抓取: {scrape_result.get('scraped', 0)} 篇")

            # Step 2: 找出有活跃内容的产品（近7天有发布/有新鲜数据）
            logger.info("[闭环] Step 2/4: 筛选活跃产品...")
            from datetime import datetime as dt, timedelta
            from backend.models.models import PublishRecord, ContentMetric

            seven_days_ago = dt.utcnow() - timedelta(days=7)

            # 查找有新抓取数据的产品
            active_product_query = (
                select(Content.product_id.distinct())
                .join(PublishRecord, PublishRecord.content_id == Content.id)
                .join(ContentMetric, ContentMetric.publish_record_id == PublishRecord.id)
                .where(ContentMetric.scraped_at >= seven_days_ago)
            )
            result = await db.execute(active_product_query)
            active_product_ids = [row[0] for row in result.all()]

            if not active_product_ids:
                logger.info("[闭环] 无活跃产品，跳过分析")
                return {"status": "no_active_products"}

            # Step 3: 逐个产品分析并生成建议
            logger.info(f"[闭环] Step 3/4: 分析 {len(active_product_ids)} 个活跃产品...")
            total_changes = 0
            for pid in active_product_ids:
                try:
                    suggestions = await optimizer.analyze_and_optimize(pid, db)
                    for s in suggestions:
                        # 只保存非重复的实质性建议
                        if not s.get("is_duplicate", False):
                            change = OptimizationChange(**s)
                            db.add(change)
                            total_changes += 1
                except Exception as e:
                    logger.error(f"[闭环] 产品 {pid} 分析失败: {e}")

            await db.commit()

            # Step 4: 输出闭环报告
            logger.info(f"[闭环] Step 4/4: 完成 — {len(active_product_ids)} 产品, {total_changes} 新建议")
            return {
                "status": "completed",
                "scraped": scrape_result.get("scraped", 0),
                "active_products": len(active_product_ids),
                "new_suggestions": total_changes,
                "timestamp": dt.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"[调度器] 自动优化闭环失败: {e}")
        return {"status": "error", "error": str(e)}


# ==================== 调度器启动 ====================

def start_scheduler():
    """启动所有定时任务"""
    scheduler = get_scheduler()

    # 数据抓取：每 6 小时
    scheduler.add_job(
        job_scrape_data,
        trigger=IntervalTrigger(hours=6),
        id="scrape_data",
        name="数据抓取（每6小时）",
        replace_existing=True,
    )

    # 优化分析：每日凌晨 3:00
    scheduler.add_job(
        job_analyze_all,
        trigger=CronTrigger(hour=3, minute=0),
        id="analyze_all",
        name="全产品优化分析（每日03:00）",
        replace_existing=True,
    )

    # 会话检查：每 12 小时
    scheduler.add_job(
        job_check_sessions,
        trigger=IntervalTrigger(hours=12),
        id="check_sessions",
        name="会话健康检查（每12小时）",
        replace_existing=True,
    )

    # 自动优化闭环：每日凌晨 4:00（在数据抓取和分析之后）
    scheduler.add_job(
        job_auto_optimize_loop,
        trigger=CronTrigger(hour=4, minute=0),
        id="auto_optimize_loop",
        name="自动优化闭环（每日04:00）",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[调度器] 已启动 (4 个定时任务)")
    return scheduler


def stop_scheduler():
    """停止调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[调度器] 已停止")
