"""
微博发布器 — Playwright 方案（OAuth API 作为降级）
"""
from typing import Dict, Any
from loguru import logger
from backend.services.publisher_base import PlatformPublisher


class WeiboPlaywrightPublisher(PlatformPublisher):
    platform_name = "weibo"

    async def publish(self, context, content: Dict[str, Any]) -> Dict[str, Any]:
        page = None
        try:
            page = await context.new_page()

            logger.info("[Weibo] 进入发布页...")
            await page.goto(
                "https://weibo.com",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)

            # 微博发布框
            body = content.get("body", "")
            tags = " ".join([f"#{t}" for t in content.get("tags", [])])
            full_text = f"{body}\n\n{tags}"

            # 定位发布框
            textarea = page.locator('textarea[class*="Content"]')
            await textarea.fill(full_text)
            await page.wait_for_timeout(500)

            # 如果有图片
            images = content.get("image_paths", [])
            if images:
                file_input = page.locator('input[type="file"]')
                await file_input.set_input_files(images)
                await page.wait_for_timeout(3000)

            # 点击发布
            logger.info("[Weibo] 点击发布...")
            submit_btn = page.locator('a[action-type="submit"]')
            await submit_btn.click()
            await page.wait_for_timeout(5000)

            return {"success": True, "content_id": page.url}

        except Exception as e:
            logger.error(f"[Weibo] 发布异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if page:
                await page.close()
