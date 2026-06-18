"""
豆包 Seedream 5.0 Lite 图片生成服务
火山引擎方舟平台 API: POST /api/v3/images/generations
"""
import httpx
from typing import List, Optional
from loguru import logger
from backend.config import settings


class ImageGenerator:
    """Seedream 5.0 图片生成"""

    # 支持的尺寸（Seedream API 要求小写: 2k/3k/4k 或 WIDTHxHEIGHT）
    SIZE_OPTIONS = {
        "1k": "1472x1472",  # ≈1K 判等
        "2k": "2k",
        "3k": "3k",
        "4k": "4k",
    }

    def __init__(self):
        self.api_key = settings.IMAGE_GEN_API_KEY
        self.api_base = settings.IMAGE_GEN_API_BASE
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
        size: str = "2k",
        negative_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """
        生成单张图片

        Args:
            prompt: 图片描述词
            size: 1K / 2K / 4K
            negative_prompt: 反向提示词

        Returns:
            图片 URL，失败返回 None
        """
        if not self.is_configured:
            logger.warning("IMAGE_GEN_API_KEY 未配置，跳过图片生成")
            return None

        url = f"{self.api_base}/images/generations"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": size,
            "stream": False,
            "watermark": True,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

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
                logger.info(f"[Seedream] 图片生成成功: {image_url[:60]}...")
            else:
                logger.warning(f"[Seedream] 返回数据中无图片URL: {data}")
            return image_url

        except httpx.HTTPStatusError as e:
            logger.error(f"[Seedream] HTTP {e.response.status_code}: {e.response.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"[Seedream] 生成异常: {e}")
            return None

    async def generate_batch(
        self,
        prompts: List[str],
        size: str = "2k",
    ) -> List[Optional[str]]:
        """
        批量生成图片（带2秒间隔避免并发限流）

        Returns:
            URL 列表，生成失败的项为 None
        """
        import asyncio

        urls = []
        for i, prompt in enumerate(prompts):
            if not prompt or not prompt.strip():
                urls.append(None)
                continue

            logger.info(f"[Seedream] 生成第 {i+1}/{len(prompts)} 张: {prompt[:50]}...")
            url = await self.generate(prompt, size)
            urls.append(url)

            # 间隔避免限流
            if i < len(prompts) - 1:
                await asyncio.sleep(2)

        return urls

    def _extract_url(self, data: dict) -> Optional[str]:
        """从 Seedream 响应中提取图片 URL"""
        # 标准返回格式: {"data": [{"url": "https://..."}]}
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            item = data["data"][0]
            if isinstance(item, dict):
                return item.get("url")
            elif isinstance(item, str):
                return item
        return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# 全局单例
image_generator = ImageGenerator()
