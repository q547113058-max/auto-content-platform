"""
今日头条发布器 — Playwright 方案
"""
from typing import Dict, Any
from loguru import logger
from backend.services.publisher_base import PlatformPublisher


class ToutiaoPlaywrightPublisher(PlatformPublisher):
    platform_name = "toutiao"

    async def publish(self, context, content: Dict[str, Any]) -> Dict[str, Any]:
        page = None
        try:
            page = await context.new_page()

            logger.info("[Toutiao] 进入头条号后台...")
            await page.goto(
                "https://mp.toutiao.com/profile_v4/graphic/publish",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)

            # 填写标题
            title = content.get("title", "")
            if title:
                title_input = page.locator('[placeholder*="标题"]')
                await title_input.fill(title)
                await page.wait_for_timeout(500)

            # 填写正文
            body = content.get("body", "")
            if body:
                editor = page.locator('[class*="editor"]')
                await editor.fill(body)
                await page.wait_for_timeout(1000)

            # 发布
            logger.info("[Toutiao] 点击发布...")
            publish_btn = page.locator('button:has-text("发布")')
            await publish_btn.click()
            await page.wait_for_timeout(5000)

            return {"success": True, "content_id": page.url}

        except Exception as e:
            logger.error(f"[Toutiao] 发布异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if page:
                await page.close()
