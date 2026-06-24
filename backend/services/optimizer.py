"""
优化学习模块 — 改动记录 + 语义去重
"""
import hashlib
import json
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from backend.config import settings
from backend.services.ai_generator import ai_generator


class Optimizer:
    """优化引擎 — 分析数据差异，生成调整建议"""

    async def analyze_and_optimize(
        self, product_id: int, db_session
    ) -> List[Dict[str, Any]]:
        """
        分析流程：
        1. 拉取该产品在所有平台的历史发布数据和内容
        2. 横向对比（同产品不同平台差异）
        3. 纵向对比（同平台不同时间趋势）
        4. 识别表现差的平台和共性原因
        5. 生成优化建议（去重已有记录）
        """
        from sqlalchemy import select, and_, func
        from backend.models.models import Content, PublishRecord, ContentMetric, Product
        from datetime import datetime, timedelta
        from backend.utils.timezone_utils import now_shanghai

        # 1. 获取产品信息
        result = await db_session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            return []

        # 2. 获取该产品所有已发布内容
        contents_result = await db_session.execute(
            select(Content)
            .where(Content.product_id == product_id, Content.status == "published")
            .order_by(Content.created_at.desc())
        )
        contents = contents_result.scalars().all()

        if not contents:
            return [{"message": "暂无已发布内容，无法分析"}]

        # 3. 获取各平台的指标数据
        platform_metrics = {}
        for content in contents:
            # 获取最新指标
            result = await db_session.execute(
                select(ContentMetric)
                .join(PublishRecord)
                .where(PublishRecord.content_id == content.id)
                .order_by(ContentMetric.scraped_at.desc())
                .limit(1)
            )
            metric = result.scalar_one_or_none()
            if metric:
                if content.platform not in platform_metrics:
                    platform_metrics[content.platform] = []
                platform_metrics[content.platform].append({
                    "metric": metric,
                    "content": content,
                })

        # 4. 分析各平台表现
        suggestions = []
        for platform, metrics_list in platform_metrics.items():
            avg_engagement = self._calc_avg_engagement(metrics_list)
            if avg_engagement < 0.02:  # 互动率低于 2%
                suggestion = await self._generate_suggestion(
                    platform, product, metrics_list, avg_engagement, db_session
                )
                if suggestion:
                    # 检查去重
                    is_dup, similar_id = await self.check_duplicate(suggestion, db_session)
                    suggestion["is_duplicate"] = is_dup
                    suggestion["similar_to_change_id"] = similar_id
                    suggestions.append(suggestion)

        return suggestions

    def _calc_avg_engagement(self, metrics_list: list) -> float:
        """计算平均互动率"""
        if not metrics_list:
            return 0.0
        total_interactions = 0
        total_views = 0
        for item in metrics_list:
            m = item["metric"]
            total_interactions += (m.likes or 0) + (m.comments or 0) + (m.shares or 0) + (m.collects or 0)
            total_views += m.views or 0
        return total_interactions / max(total_views, 1)

    async def _generate_suggestion(
        self, platform: str, product, metrics_list: list, avg_engagement: float, db_session
    ) -> Dict[str, Any]:
        """生成优化建议"""
        # 构建提示词
        prompt = f"""
你是内容优化专家。以下是 {platform} 平台上「{product.name}」的运营数据：

平台：{platform}
平均互动率：{avg_engagement:.2%}（低于 2% 阈值）
发布内容数：{len(metrics_list)}

各篇表现：
{self._format_metrics(metrics_list)}

请分析表现差的原因，并给出优化建议。

返回 JSON 格式：
{{
  "issue": "问题总结",
  "hypothesis": "可能原因（小红书互动率低通常是标题不够吸引/缺少emoji/图片质量不够精美）",
  "action": "建议采取的优化动作（调整提示词：增加标题吸引力要求/增加emoji比例/强化配图要求）",
  "change_type": "prompt_tuning"
}}
"""
        try:
            response = await ai_generator.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            text = response.choices[0].message.content
            # 解析 JSON
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "platform": platform,
                    "issue_description": data.get("issue", "数据表现不佳"),
                    "hypothesis": data.get("hypothesis", ""),
                    "action_taken": data.get("action", ""),
                    "change_type": data.get("change_type", "prompt_tuning"),
                    "product_id": product.id,
                }
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")

        return {
            "platform": platform,
            "issue_description": f"{platform} 互动率 {avg_engagement:.2%} 低于阈值",
            "hypothesis": "可能是标题/配图/内容风格不匹配平台调性",
            "action_taken": "建议人工审查提示词配置",
            "change_type": "manual_review",
            "product_id": product.id,
        }

    def _format_metrics(self, metrics_list: list) -> str:
        lines = []
        for item in metrics_list:
            m = item["metric"]
            c = item["content"]
            lines.append(f"- {c.title[:30]}: 阅读{m.views} 点赞{m.likes} 评论{m.comments}")
        return "\n".join(lines)

    async def check_duplicate(
        self, suggestion: Dict[str, Any], db_session
    ) -> Tuple[bool, Optional[int]]:
        """
        AI 语义去重：判断新建议是否与历史改动本质相同
        返回：(is_duplicate, similar_change_id)
        """
        from sqlalchemy import select
        from backend.models.models import OptimizationChange
        from datetime import datetime, timedelta
        from backend.utils.timezone_utils import now_shanghai

        # 获取近期改动
        cutoff = now_shanghai() - timedelta(days=30)
        result = await db_session.execute(
            select(OptimizationChange)
            .where(
                OptimizationChange.product_id == suggestion["product_id"],
                OptimizationChange.platform == suggestion["platform"],
                OptimizationChange.created_at > cutoff,
            )
        )
        recent_changes = result.scalars().all()

        if not recent_changes:
            return False, None

        # AI 语义匹配
        change_summaries = []
        for c in recent_changes:
            change_summaries.append({
                "id": c.id,
                "issue": c.issue_description,
                "action": c.action_taken,
            })

        prompt = f"""
已有历史改动记录：
{json.dumps(change_summaries, ensure_ascii=False, indent=2)}

新建议：
- 问题：{suggestion['issue_description']}
- 动作：{suggestion['action_taken']}

请判断新建议是否与历史改动本质相同（即使表述不同但目标和方法一致）。
返回严格 JSON：{{"is_duplicate": true/false, "similar_id": 最相似的记录ID或null, "reason": "原因"}}
"""
        try:
            response = await ai_generator.client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            is_dup = result.get("is_duplicate", False)
            similar_id = result.get("similar_id")
            return bool(is_dup), similar_id
        except Exception as e:
            logger.warning(f"语义去重 AI 调用失败，默认不重复: {e}")
            return False, None


optimizer = Optimizer()
