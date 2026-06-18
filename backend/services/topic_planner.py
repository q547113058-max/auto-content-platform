"""
选题调度器 — 多臂老虎机 (Multi-Armed Bandit) 策略
支持 探索期(轮询) → 收敛期(80/20) → 稳态(季度重评) 三阶段
+ 去重检查：同一产品+同一选题+同一平台 N 天内不重复
"""
import random
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from loguru import logger

from backend.topic_config import (
    FISHERY_TOPICS, TOPIC_MAP, TOPIC_LIST,
    PLATFORM_TOPIC_PRIORITY, DEDUP_WINDOW_DAYS,
)


class TopicPlanner:
    """选题调度引擎"""

    # ==================== 公开 API ====================

    @classmethod
    def get_all_categories(cls) -> List[dict]:
        """获取全部选题类别（前端下拉框用）"""
        return [t.to_dict() for t in FISHERY_TOPICS]

    @classmethod
    def get_platform_topics(cls, platform: str) -> List[str]:
        """获取某平台推荐的选题列表（按优先级排序）"""
        return PLATFORM_TOPIC_PRIORITY.get(platform, TOPIC_LIST)

    @classmethod
    async def suggest(
        cls, product_id: int, platform: str, db,
        topic_rotation: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, dict]:
        """
        核心方法：为指定产品+平台推荐下一个选题

        Returns:
            (topic_id, phase, debug_info)
        """
        topic_rotation = topic_rotation or cls._default_rotation()
        phase = topic_rotation.get("phase", "explore")
        topic_stats = topic_rotation.get("topic_stats", {})
        last_used = topic_rotation.get("last_used", {})

        # 1. 根据阶段选策略
        if phase == "explore":
            topic_id = cls._explore_strategy(platform, topic_stats, last_used)
        else:
            topic_id = cls._converge_strategy(platform, topic_stats, last_used)

        # 2. 去重检查
        topic_id = await cls._dedup_check(topic_id, product_id, platform, db)

        # 3. 记录使用时间
        now = datetime.utcnow().isoformat()
        key = f"{platform}:{topic_id}"
        last_used[key] = now
        topic_rotation["last_used"] = last_used

        # 4. 更新统计
        if topic_id not in topic_stats:
            topic_stats[topic_id] = {"uses": 0, "total_engagement": 0, "count": 0}
        topic_stats[topic_id]["uses"] += 1
        topic_rotation["topic_stats"] = topic_stats

        debug = {
            "phase": phase,
            "platform_topics": cls.get_platform_topics(platform),
            "topic_stats_snapshot": {k: v.get("uses", 0) for k, v in topic_stats.items()},
        }

        logger.info(f"[TopicPlanner] product={product_id} platform={platform} → {topic_id} (phase={phase})")
        return topic_id, phase, debug

    @classmethod
    def evaluate_phase(cls, topic_rotation: Dict[str, Any]) -> str:
        """评估当前应该处于哪个阶段"""
        stats = topic_rotation.get("topic_stats", {})
        total_uses = sum(s.get("uses", 0) for s in stats.values())
        topics_with_data = sum(1 for s in stats.values() if s.get("uses", 0) >= 3)

        if total_uses < 20 or topics_with_data < 3:
            return "explore"
        elif total_uses < 60:
            return "converge"
        else:
            return "steady"

    @classmethod
    def record_engagement(
        cls, topic_rotation: Dict[str, Any], topic_id: str,
        views: int, likes: int, comments: int, shares: int, collects: int,
    ) -> dict:
        """记录一篇内容的互动数据，更新选题统计"""
        engagement = likes * 1.0 + comments * 2.0 + shares * 3.0 + collects * 2.5
        rate = engagement / max(views, 1)

        stats = topic_rotation.get("topic_stats", {})
        if topic_id not in stats:
            stats[topic_id] = {"uses": 0, "total_engagement": 0.0, "count": 0, "avg_engagement": 0.0}
        stats[topic_id]["total_engagement"] = stats[topic_id].get("total_engagement", 0) + engagement
        stats[topic_id]["count"] = stats[topic_id].get("count", 0) + 1
        stats[topic_id]["avg_engagement"] = (
            stats[topic_id]["total_engagement"] / stats[topic_id]["count"]
        )
        topic_rotation["topic_stats"] = stats

        # 重新评估阶段
        new_phase = cls.evaluate_phase(topic_rotation)
        if new_phase != topic_rotation.get("phase", "explore"):
            logger.info(f"[TopicPlanner] 阶段切换: {topic_rotation.get('phase')} → {new_phase}")
            topic_rotation["phase"] = new_phase

        return topic_rotation

    # ==================== 内部策略 ====================

    @classmethod
    def _explore_strategy(cls, platform: str, stats: dict, last_used: dict) -> str:
        """探索期 — LRU 轮询：优先选最久没用的方向"""
        candidates = cls.get_platform_topics(platform)
        ranked = sorted(candidates, key=lambda t: last_used.get(f"{platform}:{t}", "2000-01-01"))
        return ranked[0]

    @classmethod
    def _converge_strategy(cls, platform: str, stats: dict, last_used: dict) -> str:
        """收敛期 — 80/20 分配：80% 概率选 Top 3，20% 概率选其余方向"""
        if random.random() < 0.2:
            return cls._explore_strategy(platform, stats, last_used)

        candidates = cls.get_platform_topics(platform)
        scored = []
        for t in candidates:
            s = stats.get(t, {})
            avg = s.get("avg_engagement", 0)
            uses = s.get("uses", 0)
            # 威尔逊下限修正：少量样本降低置信度
            if uses < 3:
                avg *= (uses / 3)
            scored.append((t, avg))

        scored.sort(key=lambda x: x[1], reverse=True)
        top3 = [t[0] for t in scored[:3]]
        if top3:
            return random.choices(top3, weights=[3, 2, 1], k=1)[0]
        return cls._explore_strategy(platform, stats, last_used)

    @classmethod
    async def _dedup_check(cls, topic_id: str, product_id: int, platform: str, db) -> str:
        """去重：同一产品+选题+平台 在 DEDUP_WINDOW_DAYS 天内不重复"""
        from sqlalchemy import select, and_
        from backend.models.models import Content

        cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
        result = await db.execute(
            select(Content).where(
                and_(
                    Content.product_id == product_id,
                    Content.platform == platform,
                    Content.topic_category == topic_id,
                    Content.created_at >= cutoff,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"[TopicPlanner] 去重拦截: product={product_id} platform={platform} topic={topic_id}")
            # 换一个没在该平台用过的方向
            return await cls._fallback_topic(topic_id, platform, product_id, db)
        return topic_id

    @classmethod
    async def _fallback_topic(cls, exclude: str, platform: str, product_id: int, db) -> str:
        """找一个替代选题（未在去重窗口内使用过）"""
        from sqlalchemy import select, and_
        from backend.models.models import Content

        cutoff = datetime.utcnow() - timedelta(days=DEDUP_WINDOW_DAYS)
        result = await db.execute(
            select(Content.topic_category).where(
                and_(
                    Content.product_id == product_id,
                    Content.platform == platform,
                    Content.created_at >= cutoff,
                )
            ).distinct()
        )
        used = {r[0] for r in result.all()}

        candidates = [t for t in cls.get_platform_topics(platform) if t not in used and t != exclude]
        if not candidates:
            candidates = [t for t in TOPIC_LIST if t not in used and t != exclude]
        if not candidates:
            candidates = [t for t in TOPIC_LIST if t != exclude]

        return candidates[0] if candidates else exclude

    @classmethod
    async def get_history(cls, product_id: int, db) -> List[dict]:
        """获取某产品最近的选题历史"""
        from sqlalchemy import select
        from backend.models.models import Content

        result = await db.execute(
            select(Content.topic_category, Content.platform, Content.created_at, Content.id, Content.title)
            .where(Content.product_id == product_id)
            .where(Content.topic_category.isnot(None))
            .order_by(Content.created_at.desc())
            .limit(50)
        )
        return [
            {
                "content_id": r.id, "topic_category": r.topic_category,
                "topic_name": TOPIC_MAP.get(r.topic_category, {}).id if hasattr(TOPIC_MAP.get(r.topic_category, {}), 'id') else "未知",
                "platform": r.platform, "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in result.all()
        ]

    @classmethod
    def _default_rotation(cls) -> dict:
        return {
            "phase": "explore",
            "topic_stats": {},
            "last_used": {},
            "created_at": datetime.utcnow().isoformat(),
        }


# 全局单例
topic_planner = TopicPlanner()
