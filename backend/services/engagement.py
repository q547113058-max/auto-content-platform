"""
互动引擎 — 评论区自动回复
支持平台: 知乎、今日头条（基于 Playwright 自动化）
"""
from __future__ import annotations
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from loguru import logger

from backend.config import settings
from backend.models.database import AsyncSessionLocal
from backend.models.models import CommentReply, PublishRecord, PlatformAccount, Content
from sqlalchemy import select, and_

# Playwright 可选导入
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# AI 生成器可选导入
try:
    from backend.services.ai_generator import AIGenerator
    AI_AVAILABLE = True
except Exception:
    AI_AVAILABLE = False


# ======================= 平台评论页配置 =======================
ENGAGEMENT_CONFIGS = {
    "zhihu": {
        "name": "知乎",
        "creator_home": "https://www.zhihu.com/creator",
        "content_list_url": "https://www.zhihu.com/creator/content/answers",
        "comment_section_selector": ".Comments-container, [class*='Comments']",
        "comment_item_selector": ".CommentItem, [class*='CommentItem'], [itemprop='comment']",
        "comment_text_selector": ".CommentItem-content .RichText, [class*='CommentContent'], [class*='content']",
        "commenter_selector": ".AuthorInfo-name .UserLink-link, [class*='AuthorInfo'] [class*='name']",
        "comment_id_attr": "data-id",
        "reply_button_selector": "button[class*='Reply'], [class*='replyButton'], [class*='reply']",
        "reply_textarea_selector": "textarea[class*='Input'], .public-DraftEditor-content, [contenteditable='true']",
        "reply_submit_selector": "button[class*='submit'], button[class*='Submit'], button[class*='primary']",
        "load_more_selector": "button[class*='LoadMore'], [class*='loadMore'], [class*='Pagination'] button",
        "comment_section_wait": 3000,
        "reply_wait": 1500,
    },
    "toutiao": {
        "name": "今日头条",
        "creator_home": "https://mp.toutiao.com/",
        "content_list_url": "https://mp.toutiao.com/profile_v4/graphic/articles",
        "comment_section_selector": ".comment-list, [class*='comment-list'], [class*='commentList']",
        "comment_item_selector": ".comment-item, [class*='commentItem'], [class*='comment-item']",
        "comment_text_selector": ".comment-content, [class*='commentContent'], [class*='comment-content'] .text",
        "commenter_selector": ".comment-user-name, [class*='commentUser'], [class*='userName'], [class*='nickname']",
        "comment_id_attr": "data-comment-id",
        "reply_button_selector": ".reply-btn, [class*='replyBtn'], [class*='reply-btn'], [class*='reply'] span",
        "reply_textarea_selector": "textarea.reply-input, [class*='replyInput'], [class*='reply-input'] textarea",
        "reply_submit_selector": ".reply-submit, button[class*='replySubmit'], button[class*='submitReply']",
        "load_more_selector": ".load-more, [class*='loadMore'], .pagination-next",
        "comment_section_wait": 3000,
        "reply_wait": 2000,
    },
}

# ======================= 回复策略提示词 =======================
REPLY_PROMPT_TEMPLATE = """你是品牌账号运营，需要回复用户评论。
回复要求：
- 语气自然、亲切，像真人而非机器人
- 针对评论内容做出具体回应，不要泛泛而谈
- 适当使用 emoji（控制在 1-2 个）
- 回复长度控制在 15-80 字
- 不要使用「亲」「宝」等过于电商化的称呼
- 如果评论是负面/质疑，保持专业和耐心解释

【发布的文章标题】{content_title}
【文章摘要】{content_summary}
【产品信息】{product_knowledge}
【用户评论】{comment_text}

请生成一条简洁的回复："""


class EngagementEngine:
    """评论互动引擎"""

    def __init__(self):
        self._ai_generator = None

    @property
    def ai(self):
        if self._ai_generator is None and AI_AVAILABLE:
            try:
                self._ai_generator = AIGenerator()
            except Exception as e:
                logger.warning(f"AI 生成器初始化失败: {e}")
        return self._ai_generator

    async def get_context(self, platform: str, account_id: int):
        """获取浏览器上下文（从 SessionManager 复用）"""
        from backend.services.session_manager import session_manager, PLAYWRIGHT_AVAILABLE as SM_PW

        if not SM_PW or not PLAYWRIGHT_AVAILABLE:
            return None, "Playwright 未安装"

        try:
            ctx = await session_manager.get_context(platform, account_id)
            return ctx, None
        except Exception as e:
            return None, str(e)

    # ---------- 评论抓取 ----------
    async def fetch_new_comments(
        self, page: Page, platform: str, account_id: int, limit: int = 20
    ) -> List[Dict]:
        """抓取未回复的新评论"""
        config = ENGAGEMENT_CONFIGS.get(platform)
        if not config:
            return []

        comments = []
        try:
            # 等待评论区加载
            await page.wait_for_selector(
                config["comment_section_selector"], timeout=10000
            )
            await asyncio.sleep(config["comment_section_wait"] / 1000)

            # 尝试加载更多评论
            for _ in range(3):
                try:
                    load_more = page.locator(config["load_more_selector"]).first
                    if await load_more.is_visible(timeout=2000):
                        await load_more.click()
                        await asyncio.sleep(1.5)
                except Exception:
                    break

            # 提取评论元素
            comment_elements = page.locator(config["comment_item_selector"])
            count = await comment_elements.count()

            for i in range(min(count, limit * 2)):  # 多抓一些，去重后筛选
                try:
                    el = comment_elements.nth(i)

                    # 获取评论ID
                    comment_id = await el.get_attribute(config["comment_id_attr"])
                    if not comment_id:
                        comment_id = await el.get_attribute("id")

                    # 获取评论文本
                    text_el = el.locator(config["comment_text_selector"]).first
                    comment_text = ""
                    try:
                        comment_text = (await text_el.inner_text()).strip()
                    except Exception:
                        comment_text = (await el.inner_text()).strip()[:200]

                    # 获取评论者昵称
                    commenter = ""
                    try:
                        commenter_el = el.locator(config["commenter_selector"]).first
                        commenter = (await commenter_el.inner_text()).strip()
                    except Exception:
                        pass

                    if comment_text and len(comment_text) >= 3:
                        comments.append({
                            "comment_id": comment_id or hashlib.md5(
                                (commenter + comment_text[:50]).encode()
                            ).hexdigest()[:12],
                            "commenter": commenter or "用户",
                            "comment_text": comment_text,
                        })

                    if len(comments) >= limit:
                        break

                except Exception as e:
                    logger.debug(f"提取评论 #{i} 失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"抓取 {platform} 评论失败: {e}")

        return comments

    async def filter_unreplied(self, platform: str, comments: List[Dict]) -> List[Dict]:
        """过滤已回复过的评论"""
        if not comments:
            return []

        comment_ids = [c["comment_id"] for c in comments]
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CommentReply.comment_id).where(
                    and_(
                        CommentReply.platform == platform,
                        CommentReply.comment_id.in_(comment_ids),
                    )
                )
            )
            replied_ids = {row[0] for row in result.all()}

        return [c for c in comments if c["comment_id"] not in replied_ids]

    # ---------- AI 回复生成 ----------
    async def generate_reply(
        self, comment: Dict, content_info: Dict
    ) -> Optional[str]:
        """使用 AI 生成回复"""
        if not self.ai:
            # 降级：使用模板回复
            return self._fallback_reply(comment["comment_text"])

        try:
            prompt = REPLY_PROMPT_TEMPLATE.format(
                content_title=content_info.get("title", ""),
                content_summary=content_info.get("summary", content_info.get("body", ""))[:200],
                product_knowledge=content_info.get("knowledge", "通用消费品"),
                comment_text=comment["comment_text"],
            )

            response = await self.ai.client.chat.completions.create(
                model=settings.AI_MODEL or "deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的品牌运营，擅长与用户互动。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=0.8,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"AI 生成回复失败，使用降级方案: {e}")
            return self._fallback_reply(comment["comment_text"])

    def _fallback_reply(self, comment_text: str) -> str:
        """AI 不可用时的降级模板回复"""
        text = comment_text[:20]
        replies = [
            f"感谢关注！关于「{text}」这个问题，我们后续会出详细内容 😊",
            f"谢谢你的评论～我们会持续分享更多干货 💪",
            "感谢支持！有什么想了解的可以留言告诉我们",
            "收到你的反馈了，非常宝贵的建议 👍",
        ]
        idx = hash(comment_text) % len(replies)
        return replies[idx]

    # ---------- 回复执行 ----------
    async def post_reply(
        self, page: Page, platform: str, comment: Dict, reply_text: str
    ) -> Tuple[bool, str]:
        """在评论区发布回复"""
        config = ENGAGEMENT_CONFIGS.get(platform)
        if not config:
            return False, "平台配置不存在"

        try:
            # 1. 找到该评论的回复按钮
            reply_btn = page.locator(config["reply_button_selector"]).first
            await reply_btn.click()
            await asyncio.sleep(0.8)

            # 2. 找到输入框并填入回复
            textarea = page.locator(config["reply_textarea_selector"]).first
            await textarea.wait_for(state="visible", timeout=5000)
            await textarea.click()
            await textarea.fill(reply_text)
            await asyncio.sleep(0.3)

            # 3. 提交回复
            submit = page.locator(config["reply_submit_selector"]).first
            await submit.click()
            await asyncio.sleep(config["reply_wait"] / 1000)

            return True, ""
        except Exception as e:
            return False, str(e)

    # ---------- 保存回复记录 ----------
    async def save_reply(
        self, platform: str, account_id: int, comment: Dict,
        reply_text: str, content_external_id: str = "",
        publish_record_id: int = None,
    ):
        """保存回复记录到数据库"""
        async with AsyncSessionLocal() as db:
            record = CommentReply(
                platform=platform,
                account_id=account_id,
                publish_record_id=publish_record_id,
                content_external_id=content_external_id,
                comment_id=comment["comment_id"],
                commenter_name=comment.get("commenter", ""),
                comment_text=comment["comment_text"],
                reply_text=reply_text,
                ai_generated=AI_AVAILABLE,
                status="success",
            )
            db.add(record)
            await db.commit()

    async def save_failed_reply(
        self, platform: str, account_id: int, comment: Dict,
        error: str, content_external_id: str = "",
    ):
        """保存失败记录"""
        async with AsyncSessionLocal() as db:
            record = CommentReply(
                platform=platform,
                account_id=account_id,
                content_external_id=content_external_id,
                comment_id=comment["comment_id"],
                commenter_name=comment.get("commenter", ""),
                comment_text=comment["comment_text"],
                reply_text="",
                status="failed",
                error_message=error,
            )
            db.add(record)
            await db.commit()

    # ---------- 主流程：单个平台的内容评论区遍历 ----------
    async def engage_single_content(
        self, page: Page, platform: str, account_id: int,
        publish_record: PublishRecord, content: Content,
        limit: int = 10,
    ) -> Dict:
        """对单篇已发布内容执行评论互动"""
        result = {
            "platform": platform,
            "content_id": content.id,
            "publish_record_id": publish_record.id,
            "external_id": publish_record.external_content_id or "",
            "comments_found": 0,
            "replied": 0,
            "failed": 0,
            "skipped": 0,
        }

        # 导航到内容评论区
        external_id = publish_record.external_content_id
        if not external_id:
            logger.info(f"内容 {content.id} 无 external_content_id，跳过")
            return result

        # 知乎导航到具体内容页
        if platform == "zhihu":
            target_url = f"https://www.zhihu.com/question/{external_id}/answer/" if external_id.isdigit() else f"https://zhuanlan.zhihu.com/p/{external_id}"
        elif platform == "toutiao":
            target_url = f"https://www.toutiao.com/item/{external_id}/"
        else:
            return result

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"导航到内容页失败: {e}")
            return result

        # 滚动到评论区
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
            await asyncio.sleep(1)
        except Exception:
            pass

        # 抓取新评论
        comments = await self.fetch_new_comments(page, platform, account_id, limit)
        if not comments:
            return result

        result["comments_found"] = len(comments)

        # 过滤已回复
        unreplied = await self.filter_unreplied(platform, comments)
        result["skipped"] = len(comments) - len(unreplied)

        # 获取内容信息用于 AI 生成上下文
        content_info = {
            "title": content.title or "",
            "body": content.body or "",
            "summary": (content.body or "")[:200],
            "knowledge": "",
        }

        # 逐个回复
        for comment in unreplied:
            try:
                reply_text = await self.generate_reply(comment, content_info)
                success, error = await self.post_reply(page, platform, comment, reply_text)

                if success:
                    await self.save_reply(
                        platform, account_id, comment, reply_text,
                        content_external_id=external_id,
                        publish_record_id=publish_record.id,
                    )
                    result["replied"] += 1
                else:
                    await self.save_failed_reply(
                        platform, account_id, comment, error,
                        content_external_id=external_id,
                    )
                    result["failed"] += 1

                # 回复间隔，避免频率过高
                await asyncio.sleep(3 + (hash(comment["comment_id"]) % 5))

            except Exception as e:
                logger.error(f"回复评论 {comment['comment_id']} 失败: {e}")
                await self.save_failed_reply(
                    platform, account_id, comment, str(e),
                    content_external_id=external_id,
                )
                result["failed"] += 1

        return result

    # ---------- 主入口：批量互动 ----------
    async def engage_platform(
        self, platform: str, account_id: int = None, product_id: int = None,
        limit_per_content: int = 10, max_contents: int = 5,
    ) -> Dict:
        """对指定平台执行批量评论互动"""
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright 未安装", "results": []}

        config = ENGAGEMENT_CONFIGS.get(platform)
        if not config:
            return {"error": f"不支持的平台: {platform}", "results": []}

        # 1. 获取账号
        async with AsyncSessionLocal() as db:
            if account_id:
                result = await db.execute(
                    select(PlatformAccount).where(
                        and_(
                            PlatformAccount.id == account_id,
                            PlatformAccount.platform == platform,
                            PlatformAccount.status == "active",
                        )
                    )
                )
                accounts = result.scalars().all()
            else:
                stmt = select(PlatformAccount).where(
                    and_(
                        PlatformAccount.platform == platform,
                        PlatformAccount.status == "active",
                    )
                )
                if product_id:
                    pass  # 账号与产品无直接关联，按平台取所有活跃账号
                result = await db.execute(stmt)
                accounts = result.scalars().all()

            if not accounts:
                return {"error": f"没有活跃的 {config['name']} 账号", "results": []}

            # 2. 获取已发布内容（有 external_content_id 的）
            results = []

            for account in accounts:
                # 获取该账号的已发布内容
                stmt = (
                    select(PublishRecord, Content)
                    .join(Content, PublishRecord.content_id == Content.id)
                    .where(
                        and_(
                            PublishRecord.account_id == account.id,
                            PublishRecord.platform == platform,
                            PublishRecord.status == "success",
                            PublishRecord.external_content_id.isnot(None),
                            PublishRecord.external_content_id != "",
                        )
                    )
                    .order_by(PublishRecord.publish_time.desc())
                    .limit(max_contents)
                )
                pub_result = await db.execute(stmt)
                pub_contents = pub_result.all()

                if not pub_contents:
                    continue

                # 3. 获取浏览器上下文
                ctx, error = await self.get_context(platform, account.id)
                if error:
                    results.append({
                        "account_id": account.id,
                        "account_name": account.account_name,
                        "error": error,
                    })
                    continue

                page = await ctx.new_page()

                try:
                    for pub_record, content in pub_contents:
                        res = await self.engage_single_content(
                            page, platform, account.id,
                            pub_record, content, limit_per_content,
                        )
                        res["account_name"] = account.account_name
                        results.append(res)
                finally:
                    await page.close()

        summary = {
            "platform": platform,
            "platform_name": config["name"],
            "total_replied": sum(r.get("replied", 0) for r in results),
            "total_failed": sum(r.get("failed", 0) for r in results),
            "total_skipped": sum(r.get("skipped", 0) for r in results),
            "total_found": sum(r.get("comments_found", 0) for r in results),
            "contents_processed": len(results),
            "results": results,
        }
        return summary

    async def get_stats(self, platform: str = None) -> Dict:
        """获取互动统计"""
        async with AsyncSessionLocal() as db:
            stmt = select(CommentReply)
            if platform:
                stmt = stmt.where(CommentReply.platform == platform)

            result = await db.execute(stmt)
            replies = result.scalars().all()

            total = len(replies)
            success = sum(1 for r in replies if r.status == "success")
            failed = sum(1 for r in replies if r.status == "failed")
            ai_count = sum(1 for r in replies if r.ai_generated)

            # 按平台分组
            by_platform = {}
            for r in replies:
                by_platform.setdefault(r.platform, {"total": 0, "success": 0, "failed": 0})
                by_platform[r.platform]["total"] += 1
                if r.status == "success":
                    by_platform[r.platform]["success"] += 1
                else:
                    by_platform[r.platform]["failed"] += 1

            return {
                "total": total,
                "success": success,
                "failed": failed,
                "ai_generated": ai_count,
                "by_platform": by_platform,
            }

    async def get_reply_history(
        self, platform: str = None, account_id: int = None,
        status: str = None, limit: int = 50, offset: int = 0,
    ) -> List[Dict]:
        """获取回复历史"""
        async with AsyncSessionLocal() as db:
            stmt = select(CommentReply).order_by(CommentReply.replied_at.desc())

            if platform:
                stmt = stmt.where(CommentReply.platform == platform)
            if account_id:
                stmt = stmt.where(CommentReply.account_id == account_id)
            if status:
                stmt = stmt.where(CommentReply.status == status)

            result = await db.execute(stmt.offset(offset).limit(limit))
            replies = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "platform": r.platform,
                    "account_id": r.account_id,
                    "commenter_name": r.commenter_name,
                    "comment_text": r.comment_text[:100],
                    "reply_text": r.reply_text[:100] if r.reply_text else "",
                    "ai_generated": r.ai_generated,
                    "status": r.status,
                    "replied_at": r.replied_at.isoformat() if r.replied_at else "",
                }
                for r in replies
            ]


# 全局单例
engagement_engine = EngagementEngine()
