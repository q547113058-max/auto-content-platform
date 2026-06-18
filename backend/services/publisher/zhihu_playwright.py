"""
知乎发布器 — Playwright 方案
支持图片上传（从生成的URL下载后上传到知乎编辑器）
"""
import os
import re
import tempfile
from typing import Dict, Any, List
from loguru import logger
import httpx
from backend.services.publisher_base import PlatformPublisher


class ZhihuPlaywrightPublisher(PlatformPublisher):
    platform_name = "zhihu"

    async def _download_images(self, urls: List[str]) -> List[str]:
        """下载图片到临时文件，返回本地路径列表（下载失败跳过，不中断发布）"""
        temp_files = []
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="zhihu_images_")
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for i, url in enumerate(urls):
                if not url:
                    temp_files.append(None)
                    continue
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    ext = ".png"
                    content_type = resp.headers.get("content-type", "")
                    if "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    elif "webp" in content_type:
                        ext = ".webp"
                    tmp_path = os.path.join(tmp_dir, f"img_{i}{ext}")
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    temp_files.append(tmp_path)
                    logger.info(f"[Zhihu] 图片下载成功: {url[:60]}... ({len(resp.content)} bytes)")
                except Exception as e:
                    logger.warning(f"[Zhihu] 图片下载失败（跳过）{url[:60]}: {e}")
                    temp_files.append(None)  # 失败跳过，不影响文字发布
        return temp_files

    async def _upload_images_to_editor(self, page, temp_files: List[str]) -> int:
        """通过知乎编辑器的文件上传按钮上传图片，返回成功上传数量"""
        uploaded = 0
        valid_files = [f for f in temp_files if f and os.path.exists(f)]
        if not valid_files:
            logger.info("[Zhihu] 没有需要上传的图片")
            return 0

        # 知乎编辑器图片上传按钮选择器（精准匹配，避免点到撤销/重做等其他按钮）
        img_trigger_selectors = [
            # 最精准：直接找 hidden file input（知乎编辑器内置）
            # 后备方案：工具栏中含有 Picture/Image 图标类名的按钮
            'button[data-tooltip*="图片"]',
            'button[data-tooltip*="Image"]',
            'button[aria-label*="图片"]',
            'button[aria-label*="Image"]',
            '[class*="toolbar"] button[class*="image"]',
            '[class*="Toolbar"] button[class*="image"]',
            # 知乎特定：图片上传按钮通常有 Picture 图标
            'svg[class*="Picture"] >> xpath=../../../..',
            'svg[class*="Image"] >> xpath=../../../..',
            'button:has(svg[class*="Picture"])',
            'button:has(svg[class*="Image"])',
            # 工具栏里第6个按钮（通常是图片，在粗体/斜体/链接/代码/分割线之后）
            '[class*="toolbar"] button:nth-child(6)',
        ]

        # 确保编辑器获得焦点
        editor = page.locator('div[role="textbox"][contenteditable="true"]').first
        await editor.click()
        await page.wait_for_timeout(500)

        # 截图调试（查看当前页面状态）
        try:
            await page.screenshot(path="/tmp/zhihu_before_upload.png")
            logger.info("[Zhihu] 截图已保存到 /tmp/zhihu_before_upload.png")
        except Exception:
            pass

        # 逐个上传图片（知乎编辑器每次只能上传一张）
        for i, tmp_file in enumerate(valid_files):
            try:
                # 方法1: 直接找隐藏的 file input（最可靠）
                file_inputs = page.locator('input[type="file"]')
                input_count = await file_inputs.count()
                logger.info(f"[Zhihu] 找到 {input_count} 个 file input")
                
                if input_count > 0:
                    # 找接受图片的 input
                    for fi_idx in range(input_count):
                        fi = file_inputs.nth(fi_idx)
                        accept = await fi.get_attribute("accept") or ""
                        logger.info(f"[Zhihu] file input {fi_idx}: accept={accept}")
                        if "image" in accept or accept == "":
                            await fi.set_input_files(tmp_file)
                            await page.wait_for_timeout(6000)
                            uploaded += 1
                            logger.info(f"[Zhihu] 图片 {i+1}/{len(valid_files)} 上传成功 (file input {fi_idx})")
                            break
                    else:
                        logger.warning(f"[Zhihu] 未找到适合图片的 file input，跳过图片 {i+1}")
                    continue
                
                # 方法2: 尝试工具栏按钮触发 file chooser
                clicked = False
                for sel in img_trigger_selectors:
                    btn = page.locator(sel).first
                    count = await btn.count()
                    if count > 0:
                        # 快速检查按钮是否可见
                        try:
                            is_visible = await btn.is_visible()
                        except Exception:
                            is_visible = False
                        if is_visible:
                            try:
                                async with page.expect_file_chooser(timeout=5000) as fc_info:
                                    await btn.click(timeout=5000)
                                file_chooser = await fc_info.value
                                await file_chooser.set_files(tmp_file)
                                await page.wait_for_timeout(6000)
                                uploaded += 1
                                clicked = True
                                logger.info(f"[Zhihu] 图片 {i+1}/{len(valid_files)} 上传成功 via {sel}")
                                break
                            except Exception as e2:
                                logger.warning(f"[Zhihu] 选择器 {sel} 触发失败: {e2}")
                
                if not clicked:
                    logger.warning(f"[Zhihu] 未找到图片上传入口，跳过图片 {i+1}")

            except Exception as e:
                logger.error(f"[Zhihu] 图片上传失败 {i+1}: {e}")

        return uploaded

    async def publish(self, context, content: Dict[str, Any]) -> Dict[str, Any]:
        page = None
        temp_files = []
        try:
            # 授予剪贴板权限
            await context.grant_permissions(["clipboard-read", "clipboard-write"])

            page = await context.new_page()

            logger.info("[Zhihu] 进入创作中心...")
            await page.goto(
                "https://zhuanlan.zhihu.com/write",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)
            
            # 截图确认页面状态
            try:
                await page.screenshot(path="/tmp/zhihu_page_loaded.png")
                logger.info(f"[Zhihu] 页面已加载，URL: {page.url}")
            except Exception:
                pass

            # === 1. 填写标题 ===
            title = content.get("title", "")
            if title:
                # 知乎文章标题选择器（多种尝试）
                title_selectors = [
                    'textarea[placeholder*="请输入标题"]',
                    'input[placeholder*="请输入标题"]',
                    'textarea[placeholder*="标题"]',
                    'input[placeholder*="标题"]',
                    '[class*="title"] textarea',
                    '[class*="title"] input',
                    '[class*="Title"] textarea',
                    '[class*="Title"] input',
                    'div[data-placeholder*="标题"]',
                    'div[contenteditable="true"][data-placeholder*="标题"]',
                ]
                title_filled = False
                for sel in title_selectors:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        try:
                            await el.click(timeout=3000)
                            await page.wait_for_timeout(300)
                            # 先清空
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            # 填写标题
                            try:
                                await el.fill(title, timeout=3000)
                            except Exception:
                                # contenteditable div 不支持 fill，用 type
                                await el.type(title, timeout=5000)
                            await page.wait_for_timeout(500)
                            title_filled = True
                            logger.info(f"[Zhihu] 标题填写成功，选择器: {sel}")
                            break
                        except Exception as e2:
                            logger.warning(f"[Zhihu] 标题选择器 {sel} 失败: {e2}")
                
                if not title_filled:
                    # 获取页面 HTML 帮助调试
                    try:
                        inputs = await page.locator('input, textarea, [contenteditable="true"]').all()
                        logger.warning(f"[Zhihu] 未找到标题输入框，页面共有 {len(inputs)} 个输入元素")
                        for idx, inp in enumerate(inputs[:5]):
                            ph = await inp.get_attribute("placeholder") or ""
                            cls = await inp.get_attribute("class") or ""
                            logger.warning(f"[Zhihu] 输入元素 {idx}: placeholder='{ph}' class='{cls[:50]}'")
                    except Exception:
                        pass

            # === 2. 处理正文和图片 ===
            body = content.get("body", "")
            image_urls = content.get("image_paths", []) or []
            
            # 也尝试从 body 中解析 [配图:url] 标记
            marker_urls = re.findall(r'\[配图:(.*?)\]', body)
            
            # 合并图片URL：优先用 image_paths，其次用 body 中的标记
            all_image_urls = list(image_urls)
            for u in marker_urls:
                if u not in all_image_urls:
                    all_image_urls.append(u)
            
            # 清理 body 中的标记
            clean_body = re.sub(r'\[配图:.*?\]', '', body)
            clean_body = clean_body.strip()

            editor = page.locator('div[role="textbox"][contenteditable="true"]').first

            if all_image_urls:
                logger.info(f"[Zhihu] 准备上传 {len(all_image_urls)} 张图片...")
                
                # 下载图片到临时文件
                temp_files = await self._download_images(all_image_urls)
                valid_count = sum(1 for f in temp_files if f)
                
                if valid_count > 0:
                    # 先粘贴文本
                    if clean_body:
                        await editor.click()
                        await page.wait_for_timeout(300)
                        await page.keyboard.press("Control+a")
                        await page.keyboard.press("Backspace")
                        await page.wait_for_timeout(300)
                        
                        body_escaped = clean_body.replace("`", "\\`").replace("$", "\\$")
                        await page.evaluate("text => navigator.clipboard.writeText(text)", body_escaped)
                        await page.wait_for_timeout(500)
                        await page.keyboard.press("Control+v")
                        await page.wait_for_timeout(2000)
                        logger.info("[Zhihu] 正文粘贴成功")

                    # 光标移到末尾，准备插入图片
                    await editor.click()
                    await page.keyboard.press("Control+End")
                    await page.wait_for_timeout(500)

                    # 上传图片
                    uploaded = await self._upload_images_to_editor(page, temp_files)
                    logger.info(f"[Zhihu] 图片上传完成: {uploaded}/{valid_count} 张")
                    
                    if uploaded < valid_count:
                        logger.warning(f"[Zhihu] {valid_count - uploaded} 张图片上传失败")
                else:
                    # 无有效图片，只粘贴文本
                    if clean_body:
                        await editor.click()
                        await page.wait_for_timeout(300)
                        await page.keyboard.press("Control+a")
                        await page.keyboard.press("Backspace")
                        await page.wait_for_timeout(300)
                        body_escaped = clean_body.replace("`", "\\`").replace("$", "\\$")
                        await page.evaluate("text => navigator.clipboard.writeText(text)", body_escaped)
                        await page.wait_for_timeout(500)
                        await page.keyboard.press("Control+v")
                        await page.wait_for_timeout(2000)
            else:
                # 无图片，纯文本发布
                if clean_body:
                    await editor.click()
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Backspace")
                    await page.wait_for_timeout(300)
                    body_escaped = clean_body.replace("`", "\\`").replace("$", "\\$")
                    await page.evaluate("text => navigator.clipboard.writeText(text)", body_escaped)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Control+v")
                    await page.wait_for_timeout(2000)

            # === 3. 发布 ===
            await page.wait_for_timeout(1500)

            # 截图确认发布前状态
            try:
                await page.screenshot(path="/tmp/zhihu_before_publish.png")
                logger.info("[Zhihu] 发布前截图已保存")
            except Exception:
                pass

            # 知乎发布/更新按钮：新文章显示"发布文章"/"发布"，已存草稿显示"更新"
            # 排除"发布设置"、"发布到"等非主按钮
            # 优先匹配：主按钮（Button--pri 类），通常是发布/更新按钮
            publish_selectors = [
                'button:has-text("发布文章")',
                'button:has-text("更新")',
                'button:has-text("发布"):not(:has-text("发布设置")):not(:has-text("发布到"))',
                'button:has-text("提交")',
                'button[aria-label*="发布"]',
                'button[data-tooltip*="发布"]',
                # 兜底：找底部蓝色主按钮 (Button--pri = primary button)
                'button.Button--pri',
            ]

            publish_btn = None
            for ps in publish_selectors:
                btn = page.locator(ps).first
                if await btn.count() > 0:
                    try:
                        is_visible = await btn.is_visible()
                    except Exception:
                        is_visible = False
                    if is_visible:
                        publish_btn = btn
                        btn_text = await btn.inner_text()
                        logger.info(f"[Zhihu] 找到发布按钮: '{btn_text.strip()}' -> 选择器: {ps}")
                        break

            if publish_btn is None:
                # 枚举所有按钮帮助调试
                all_btns = await page.locator('button').all()
                logger.warning(f"[Zhihu] 未找到发布按钮！页面共有 {len(all_btns)} 个 button 元素")
                for bi, b in enumerate(all_btns[:10]):
                    try:
                        txt = await b.inner_text()
                        dis = await b.get_attribute("disabled")
                        logger.warning(f"[Zhihu] button[{bi}]: text='{txt.strip()[:30]}' disabled={dis}")
                    except Exception:
                        pass
                return {"success": False, "error": "未找到发布按钮"}

            # 等待发布按钮变为 enabled（最多等20s）
            btn_enabled = False
            for i in range(40):
                is_disabled = await publish_btn.get_attribute("disabled")
                if is_disabled is None:
                    btn_enabled = True
                    break
                # 也检查 aria-disabled
                aria_disabled = await publish_btn.get_attribute("aria-disabled")
                if aria_disabled != "true" and is_disabled != "true":
                    btn_enabled = True
                    break
                if i % 4 == 0:
                    logger.info(f"[Zhihu] 发布按钮仍 disabled (第{i*0.5:.0f}s)...")
                await page.wait_for_timeout(500)

            if not btn_enabled:
                logger.warning("[Zhihu] 发布按钮等待20s仍 disabled，尝试强制点击...")

            logger.info("[Zhihu] 点击发布按钮...")
            
            # 方法1: 直接 click
            try:
                await publish_btn.click(timeout=5000, force=not btn_enabled)
            except Exception as click_err:
                logger.warning(f"[Zhihu] click 失败: {click_err}，尝试 JS click...")
                await publish_btn.evaluate("el => el.click()")

            await page.wait_for_timeout(2000)

            # 检查是否有确认弹窗（知乎有时会弹出"确认发布"对话框）
            confirm_selectors = [
                'button:has-text("确认")',
                'button:has-text("确定")',
                'button:has-text("确认发布")',
                'div[role="dialog"] button:has-text("发布")',
                '[class*="Modal"] button:has-text("发布")',
                '[class*="modal"] button:has-text("发布")',
            ]
            for cs in confirm_selectors:
                confirm_btn = page.locator(cs).first
                if await confirm_btn.count() > 0:
                    try:
                        is_visible = await confirm_btn.is_visible()
                    except Exception:
                        is_visible = False
                    if is_visible:
                        confirm_text = await confirm_btn.inner_text()
                        logger.info(f"[Zhihu] 发现确认弹窗按钮: '{confirm_text.strip()}'，点击确认...")
                        await confirm_btn.click(timeout=5000)
                        await page.wait_for_timeout(5000)
                        break

            # 检查是否发布成功（编辑页URL含 /edit，发布后不含 /edit）
            await page.wait_for_timeout(3000)
            current_url = page.url
            
            # 截图确认发布后状态
            try:
                await page.screenshot(path="/tmp/zhihu_after_publish.png")
                logger.info(f"[Zhihu] 发布后截图已保存，URL: {current_url}")
            except Exception:
                pass

            # 成功标志：URL 包含 /p/xxx 但不包含 /edit
            if "/p/" in current_url and "/edit" not in current_url:
                logger.info(f"[Zhihu] 发布成功: {current_url}")
                return {"success": True, "content_id": current_url}
            
            # 仍在编辑页：发布按钮可能没生效
            if "/edit" in current_url:
                logger.warning(f"[Zhihu] 仍在编辑页，发布可能未生效: {current_url}")
                # 再等一会看看是否会自动跳转
                await page.wait_for_timeout(5000)
                current_url = page.url
                if "/p/" in current_url and "/edit" not in current_url:
                    logger.info(f"[Zhihu] 延迟后发布成功: {current_url}")
                    return {"success": True, "content_id": current_url}
                return {"success": False, "error": "发布按钮已点击但页面仍在编辑页，可能标题/内容校验未通过"}

            logger.warning(f"[Zhihu] 发布后 URL 异常: {current_url}")
            return {"success": True, "content_id": current_url, "note": "URL未跳转到文章页但可能已发布"}

        except Exception as e:
            logger.error(f"[Zhihu] 发布异常: {e}")
            return {"success": False, "error": str(e)}
        finally:
            # 清理临时文件
            for f in temp_files:
                if f:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            if page:
                await page.close()
