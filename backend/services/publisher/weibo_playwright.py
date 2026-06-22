"""
微博发布器 — Playwright 方案
适配微博 PC 端新版 UI 发布流程
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from backend.services.publisher_base import PlatformPublisher

# 截图目录
SCREENSHOT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "debug_screenshots"


class WeiboPlaywrightPublisher(PlatformPublisher):
    platform_name = "weibo"

    # 发布框候选选择器（按优先级）
    COMPOSE_SELECTORS = [
        # 新版微博发布框
        'textarea[class*="Form"]',
        'textarea[class*="Content"]',
        'textarea[class*="input"]',
        'textarea[class*="editor"]',
        'textarea[placeholder*="发布"]',
        'textarea[placeholder*="微博"]',
        'textarea[placeholder*="说点什么"]',
        'textarea[placeholder*="有什么新鲜事"]',
        # 通用 textarea
        'textarea',
    ]

    # 发布按钮候选选择器
    SUBMIT_SELECTORS = [
        'a[action-type="submit"]',
        'button[class*="submit"]',
        'button[class*="publish"]',
        'button[class*="send"]',
        'span[class*="publish"]:not([class*="disabled"])',
        '[class*="publish"] [class*="btn"]',
    ]

    async def _find_compose_box(self, page):
        """多策略查找发布框，返回第一个匹配的 locator"""
        for sel in self.COMPOSE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    logger.info(f"[Weibo] 匹配发布框: {sel}")
                    return el, sel
            except Exception:
                continue
        return None, None

    async def _find_submit_btn(self, page):
        """多策略查找发布按钮"""
        for sel in self.SUBMIT_SELECTORS:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1000):
                    logger.info(f"[Weibo] 匹配发布按钮: {sel}")
                    return btn
            except Exception:
                continue
        return None

    async def _save_debug_screenshot(self, page, tag: str):
        """保存调试截图"""
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = SCREENSHOT_DIR / f"weibo_publish_{tag}_{ts}.png"
            await page.screenshot(path=str(path), full_page=True)
            logger.info(f"[Weibo] 调试截图: {path}")
        except Exception as e:
            logger.warning(f"[Weibo] 截图失败: {e}")

    async def publish(self, context, content: Dict[str, Any]) -> Dict[str, Any]:
        page = None
        try:
            page = await context.new_page()

            # ── 步骤 1: 导航到微博首页 ──
            logger.info("[Weibo] 导航到微博首页...")
            await page.goto(
                "https://weibo.com",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(2000)

            # ── 步骤 2: 激活发布框（新版微博需要点击展开） ──
            logger.info("[Weibo] 激活发布框...")
            # 尝试点击发布区域激活输入框
            click_targets = [
                'textarea',  # 直接点 textarea
                'div[class*="publish"]',  # 发布区域外框
                'div[class*="input"]',  # 输入区
                '[class*="editor"]',  # 编辑器区
                '[class*="compose"]',  # 编写区
            ]
            activated = False
            for csel in click_targets:
                try:
                    el = page.locator(csel).first
                    if await el.is_visible(timeout=800):
                        await el.click(timeout=2000)
                        await page.wait_for_timeout(1500)
                        logger.info(f"[Weibo] 点击激活: {csel}")
                        activated = True
                        break
                except Exception:
                    continue

            if not activated:
                logger.warning("[Weibo] 未能找到可点击的发布区域，继续尝试直接输入")

            # ── 步骤 3: 构建发布文本 ──
            body = content.get("body", "")
            import re
            # 仅清理行首残留的 AI 幻觉占位符（兜底，正常已在 content_task 清理）
            body = re.sub(r'^\s*\[(配图|图片|链接)[：:][^\]]*\]\s*$', '', body, flags=re.MULTILINE)
            body = re.sub(r'\n{3,}', '\n\n', body).strip()
            # 确保换行：每个句号后如果没换行，补一个换行（微博排版优化）
            body = re.sub(r'(。)(?=[^\n])', r'\1\n', body)
            tags = " ".join([f"#{t}" for t in content.get("tags", [])])
            full_text = f"{body}\n\n{tags}"

            textarea, matched_sel = await self._find_compose_box(page)
            if not textarea:
                await self._save_debug_screenshot(page, "no_compose_box")
                return {
                    "success": False,
                    "error": "未找到微博发布框，已保存调试截图。请确认账号已登录且页面正常加载。",
                }

            logger.info(f"[Weibo] 填入内容 ({len(full_text)} 字)...")
            await textarea.fill(full_text)
            await page.wait_for_timeout(800)

            # ── 步骤 4: 上传图片 ──
            images = content.get("image_paths", [])
            if images:
                from pathlib import Path as _Path
                import httpx as _httpx
                # 过滤：确保都是本地可访问文件
                local_imgs = []
                for img in images:
                    p = _Path(img)
                    if p.exists():
                        local_imgs.append(str(p.resolve()))
                    elif img.startswith("http"):
                        # 远程URL → 下载到临时目录
                        try:
                            async with _httpx.AsyncClient(timeout=_httpx.Timeout(30.0)) as cli:
                                resp = await cli.get(img)
                                resp.raise_for_status()
                                tmp = SCREENSHOT_DIR / f"upload_{_Path(img).name or 'img.png'}"
                                tmp.write_bytes(resp.content)
                                local_imgs.append(str(tmp.resolve()))
                                logger.info(f"[Weibo] 临时下载: {img[:50]}... -> {tmp}")
                        except Exception as e:
                            logger.warning(f"[Weibo] 图片下载失败: {img[:50]}... {e}")
                    else:
                        logger.warning(f"[Weibo] 跳过无效图片路径: {img}")

                if local_imgs:
                    logger.info(f"[Weibo] 上传 {len(local_imgs)} 张图片...")
                    file_input = page.locator('input[type="file"]').first
                    try:
                        await file_input.set_input_files(local_imgs, timeout=10000)
                        await page.wait_for_timeout(3000)
                        logger.info(f"[Weibo] 图片上传完成: {len(local_imgs)} 张")
                    except Exception as e:
                        logger.warning(f"[Weibo] 图片上传失败（继续发布纯文本）: {e}")
                else:
                    logger.info("[Weibo] 无有效本地图片，跳过上传")
            else:
                logger.info("[Weibo] 无配图，纯文本发布")

            # ── 步骤 5: 点击发布 ──
            logger.info("[Weibo] 点击发布...")
            submit_btn = await self._find_submit_btn(page)
            if not submit_btn:
                # 尝试用键盘快捷键发布 (Ctrl+Enter)
                logger.info("[Weibo] 未找到发布按钮，尝试 Ctrl+Enter...")
                await page.keyboard.press("Control+Enter")
            else:
                await submit_btn.click(timeout=5000)

            await page.wait_for_timeout(5000)

            # 检查是否发布成功（页面不应跳转到登录/错误页）
            current_url = page.url
            if any(kw in current_url.lower() for kw in ("login", "error", "denied", "captcha")):
                return {"success": False, "error": f"发布后跳转到异常页面: {current_url}"}

            return {"success": True, "content_id": current_url}

        except Exception as e:
            logger.error(f"[Weibo] 发布异常: {e}")
            if page:
                await self._save_debug_screenshot(page, "exception")
            return {"success": False, "error": str(e)}
        finally:
            if page:
                await page.close()
