"""
小红书发布器 — Playwright 方案
https://creator.xiaohongshu.com
"""
from typing import Dict, Any
from loguru import logger
from backend.services.publisher_base import PlatformPublisher


class XhsPlaywrightPublisher(PlatformPublisher):
    platform_name = "xiaohongshu"

    async def publish(
        self, context, content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        小红书图文发布流程：
        1. 进入创作者中心发布页
        2. 上传图片（竖图 3:4 最佳）
        3. 填写标题（20字以内）
        4. 填写正文
        5. 添加话题标签
        6. 点击发布
        """
        page = None
        try:
            page = await context.new_page()

            # 1. 进入发布页
            logger.info("[XHS] 进入发布页...")
            await page.goto(
                "https://creator.xiaohongshu.com/publish/publish",
                wait_until="networkidle",
                timeout=30000,
            )

            # 等待页面加载
            await page.wait_for_timeout(3000)

            # 2. 上传图片
            image_paths = content.get("image_paths", [])
            if image_paths:
                logger.info(f"[XHS] 上传 {len(image_paths)} 张图片...")
                file_input = page.locator('input[type="file"]')
                await file_input.set_input_files(image_paths)
                await page.wait_for_timeout(5000)  # 等待图片上传处理

            # 3. 填写标题
            title = content.get("title", "")
            if title:
                logger.info(f"[XHS] 填写标题: {title[:30]}...")
                # 小红书的标题输入框
                title_input = page.locator('[placeholder*="标题"]')
                await title_input.fill(title[:20])  # 限制20字
                await page.wait_for_timeout(500)

            # 4. 填写正文
            body = content.get("body", "")
            if body:
                logger.info(f"[XHS] 填写正文 ({len(body)} 字)...")
                body_box = page.locator('[placeholder*="正文"]') or page.locator('.ql-editor')
                await body_box.fill(body)
                await page.wait_for_timeout(1000)

            # 5. 添加标签
            tags = content.get("tags", [])
            if tags:
                logger.info(f"[XHS] 添加 {len(tags)} 个标签...")
                tag_input = page.locator('[placeholder*="话题"]')
                for tag in tags[:10]:  # 最多10个标签
                    await tag_input.fill(f"#{tag}")
                    await page.wait_for_timeout(800)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(500)

            # 6. 点击发布
            logger.info("[XHS] 点击发布按钮...")
            publish_btn = page.locator('button:has-text("发布")')
            await publish_btn.click()

            # 等待发布完成
            await page.wait_for_timeout(5000)

            # 检查是否成功
            current_url = page.url
            if "publish" not in current_url and "creator" in current_url:
                return {"success": True, "content_id": current_url}
            else:
                # 截图留证
                await page.screenshot(
                    path=f"error_screenshots/xhs_{int(import_time())}.png"
                )
                return {"success": False, "error": "发布后未跳转到预期页面"}

        except Exception as e:
            logger.error(f"[XHS] 发布异常: {e}")
            if page:
                try:
                    await page.screenshot(path=f"error_screenshots/xhs_error.png")
                except Exception:
                    pass
            return {"success": False, "error": str(e)}
        finally:
            if page:
                await page.close()


def import_time():
    import time
    return time.time()
