"""
广告密度自主分析器 — 混合模式专用

职责：
  在 mixed 模式生成前，自动分析该公司最近若干篇文章中的产品/广告内容密度，
  根据分析结论自主决定本篇是否引入产品信息。

决策逻辑：
  ┌──────────────────────────────────────────┐
  │ 近 N 篇中"含产品"文章占比  →  本篇决策  │
  │  < AD_RATIO_LOW   (30%)  →  可以引入产品  │
  │  AD_RATIO_LOW ~ HIGH     →  随机/权重引入 │
  │  > AD_RATIO_HIGH  (60%)  →  本篇纯公司   │
  └──────────────────────────────────────────┘

"含产品"的判断：
  1. 快速规则判断：body 中出现产品名/产品推荐词超过阈值字数
  2. 若规则无法判断（无产品名），调用轻量 LLM 打分

决策结果通过 AdRatioDecision 对象返回，供 content_tasks._build_product_info 使用。
"""
import re
from dataclasses import dataclass
from typing import Optional, List
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

# 调节参数 — 可在 config 中覆盖
AD_RATIO_LOW = 0.30    # 低于此比率 → 允许引入产品
AD_RATIO_HIGH = 0.60   # 高于此比率 → 本篇纯公司
LOOKBACK_COUNT = 10    # 回溯最近多少篇 mixed 模式文章
MIN_SAMPLE = 3         # 样本不足时放宽决策（默认允许）
AD_DENSITY_THRESHOLD = 0.08  # 单篇文章中产品相关词占比超过此值视为"含广告"


@dataclass
class AdRatioDecision:
    """广告密度决策结果"""
    include_product: bool          # 本篇是否引入产品信息
    ad_ratio: float                # 近期文章广告占比 (0-1)
    sample_count: int              # 分析样本数
    reason: str                    # 决策理由（供日志/调试）
    product_articles: int          # 样本中含产品文章数
    suppress_product_name: bool    # 即使 include_product=True，是否压低产品名提及


class AdRatioAnalyzer:
    """
    混合模式广告密度分析器
    全局单例，无状态，每次调用独立分析
    """

    # 产品推广相关词库（规则快速判断）
    AD_KEYWORDS = [
        "购买", "下单", "立即购", "点击购", "优惠", "折扣", "促销",
        "特价", "买即送", "赠品", "套装", "旗舰店", "淘宝", "京东",
        "扫码", "咨询", "联系我们", "代理", "经销商", "推荐使用",
        "效果显著", "深受好评", "畅销", "爆款",
    ]

    def _score_single_article(self, body: str, product_name: str = "") -> float:
        """
        规则打分：计算单篇文章的广告密度分数 (0-1)
        分数越高，广告内容越多。
        """
        if not body:
            return 0.0

        body_len = len(body)
        ad_hits = 0

        # 1. 广告关键词命中
        for kw in self.AD_KEYWORDS:
            count = body.count(kw)
            ad_hits += count * len(kw)

        # 2. 产品名多次出现（超过 2 次视为刻意推销）
        if product_name and len(product_name) >= 2:
            occurrences = body.count(product_name)
            if occurrences > 2:
                ad_hits += (occurrences - 2) * len(product_name) * 2  # 加权

        # 3. 价格数字出现（￥/元）
        price_matches = len(re.findall(r'[￥¥]\s*\d+|[\d,]+\s*元', body))
        ad_hits += price_matches * 4

        density = ad_hits / max(body_len, 1)
        return min(density, 1.0)

    async def analyze(
        self,
        db: AsyncSession,
        company_id: int,
        product_id: Optional[int] = None,
        product_name: str = "",
        platform: str = "",
    ) -> AdRatioDecision:
        """
        分析该公司最近的 mixed 模式文章广告密度，返回决策。

        参数：
          db           : 数据库会话
          company_id   : 公司 ID
          product_id   : 可选，过滤只看同一产品的历史文章
          product_name : 用于规则打分（产品名识别）
          platform     : 若指定，只看该平台的历史文章（可选）
        """
        from backend.models.models import Content

        # ── 1. 查询近期 mixed 模式文章 ──
        query = select(Content).where(
            and_(
                Content.company_id == company_id,
                Content.content_mode == "mixed",
                Content.status.in_(["draft", "approved", "published"]),
            )
        ).order_by(Content.created_at.desc()).limit(LOOKBACK_COUNT)

        if platform:
            query = query.where(Content.platform == platform)

        result = await db.execute(query)
        recent_articles: List[Content] = result.scalars().all()

        sample_count = len(recent_articles)

        # ── 2. 样本不足 → 宽松决策（允许引入产品） ──
        if sample_count < MIN_SAMPLE:
            logger.info(
                f"[AdRatio] company_id={company_id} 样本不足 ({sample_count}<{MIN_SAMPLE})，"
                f"默认允许引入产品"
            )
            return AdRatioDecision(
                include_product=True,
                ad_ratio=0.0,
                sample_count=sample_count,
                reason=f"历史样本不足({sample_count}篇)，默认允许引入产品",
                product_articles=0,
                suppress_product_name=False,
            )

        # ── 3. 逐篇打分 ──
        product_article_count = 0
        density_scores = []

        for article in recent_articles:
            body = article.body or ""
            # 尝试从 generation_params 获取产品名（增强准确性）
            gp = article.generation_params or {}
            art_product_name = (
                product_name
                or gp.get("product_name", "")
                or (article.product.name if article.product else "")
            )

            density = self._score_single_article(body, art_product_name)
            density_scores.append(density)

            if density >= AD_DENSITY_THRESHOLD:
                product_article_count += 1

        ad_ratio = product_article_count / sample_count
        avg_density = sum(density_scores) / len(density_scores)

        logger.info(
            f"[AdRatio] company_id={company_id} platform={platform or 'ALL'} "
            f"样本={sample_count}篇, 含产品={product_article_count}篇, "
            f"广告占比={ad_ratio:.0%}, 平均密度={avg_density:.3f}"
        )

        # ── 4. 决策 ──
        if ad_ratio >= AD_RATIO_HIGH:
            # 广告太多 → 本篇纯公司，彻底不引入产品
            return AdRatioDecision(
                include_product=False,
                ad_ratio=ad_ratio,
                sample_count=sample_count,
                reason=(
                    f"近{sample_count}篇中有{product_article_count}篇含产品推销"
                    f"({ad_ratio:.0%}≥{AD_RATIO_HIGH:.0%})，本篇采用纯公司内容"
                ),
                product_articles=product_article_count,
                suppress_product_name=True,
            )
        elif ad_ratio >= AD_RATIO_LOW:
            # 中间区间 → 允许引入但压低产品名提及频率
            return AdRatioDecision(
                include_product=True,
                ad_ratio=ad_ratio,
                sample_count=sample_count,
                reason=(
                    f"近{sample_count}篇中有{product_article_count}篇含产品推销"
                    f"({ad_ratio:.0%})，本篇可引入产品但需控制提及次数"
                ),
                product_articles=product_article_count,
                suppress_product_name=True,  # 提及但不强调
            )
        else:
            # 广告稀少 → 正常混合，可以自然引入产品
            return AdRatioDecision(
                include_product=True,
                ad_ratio=ad_ratio,
                sample_count=sample_count,
                reason=(
                    f"近{sample_count}篇中仅{product_article_count}篇含产品推销"
                    f"({ad_ratio:.0%}<{AD_RATIO_LOW:.0%})，本篇可正常引入产品"
                ),
                product_articles=product_article_count,
                suppress_product_name=False,
            )


# 全局单例
ad_ratio_analyzer = AdRatioAnalyzer()
