"""
发布引擎基类 — 统一发布接口
每个平台实现自己的 publish 方法
"""
from typing import Dict, Any
from abc import ABC, abstractmethod
from loguru import logger
from backend.config import settings
from backend.services.session_manager import session_manager


class PlatformPublisher(ABC):
    """平台发布器抽象基类"""

    platform_name: str = "unknown"

    @abstractmethod
    async def publish(
        self, context_or_token, content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行发布
        返回: {"success": bool, "content_id": str, "error": str}
        """
        pass


class Publisher:
    """统一发布引擎 — 调度各平台发布器"""

    STRATEGIES: Dict[str, PlatformPublisher] = {}

    @classmethod
    def register(cls, platform: str, publisher: PlatformPublisher):
        cls.STRATEGIES[platform] = publisher

    async def publish(
        self,
        platform: str,
        account_id: str,
        content: Dict[str, Any],
        strategy: str = None,
    ) -> Dict[str, Any]:
        """统一发布入口"""
        if platform not in self.STRATEGIES:
            return {"success": False, "error": f"不支持的平台: {platform}"}

        # 1. 频率检查
        can_publish, reason = await self._check_rate_limit(platform, account_id)
        if not can_publish:
            return {"success": False, "error": f"频率限制: {reason}"}

        # 2. 获取会话
        if platform == "wechat":
            from backend.services.session_manager import wechat_token_manager
            from backend.models.database import AsyncSessionLocal
            from backend.models.models import PlatformAccount
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PlatformAccount).where(PlatformAccount.id == int(account_id))
                )
                account = result.scalar_one_or_none()
                if not account:
                    return {"success": False, "error": "账号不存在"}

                auth = account.auth_config or {}
                token = await wechat_token_manager.get_access_token(
                    auth.get("appid", ""),
                    auth.get("appsecret", ""),
                )
                context_or_token = token
        else:
            context_or_token = await session_manager.get_context(
                platform, account_id
            )
            if context_or_token is None:
                return {"success": False, "error": f"{platform} 会话已过期，需重新登录"}

        # 3. 执行发布
        publisher = self.STRATEGIES[platform]
        try:
            result = await publisher.publish(context_or_token, content)
            logger.info(f"[{platform}] 发布结果: {result}")
            return result
        except Exception as e:
            logger.error(f"[{platform}] 发布异常: {e}")
            return {"success": False, "error": str(e)}

    async def _check_rate_limit(self, platform: str, account_id: str) -> tuple:
        """Redis 频率控制"""
        import time
        from backend.config import settings

        limits = settings.RATE_LIMITS.get(platform, {})
        max_per_day = limits.get("max_per_day", 5)
        min_interval = limits.get("min_interval_minutes", 30)

        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)

            day_key = f"rate:{platform}:{account_id}:day"
            interval_key = f"rate:{platform}:{account_id}:last"

            # 日配额检查
            day_count = await r.get(day_key)
            if day_count and int(day_count) >= max_per_day:
                return False, f"已达日上限 {max_per_day} 次"

            # 间隔检查
            last_time = await r.get(interval_key)
            if last_time:
                elapsed = time.time() - float(last_time)
                if elapsed < min_interval * 60:
                    wait = int(min_interval * 60 - elapsed)
                    return False, f"距上次发布不足 {min_interval} 分钟，还需等待 {wait} 秒"

            # 更新计数
            pipe = r.pipeline()
            pipe.incr(day_key)
            pipe.expire(day_key, 86400)  # 24小时
            pipe.set(interval_key, time.time())
            await pipe.execute()

            return True, ""
        except Exception as e:
            logger.warning(f"Redis 频率检查失败，跳过限制: {e}")
            return True, ""  # Redis 不可用时不阻止发布


# 延迟注册各平台发布器
def _register_publishers():
    from backend.services.publisher.wechat_api import WechatAPIPublisher
    from backend.services.publisher.xhs_playwright import XhsPlaywrightPublisher
    from backend.services.publisher.zhihu_playwright import ZhihuPlaywrightPublisher
    from backend.services.publisher.weibo_playwright import WeiboPlaywrightPublisher
    from backend.services.publisher.toutiao_playwright import ToutiaoPlaywrightPublisher
    from backend.services.publisher.douyin_playwright import DouyinPlaywrightPublisher

    Publisher.register("wechat", WechatAPIPublisher())
    Publisher.register("xiaohongshu", XhsPlaywrightPublisher())
    Publisher.register("zhihu", ZhihuPlaywrightPublisher())
    Publisher.register("weibo", WeiboPlaywrightPublisher())
    Publisher.register("toutiao", ToutiaoPlaywrightPublisher())
    Publisher.register("douyin", DouyinPlaywrightPublisher())


_register_publishers()
