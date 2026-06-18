"""
微信公众号发布器 — 纯 API 方案
支持草稿箱创建 + 发布
"""
from typing import Dict, Any
import httpx
import time
from loguru import logger
from backend.services.publisher_base import PlatformPublisher


class WechatAPIPublisher(PlatformPublisher):
    platform_name = "wechat"

    async def publish(
        self, token: str, content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        微信公众号发布流程：
        1. 上传封面图 → thumb_media_id
        2. Markdown → 微信 HTML
        3. 创建草稿 → media_id
        4. （可选）发布草稿
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Step 1: 上传封面图
                thumb_media_id = None
                if content.get("image_paths"):
                    thumb_media_id = await self._upload_thumb(
                        client, token, content["image_paths"][0]
                    )

                # Step 2: 生成微信兼容 HTML
                html_content = self._markdown_to_wechat_html(
                    content.get("title", ""),
                    content.get("body", ""),
                )

                # Step 3: 创建草稿
                draft_media_id = await self._create_draft(
                    client, token, content["title"], html_content, thumb_media_id
                )

                # Step 4: 发布草稿
                publish_url = (
                    "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
                )
                payload = {"media_id": draft_media_id}
                resp = await client.post(
                    f"{publish_url}?access_token={token}", json=payload
                )
                result = resp.json()

                if result.get("errcode") == 0:
                    # 发布成功，获取发布 ID
                    publish_id = result.get("publish_id", "")
                    return {
                        "success": True,
                        "content_id": publish_id,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"发布失败: {result.get('errmsg', '未知')}",
                    }

        except Exception as e:
            logger.error(f"[WeChat] 发布异常: {e}")
            return {"success": False, "error": str(e)}

    async def _upload_thumb(
        self, client: httpx.AsyncClient, token: str, image_path: str
    ) -> str:
        """上传封面图到永久素材库"""
        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        # 注意：需要 multipart/form-data，这里简化处理
        # 实际使用时需要读文件并构建 multipart
        logger.info(f"[WeChat] 上传封面图: {image_path}")
        return ""

    async def _create_draft(
        self, client, token, title, html_content, thumb_media_id
    ) -> str:
        """创建草稿"""
        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        payload = {
            "articles": [{
                "title": title,
                "content": html_content,
                "content_source_url": "",
                "thumb_media_id": thumb_media_id or "",
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }]
        }
        resp = await client.post(f"{url}?access_token={token}", json=payload)
        result = resp.json()

        if result.get("media_id"):
            return result["media_id"]
        raise RuntimeError(f"创建草稿失败: {result.get('errmsg', '未知')}")

    def _markdown_to_wechat_html(self, title: str, body: str) -> str:
        """简单的 Markdown → 微信兼容 HTML"""
        html = f"<h1>{title}</h1>\n"
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                html += "<br/>\n"
            elif line.startswith("## "):
                html += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith("- "):
                html += f"<p style='padding-left:2em;margin:5px 0;'>{line[2:]}</p>\n"
            else:
                html += f"<p style='margin:8px 0;line-height:1.8;'>{line}</p>\n"
        return html
