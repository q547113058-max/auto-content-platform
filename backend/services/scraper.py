"""
数据抓取服务 — Playwright 多平台真实 DOM 数据提取
支持：小红书/知乎/微博/头条/抖音/B站/微信公众号（API）
"""
import re
import json
from typing import Dict, Any, Optional, List
from loguru import logger
from backend.services.session_manager import session_manager
from backend.models.models import PublishRecord


def _parse_number(text: str) -> int:
    """从文本中提取数字，支持 '1.2万'/'12.3k' 等格式"""
    if not text:
        return 0
    text = str(text).strip().lower().replace(",", "").replace(" ", "")
    # 万
    m = re.match(r'([\d.]+)万', text)
    if m:
        return int(float(m.group(1)) * 10000)
    # k
    m = re.match(r'([\d.]+)k', text)
    if m:
        return int(float(m.group(1)) * 1000)
    # 纯数字
    m = re.match(r'(\d+)', text)
    if m:
        return int(m.group(1))
    return 0


class DataScraper:
    """数据抓取器 — 多平台 DOM 提取 + API 方案"""

    # ==================== 平台选择器配置 ====================
    # 每个平台提供多组备选选择器（按优先级排列），以及正则 fallback
    PLATFORM_CONFIGS = {
        "xiaohongshu": {
            "url_template": "https://creator.xiaohongshu.com/publish/note/{content_id}/data",
            "data_page": True,  # 创作者数据中心页面
            "selectors": {
                "views": [
                    "[class*='dataCard'] [class*='num']",
                    "[class*='statistic'] [class*='value']",
                    ".note-data__views .num",
                    ".views-count",
                    "[data-testid='views']",
                ],
                "likes": [
                    "[class*='dataCard']:nth-child(2) [class*='num']",
                    "[class*='statistic'] [class*='like'] [class*='value']",
                    ".note-data__likes .num",
                    ".likes-count",
                ],
                "comments": [
                    "[class*='dataCard']:nth-child(3) [class*='num']",
                    "[class*='comment'] [class*='value']",
                    ".note-data__comments .num",
                    ".comments-count",
                ],
                "shares": [
                    "[class*='dataCard']:nth-child(4) [class*='num']",
                    "[class*='share'] [class*='value']",
                    ".note-data__shares .num",
                    ".shares-count",
                ],
                "collects": [
                    "[class*='dataCard']:nth-child(5) [class*='num']",
                    "[class*='collect'] [class*='value']",
                    ".note-data__collects .num",
                    ".collects-count",
                ],
            },
            "regex_patterns": {
                "views": r'(?:阅读|浏览|观看)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:赞|点赞|喜欢)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(?:评论|回复)[^\d]*(\d[\d,.]*万?)',
                "shares": r'(?:分享|转发)[^\d]*(\d[\d,.]*万?)',
                "collects": r'(?:收藏)[^\d]*(\d[\d,.]*万?)',
            }
        },
        "zhihu": {
            "url_template": "https://zhuanlan.zhihu.com/p/{content_id}",
            "data_page": False,
            "selectors": {
                "views": [
                    "[class*='ContentItem'] [class*='views']",
                    "[class*='ArticleItem'] [class*='views']",
                    ".ContentItem-actions [class*='views']",
                ],
                "likes": [
                    "[class*='ContentItem'] button[class*='VoteButton']",
                    "[class*='ArticleItem'] [class*='VoteButton']",
                    "button[aria-label*='赞同']",
                    ".VoteButton--up",
                ],
                "comments": [
                    "[class*='ContentItem'] button[class*='comments']",
                    "[class*='ArticleItem'] [class*='CommentButton']",
                    "button[aria-label*='评论']",
                ],
            },
            "regex_patterns": {
                "views": r'(?:阅读|浏览)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:赞同|赞)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(\d+)\s*(?:条评论|评论)',
            }
        },
        "weibo": {
            "url_template": "https://weibo.com/{content_id}",
            "data_page": False,
            "selectors": {
                "views": [
                    ".woo-box-flex .woo-box-item-flex:nth-child(1) span:last-child",
                    "[class*='toolbar'] [class*='item']:nth-child(1) span",
                ],
                "likes": [
                    ".woo-box-flex .woo-box-item-flex:nth-child(4) span:last-child",
                    "[class*='toolbar'] [class*='item']:nth-child(4) span",
                ],
                "comments": [
                    ".woo-box-flex .woo-box-item-flex:nth-child(2) span:last-child",
                    "[class*='toolbar'] [class*='item']:nth-child(2) span",
                ],
                "shares": [
                    ".woo-box-flex .woo-box-item-flex:nth-child(3) span:last-child",
                    "[class*='toolbar'] [class*='item']:nth-child(3) span",
                ],
            },
            "regex_patterns": {
                "views": r'(?:阅读|播放)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:赞)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(?:评论)[^\d]*(\d[\d,.]*万?)',
                "shares": r'(?:转发)[^\d]*(\d[\d,.]*万?)',
            }
        },
        "toutiao": {
            "url_template": "https://mp.toutiao.com/profile_v4/graphic/publish/articles",
            "data_page": True,
            "selectors": {
                "views": [
                    "[class*='statistics'] [class*='read'] span",
                    "[class*='data-row'] [class*='views']",
                ],
                "likes": [
                    "[class*='statistics'] [class*='like'] span",
                ],
                "comments": [
                    "[class*='statistics'] [class*='comment'] span",
                ],
                "shares": [
                    "[class*='statistics'] [class*='share'] span",
                ],
            },
            "regex_patterns": {
                "views": r'(?:阅读|展现)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:点赞)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(?:评论)[^\d]*(\d[\d,.]*万?)',
                "shares": r'(?:分享|转发)[^\d]*(\d[\d,.]*万?)',
            }
        },
        "douyin": {
            "url_template": "https://creator.douyin.com/creator-micro/content/manage",
            "data_page": True,
            "selectors": {
                "views": [
                    "[class*='data-item'] [class*='views'] span",
                    "[class*='statistic'] [class*='play']",
                    "[class*='video-data'] [class*='views']",
                ],
                "likes": [
                    "[class*='data-item'] [class*='like'] span",
                    "[class*='statistic'] [class*='like']",
                    "[class*='video-data'] [class*='digg']",
                ],
                "comments": [
                    "[class*='data-item'] [class*='comment'] span",
                    "[class*='statistic'] [class*='comment']",
                    "[class*='video-data'] [class*='comment']",
                ],
                "shares": [
                    "[class*='data-item'] [class*='share'] span",
                    "[class*='statistic'] [class*='share']",
                    "[class*='video-data'] [class*='share']",
                ],
                "collects": [
                    "[class*='data-item'] [class*='collect'] span",
                    "[class*='statistic'] [class*='collect']",
                    "[class*='video-data'] [class*='collect']",
                ],
            },
            "regex_patterns": {
                "views": r'(?:播放|观看)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:点赞|喜欢)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(?:评论)[^\d]*(\d[\d,.]*万?)',
                "shares": r'(?:分享|转发)[^\d]*(\d[\d,.]*万?)',
                "collects": r'(?:收藏)[^\d]*(\d[\d,.]*万?)',
            }
        },
        "bilibili": {
            "url_template": "https://member.bilibili.com/platform/upload/video/data-archive",
            "data_page": True,
            "selectors": {
                "views": [
                    "[class*='data'] [class*='play'] span",
                    "[class*='video-data'] [class*='views']",
                ],
                "likes": [
                    "[class*='data'] [class*='like'] span",
                    "[class*='video-data'] [class*='likes']",
                ],
                "comments": [
                    "[class*='data'] [class*='comment'] span",
                    "[class*='video-data'] [class*='comments']",
                ],
                "shares": [
                    "[class*='data'] [class*='share'] span",
                    "[class*='video-data'] [class*='shares']",
                ],
                "collects": [
                    "[class*='data'] [class*='coin'] span",
                    "[class*='video-data'] [class*='coins']",
                ],
            },
            "regex_patterns": {
                "views": r'(?:播放)[^\d]*(\d[\d,.]*万?)',
                "likes": r'(?:点赞)[^\d]*(\d[\d,.]*万?)',
                "comments": r'(?:弹幕|评论)[^\d]*(\d[\d,.]*万?)',
                "shares": r'(?:分享)[^\d]*(\d[\d,.]*万?)',
                "collects": r'(?:硬币|收藏)[^\d]*(\d[\d,.]*万?)',
            }
        },
        "wechat": {
            "url_template": "https://api.weixin.qq.com/datacube/getarticletotal",
            "method": "api",
        },
    }

    # 通用数字匹配正则（最终 fallback）
    FALLBACK_PATTERNS = [
        # "阅读 1234" / "1.2万 views" / "赞 567"
        r'(?:阅读|浏览|播放|观看|展现)[^\d]*(\d[\d,.]*[万k]?)',
        r'(?:赞|点赞|喜欢|赞同)[^\d]*(\d[\d,.]*[万k]?)',
        r'(?:评论|回复|弹幕)[^\d]*(\d[\d,.]*[万k]?)',
        r'(?:分享|转发)[^\d]*(\d[\d,.]*[万k]?)',
        r'(?:收藏|硬币)[^\d]*(\d[\d,.]*[万k]?)',
    ]

    async def _extract_metric(self, page, selectors: List[str], metric_name: str) -> int:
        """用多组 CSS 选择器尝试提取单个指标，逐个 fallback"""
        for sel in selectors:
            if not sel:
                continue
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    text = (await el.inner_text()).strip()
                    val = _parse_number(text)
                    if val > 0:
                        logger.debug(f"  [{metric_name}] selector '{sel}' -> {val} (text: '{text}')")
                        return val
            except Exception:
                continue
        return 0

    async def _regex_extract(self, text: str, patterns: Dict[str, str]) -> Dict[str, int]:
        """正则表达式兜底提取"""
        result = {}
        for metric_name, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                val = _parse_number(matches[0])
                if val > 0:
                    result[metric_name] = val
        return result

    async def _extract_from_page_text(self, page, platform_config: dict) -> Dict[str, int]:
        """从页面文本内容中按正则提取所有指标"""
        try:
            body_text = await page.evaluate("() => document.body.innerText")
        except Exception:
            body_text = ""

        patterns = platform_config.get("regex_patterns", {})
        regex_result = await self._regex_extract(body_text, patterns)

        # 如果正则也没结果，用通用 fallback
        if not regex_result:
            # 尝试从所有可见文本中提取数字
            fallback_result = {}
            text_elements = body_text[:5000]  # 取前 5000 字符
            for pattern in self.FALLBACK_PATTERNS:
                m = re.search(pattern, text_elements, re.IGNORECASE)
                if m:
                    val = _parse_number(m.group(1))
                    if val > 0:
                        if '阅读|浏览|播放|观看|展现' in pattern:
                            key = 'views'
                        elif '赞' in pattern:
                            key = 'likes'
                        elif '评论|回复|弹幕' in pattern:
                            key = 'comments'
                        elif '分享|转发' in pattern:
                            key = 'shares'
                        elif '收藏|硬币' in pattern:
                            key = 'collects'
                        else:
                            continue
                        if key not in fallback_result:
                            fallback_result[key] = val
            regex_result = fallback_result

        return regex_result

    async def scrape_single(self, record: PublishRecord) -> Optional[Dict[str, Any]]:
        """
        抓取单篇内容数据 — 完整流程：
        1. 用 CSS 选择器提取
        2. 用正则从页面文本提取
        3. 返回结构化数据
        """
        platform = record.platform
        content_id = record.external_content_id

        if not content_id:
            logger.warning(f"[{platform}] record {record.id} 无 external_content_id，跳过")
            return None

        config = self.PLATFORM_CONFIGS.get(platform)
        if not config:
            logger.warning(f"[{platform}] 无抓取配置，跳过")
            return None

        try:
            # 微信公众号走 API
            if config.get("method") == "api":
                return await self._scrape_wechat_api(record)

            # 其他平台走 Playwright
            context = await session_manager.get_context(platform, str(record.account_id))
            if not context:
                logger.warning(f"[{platform}] 无有效会话，跳过抓取 record_id={record.id}")
                return None

            page = await context.new_page()
            url = config["url_template"].replace("{content_id}", content_id)
            logger.info(f"[{platform}] 抓取数据: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # 等待数据加载（数据页面通常有异步请求）
            await page.wait_for_timeout(4000)

            # 对于数据页面，尝试等待数字出现
            if config.get("data_page"):
                try:
                    await page.wait_for_selector("[class*='num'], [class*='value'], [class*='count']", timeout=5000)
                except Exception:
                    logger.debug(f"[{platform}] 未检测到典型数据元素，继续正则提取")

            # Step 1: CSS 选择器提取
            selectors = config.get("selectors", {})
            data = {}
            for metric_name in ["views", "likes", "comments", "shares", "collects"]:
                sel_list = selectors.get(metric_name, [])
                if sel_list:
                    data[metric_name] = await self._extract_metric(page, sel_list, metric_name)
                else:
                    data[metric_name] = 0

            # Step 2: 正则兜底（选择器没提取到的指标）
            if any(data.get(k, 0) == 0 for k in ["views", "likes"]):
                regex_data = await self._extract_from_page_text(page, config)
                for k, v in regex_data.items():
                    if k in data and data[k] == 0 and v > 0:
                        data[k] = v
                        logger.debug(f"  [{k}] regex fallback -> {v}")

            # 收集原始数据用于调试
            raw_snapshot = {
                "url": page.url,
                "title": await page.title(),
                "body_preview": (await page.evaluate("() => document.body.innerText"))[:2000],
            }

            await page.close()

            result = {
                "views": data.get("views", 0),
                "likes": data.get("likes", 0),
                "comments": data.get("comments", 0),
                "shares": data.get("shares", 0),
                "collects": data.get("collects", 0),
                "followers_delta": 0,
                "raw_data": raw_snapshot,
            }

            logger.info(
                f"[{platform}] 抓取完成: views={result['views']}, likes={result['likes']}, "
                f"comments={result['comments']}, shares={result['shares']}"
            )
            return result

        except Exception as e:
            logger.error(f"[{platform}] 抓取失败 record_id={record.id}: {e}")
            return None

    async def _scrape_wechat_api(self, record: PublishRecord) -> Dict[str, Any]:
        """微信公众号数据采集 — 通过微信数据统计 API"""
        import httpx
        from datetime import datetime, timedelta
        from backend.models.database import AsyncSessionLocal
        from backend.models.models import PlatformAccount
        from backend.services.session_manager import wechat_token_manager
        from sqlalchemy import select

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PlatformAccount).where(PlatformAccount.id == record.account_id)
                )
                account = result.scalar_one_or_none()
                if not account or not account.auth_config:
                    logger.warning(f"[wechat] 账号 {record.account_id} 配置缺失")
                    return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "collects": 0}

                auth = account.auth_config
                appid = auth.get("appid", "")
                appsecret = auth.get("appsecret", "")
                token = await wechat_token_manager.get_access_token(appid, appsecret)

            if not token:
                logger.warning("[wechat] 无法获取 access_token")
                return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "collects": 0}

            # 使用最近 7 天的数据范围
            today = datetime.now()
            begin = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")

            async with httpx.AsyncClient(timeout=15) as client:
                # 图文总阅读量
                url = f"https://api.weixin.qq.com/datacube/getarticletotal?access_token={token}"
                resp = await client.post(url, json={"begin_date": begin, "end_date": end})
                resp_data = resp.json()

                views = 0
                likes = 0
                shares = 0
                if "list" in resp_data:
                    # 匹配 external_content_id（msgid）
                    for item in resp_data["list"]:
                        if str(item.get("msgid", "")) == record.external_content_id:
                            views = item.get("int_page_read_count", 0)
                            likes = item.get("ori_page_read_count", 0)
                            shares = item.get("share_count", 0) + item.get("add_to_fav_count", 0)
                            break
                    else:
                        # 没匹配到特定文章，取第一条
                        views = resp_data["list"][0].get("int_page_read_count", 0)

                logger.info(f"[wechat] API 抓取: views={views}, likes={likes}, shares={shares}")
                return {
                    "views": views,
                    "likes": likes,
                    "comments": 0,  # 微信统计 API 不直接返回评论数
                    "shares": shares,
                    "collects": 0,
                    "raw_data": {"api_response": resp_data},
                }

        except Exception as e:
            logger.error(f"[wechat] API 抓取失败: {e}")
            return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "collects": 0}

    async def scrape_all_pending(self, db_session) -> Dict[str, Any]:
        """
        定时批量采集 — 查询 90 天内成功发布的内容，逐个抓取最新数据
        """
        from sqlalchemy import select, and_
        from datetime import datetime, timedelta
        from backend.utils.timezone_utils import now_shanghai

        cutoff = now_shanghai() - timedelta(days=90)
        query = (
            select(PublishRecord)
            .where(
                and_(
                    PublishRecord.status == "success",
                    PublishRecord.publish_time.isnot(None),
                    PublishRecord.publish_time > cutoff,
                )
            )
        )
        result = await db_session.execute(query)
        records = list(result.scalars().all())

        logger.info(f"[数据抓取] 开始批量采集，共 {len(records)} 篇待处理")

        success_count = 0
        fail_count = 0
        platform_stats: Dict[str, Dict[str, int]] = {}

        from backend.models.models import ContentMetric

        for record in records:
            data = await self.scrape_single(record)
            if data and data.get("views", 0) > 0:
                metric = ContentMetric(
                    publish_record_id=record.id,
                    views=data.get("views", 0),
                    likes=data.get("likes", 0),
                    comments=data.get("comments", 0),
                    shares=data.get("shares", 0),
                    collects=data.get("collects", 0),
                    followers_delta=data.get("followers_delta", 0),
                    raw_data=data.get("raw_data", {}),
                )
                db_session.add(metric)
                success_count += 1

                platform = record.platform
                if platform not in platform_stats:
                    platform_stats[platform] = {"scraped": 0, "total_views": 0}
                platform_stats[platform]["scraped"] += 1
                platform_stats[platform]["total_views"] += data.get("views", 0)
            else:
                fail_count += 1

        await db_session.commit()
        logger.info(
            f"[数据抓取] 完成: {success_count}/{len(records)} 成功, {fail_count} 失败"
        )
        return {
            "total": len(records),
            "scraped": success_count,
            "failed": fail_count,
            "platform_stats": platform_stats,
        }

    async def scrape_product_all(self, product_id: int, db_session) -> Dict[str, Any]:
        """
        采集指定产品关联的所有已发布内容数据
        """
        from sqlalchemy import select, and_
        from backend.models.models import Content

        # 找到产品关联的所有内容
        content_query = select(Content.id).where(Content.product_id == product_id)
        content_result = await db_session.execute(content_query)
        content_ids = [row[0] for row in content_result.all()]

        if not content_ids:
            return {"total": 0, "scraped": 0, "message": "无关联内容"}

        # 找到所有已发布的记录
        publish_query = select(PublishRecord).where(
            and_(
                PublishRecord.content_id.in_(content_ids),
                PublishRecord.status == "success",
            )
        )
        pub_result = await db_session.execute(publish_query)
        records = list(pub_result.scalars().all())

        from backend.models.models import ContentMetric

        scraped = 0
        for record in records:
            data = await self.scrape_single(record)
            if data and data.get("views", 0) > 0:
                metric = ContentMetric(
                    publish_record_id=record.id,
                    views=data.get("views", 0),
                    likes=data.get("likes", 0),
                    comments=data.get("comments", 0),
                    shares=data.get("shares", 0),
                    collects=data.get("collects", 0),
                    followers_delta=data.get("followers_delta", 0),
                    raw_data=data.get("raw_data", {}),
                )
                db_session.add(metric)
                scraped += 1

        await db_session.commit()
        return {"total": len(records), "scraped": scraped}


scraper = DataScraper()
