"""
Agnes-Image-2.1-Flash 图片生成服务
API: POST https://apihub.agnes-ai.com/v1/images/generations
返回格式: {"data": [{"url": "https://..."}]}
"""
import httpx
from typing import List, Optional
from loguru import logger
from backend.config import settings


class ImageGenerator:
    """Agnes 图片生成 (images/generations 接口)"""

    def __init__(self):
        self.api_key = settings.IMAGE_GEN_API_KEY
        self.api_base = settings.IMAGE_GEN_API_BASE.rstrip("/")
        self.model = settings.IMAGE_GEN_MODEL
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        negative_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        生成单张图片

        Args:
            prompt: 图片描述词（英文效果更佳）
            size: 图片尺寸（如 "1024x1024"，可选）
            negative_prompt: 反向提示词（追加在 prompt 后，以 avoid: 形式）

        Returns:
            图片 URL，失败返回 None
        """
        if not self.is_configured:
            logger.warning("IMAGE_GEN_API_KEY 未配置，跳过图片生成")
            return None

        # 构建完整 prompt
        full_prompt = prompt.strip()
        if negative_prompt:
            full_prompt += f", avoid: {negative_prompt.strip()}"

        url = f"{self.api_base}/images/generations"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            client = await self._get_client()
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # 解析返回的图片 URL
            image_url = self._extract_url(data)
            if image_url:
                logger.info(f"[Agnes] 图片生成成功: {image_url[:80]}...")
            else:
                logger.warning(f"[Agnes] 返回数据中未找到图片URL: {data}")
            return image_url

        except httpx.HTTPStatusError as e:
            logger.error(f"[Agnes] HTTP {e.response.status_code}: {e.response.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"[Agnes] 生成异常: {e}")
            return None

    async def generate_batch(
        self,
        prompts: List[str],
        size: str = "1024x1024",
    ) -> List[Optional[str]]:
        """
        批量生成图片（带 2 秒间隔避免并发限流）

        Returns:
            URL 列表，生成失败的项为 None
        """
        import asyncio

        urls = []
        for i, prompt in enumerate(prompts):
            if not prompt or not prompt.strip():
                urls.append(None)
                continue

            logger.info(f"[Agnes] 生成第 {i+1}/{len(prompts)} 张: {prompt[:50]}...")
            url = await self.generate(prompt, size)
            urls.append(url)

            # 间隔避免限流
            if i < len(prompts) - 1:
                await asyncio.sleep(2)

        return urls

    def _extract_url(self, data: dict) -> Optional[str]:
        """
        从 Agnes images/generations 响应中提取图片 URL

        Agnes 返回格式：
        {
          "created": 1782265562,
          "data": [{"url": "https://platform-outputs.agnes-ai.space/images/..."}]
        }
        """
        try:
            items = data.get("data", [])
            if not items:
                return None
            item = items[0]
            if isinstance(item, dict):
                return item.get("url") or item.get("b64_json")
            elif isinstance(item, str):
                return item
            return None
        except Exception as e:
            logger.error(f"[Agnes] 解析响应失败: {e}, data={data}")
            return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# 全局单例
image_generator = ImageGenerator()
