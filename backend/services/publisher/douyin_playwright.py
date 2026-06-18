"""
抖音图文发布器 — Playwright 方案
"""
from typing import Dict, Any
from loguru import logger
from backend.services.publisher_base import PlatformPublisher


class DouyinPlaywrightPublisher(PlatformPublisher):
    platform_name = "douyin"

    async def publish(self, context, content: Dict[str, Any]) -> Dict[str, Any]:
        page = None
        try:
            page = await context.new_page()

            logger.info("[Douyin] 进入抖音创作服务平台...")
            await page.goto(
                "https://creator.douyin.com/creator-micro/content/upload",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)

            # 切换到图文模式
            try:
                image_btn = page.locator('text=图文')
                await image_btn.click()
                await page.wait_for_timeout(1000)
            except Exception:
                pass

            # 上传图片
            images = content.get("image_paths", [])
            if images:
                logger.info(f"[Douyin] 上传 {len(images)} 张图片...")
                file_input = page.locator('input[type="file"]')
                await file_input.set_input_files(images)
                await page.wait_for_timeout(5000)

            # 填写描述文字
            title = content.get("title", "")
            body = content.get("body", "")
            full_text = f"{title}\n{body}"[:500]  # 抖音限制
            textarea = page.locator('div[contenteditable="true"]')
            await textarea.fill(full_text)
            await page.wait_for_timeout(500)

            # 发布
            logger.info("[Douyin] 点击发布...")
            publish_btn = page.locator('button:has-text("发布")')
            await publish_btn.click()
            await page.wait_for_timeout(5000)

            return {"success": True, "content_id": page.url}

        except Exception as e:
            logger.error(f"[Douyin] 发布异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if page:
                await page.close()
