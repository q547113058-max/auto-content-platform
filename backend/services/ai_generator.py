"""
AI 内容生成模块
支持 DeepSeek / 通义千问 / OpenAI，多平台风格适配
"""
import json
import os
import re
import string
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from openai import AsyncOpenAI
from backend.config import settings


class AIGenerator:
    """AI 内容生成器 — 单次输入，全平台适配"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self.prompts_dir = Path(settings.PROMPTS_DIR)
        self._prompts_cache: Dict[str, Dict[str, str]] = {}
        self._formatter = string.Formatter()

    async def _get_client(self) -> AsyncOpenAI:
        """延迟初始化 AI 客户端（首次调用时才校验 API Key）"""
        if self._client is None:
            self._client = self._init_client()
        return self._client

    def _safe_format(self, template_str: str, **kwargs) -> str:
        """安全格式化模板，缺失占位符替换为空字符串"""
        result = []
        for literal, field, fmt, conv in self._formatter.parse(template_str):
            result.append(literal)
            if field is not None:
                val = kwargs.get(field, "")
                if fmt:
                    val = f"{{0:{fmt}}}".format(val)
                if conv:
                    val = f"{{0!{conv}}}".format(val)
                result.append(str(val))
        return "".join(result)

    @property
    def is_configured(self) -> bool:
        """检查 AI API Key 是否已配置"""
        provider = settings.AI_PROVIDER
        if provider == "deepseek":
            return bool(settings.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", ""))
        elif provider == "qwen":
            return bool(settings.QWEN_API_KEY or os.getenv("QWEN_API_KEY", ""))
        elif provider == "openai":
            return bool(settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""))
        return False

    def _provider_name(self) -> str:
        """返回当前 AI Provider 名称（用于错误提示）"""
        return settings.AI_PROVIDER

    def _init_client(self) -> AsyncOpenAI:
        """初始化 AI 客户端"""
        provider = settings.AI_PROVIDER

        if provider == "deepseek":
            api_key = settings.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "DeepSeek API Key 未配置。请在 .env 文件中设置 DEEPSEEK_API_KEY=你的密钥，"
                    "或设置环境变量 DEEPSEEK_API_KEY。\n"
                    "获取密钥: https://platform.deepseek.com/api_keys"
                )
            return AsyncOpenAI(api_key=api_key, base_url=settings.DEEPSEEK_API_BASE)
        elif provider == "qwen":
            api_key = settings.QWEN_API_KEY or os.getenv("QWEN_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "通义千问 API Key 未配置。请在 .env 文件中设置 QWEN_API_KEY=你的密钥，"
                    "或设置环境变量 QWEN_API_KEY。\n"
                    "获取密钥: https://dashscope.console.aliyun.com/apiKey"
                )
            return AsyncOpenAI(api_key=api_key, base_url=settings.QWEN_API_BASE)
        elif provider == "openai":
            api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "OpenAI API Key 未配置。请在 .env 文件中设置 OPENAI_API_KEY=你的密钥，"
                    "或设置环境变量 OPENAI_API_KEY。\n"
                    "获取密钥: https://platform.openai.com/api-keys"
                )
            return AsyncOpenAI(api_key=api_key, base_url=settings.OPENAI_API_BASE)
        else:
            raise ValueError(f"不支持的 AI Provider: {provider}")

    def _load_prompt(self, platform: str) -> Dict[str, str]:
        """加载平台提示词（内存缓存）"""
        if platform in self._prompts_cache:
            return self._prompts_cache[platform]

        prompt_file = self.prompts_dir / f"{platform}.json"
        if not prompt_file.exists():
            logger.warning(f"平台 {platform} 提示词文件不存在: {prompt_file}")
            return {}

        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_data = json.load(f)
            self._prompts_cache[platform] = prompt_data
            return prompt_data

    async def generate_for_platform(
        self,
        platform: str,
        product_info: Dict[str, Any],
        override_prompt: Optional[str] = None,
        topic_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        为单个平台生成内容
        topic_prompt: 选题角度注入指令（附加到 system_prompt）
        """
        prompt_data = self._load_prompt(platform)
        if not prompt_data and not override_prompt:
            return {"error": f"平台 {platform} 无提示词配置"}

        system_prompt = override_prompt or prompt_data.get("system_prompt", "")
        template = prompt_data.get("template", "")

        # 注入选题角度指令
        if topic_prompt:
            system_prompt += "\n\n" + topic_prompt

        # 全局产品内容规则（兜底注入，防止 prompt JSON 遗漏）
        if "产品信息真实性规则" not in system_prompt:
            system_prompt += """

产品信息真实性规则：
- 涉及产品具体数据（价格、成分、功效、技术参数等），必须严格基于「产品信息」区块中提供的知识库数据，不得凭空编造
- 如果输入中未提供某类数据，请勿自行编造数值，改用概括性语言替代

内容比例规则：
- 直接介绍、推荐或推销产品的内容，不得超过全文总字数的十分之一
- 文章主体应为行业分析、知识科普、使用场景、个人见解等非产品内容
- 产品信息仅可在结尾或过渡处自然带出，不可喧宾夺主"""

        # 构建用户提示词
        user_prompt = self._safe_format(template, **product_info)

        # 调用 LLM
        try:
            client = await self._get_client()
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
            )

            generated_text = response.choices[0].message.content

            # 解析生成内容
            result = self._parse_generated_content(generated_text, platform)

            # 生成配图描述
            image_descs = self._extract_image_descriptions(generated_text)
            result["image_descriptions"] = image_descs

            return result
        except Exception as e:
            logger.error(f"[{platform}] AI 生成失败: {e}")
            return {"error": str(e)}

    async def generate_for_all_platforms(
        self,
        product_info: Dict[str, Any],
        platforms: List[str] = None,
        override_prompt: Optional[str] = None,
        topic_prompt_map: Optional[Dict[str, str]] = None,
        topic_name_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        一次输入，全平台生成
        topic_prompt_map: {platform: topic_prompt} 各平台选题角度注入
        topic_name_map: {platform: topic_name} 各平台选题名称（模板 {topic_category} 填充）
        """
        platforms = platforms or [
            "xiaohongshu", "zhihu", "weibo", "wechat", "toutiao", "douyin"
        ]
        topic_prompt_map = topic_prompt_map or {}
        topic_name_map = topic_name_map or {}

        import asyncio
        tasks = []
        for p in platforms:
            # 每个平台注入独立的 topic_category 名称
            p_info = dict(product_info)
            p_info["topic_category"] = topic_name_map.get(p, "")
            tasks.append(
                self.generate_for_platform(p, p_info, override_prompt, topic_prompt_map.get(p))
            )
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for platform, result in zip(platforms, results_list):
            if isinstance(result, Exception):
                results[platform] = {"error": str(result)}
            else:
                results[platform] = result

        return results

    def _parse_generated_content(self, text: str, platform: str) -> Dict[str, Any]:
        """解析 AI 生成的内容（去除 Markdown、标准化标点、提取内联图片标记、去重）"""
        # 1. 去除 Markdown 格式标记
        text = self._clean_markdown(text)

        # 2. 标准化标点符号
        text = self._normalize_punctuation(text)

        # 3. 清理 AI 幻觉占位符：[配图:xxx] / [配图：xxx] / [图片:xxx] 等
        text = re.sub(r'\[配图[：:].*?\]', '', text)
        text = re.sub(r'\[图片[：:].*?\]', '', text)

        lines = text.strip().split("\n")

        title = ""
        body_start = 0
        tags = []
        image_markers = []  # [(position_index, description), ...]

        # 尝试解析标题（通常在第一行）
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if line_stripped.startswith("标题") or line_stripped.startswith("#"):
                title = line_stripped.replace("标题：", "").replace("标题:", "").replace("# ", "").strip()
                body_start = i + 1
                break
            elif len(line_stripped) <= 30 and i == 0:
                title = line_stripped
                body_start = i + 1
                break

        # 如果没找到标题，用第一行非空内容
        if not title:
            for line in lines:
                if line.strip():
                    title = line.strip()[:30]
                    break

        # 构建正文（提取内联图片标记，句子级去重）
        body_parts = []
        seen_fingerprints = set()  # 句子指纹去重

        # 预编译正则
        img_pattern = re.compile(r'\[IMG:(.*?)\]')
        img_with_colon = re.compile(r'\[IMG[：:](.*?)\]')
        link_pattern = re.compile(r'\[配图[：:].*?\]')
        pic_pattern = re.compile(r'\[图片[：:].*?\]')
        tag_pattern = re.compile(r'#[\w\u4e00-\u9fff]+')
        # 中文句子分割（。！？\n）+ 英文句号后跟空格
        sent_split = re.compile(r'(?<=[。！？\n])(?=\S)')

        def _clean_for_fingerprint(s: str) -> str:
            """去掉标签和空格，取前30+后20字做指纹"""
            c = tag_pattern.sub('', s).strip()
            c = re.sub(r'\s+', '', c)
            return (c[:30] + c[-20:]).strip() if len(c) >= 15 else c

        for line in lines[body_start:]:
            # 提取 [IMG:description] 和 [IMG：description] 标记
            img_descs = []
            for m in img_pattern.finditer(line):
                d = m.group(1).strip()
                if d:
                    img_descs.append(d)
            for m in img_with_colon.finditer(line):
                d = m.group(1).strip()
                if d:
                    img_descs.append(d)

            for desc in img_descs:
                image_markers.append((len(body_parts), desc))

            # 移除所有标记但保留其他内容
            line = img_pattern.sub('', line)
            line = img_with_colon.sub('', line)
            line = link_pattern.sub('', line)
            line = pic_pattern.sub('', line)
            line = line.strip()

            if not line:
                continue

            # ── 句子级去重：把长行切成句子，逐句比对 ──
            if len(line) > 40:
                sub_sentences = sent_split.split(line)
                deduped_parts = []
                for sub in sub_sentences:
                    sub = sub.strip()
                    if not sub or len(sub) < 4:
                        if sub:
                            deduped_parts.append(sub)
                        continue
                    fp = _clean_for_fingerprint(sub)
                    if not fp or fp in seen_fingerprints:
                        continue
                    seen_fingerprints.add(fp)
                    deduped_parts.append(sub)
                line = ''.join(deduped_parts)
                if not line.strip():
                    continue
            else:
                # 短行：整行指纹去重
                fp = _clean_for_fingerprint(line)
                if fp and fp in seen_fingerprints:
                    continue
                if fp:
                    seen_fingerprints.add(fp)

            body_parts.append(line)

        body = "\n".join(body_parts).strip()

        # 最终清洗：移除行首尾残留的 [xxx:...] 格式（兜底）
        body = re.sub(r'^\s*\[(配图|图片|链接)[：:][^\]]*\]\s*$', '', body, flags=re.MULTILINE)

        # 提取标签
        for line in lines:
            if "标签" in line or "#" in line:
                found_tags = re.findall(r'#([\w\u4e00-\u9fff]+)', line)
                tags.extend(found_tags)
                tag_text = line.replace("标签：", "").replace("标签:", "")
                if "," in tag_text or "，" in tag_text:
                    for sep in [",", "，"]:
                        if sep in tag_text:
                            tags.extend([t.strip() for t in tag_text.split(sep)])
                            break

        # 去重 & 过滤空标签
        tags = [t for t in list(set(tags))[:10] if t.strip()]

        return {
            "title": title,
            "body": body,
            "tags": tags,
            "raw_generated": text,
            "image_markers": image_markers,  # [(line_index, description), ...]
        }

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """去除 Markdown 格式标记：**、###、---、__ 等"""
        # 水平线
        text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
        # 粗体 **text** 和 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # 斜体 *text* 和 _text_（小心不要误删乘法符号）
        text = re.sub(r'(?<!\w)\*(\S.*?\S)\*(?!\w)', r'\1', text)
        text = re.sub(r'(?<!\w)_(\S.*?\S)_(?!\w)', r'\1', text)
        # 标题标记 ### ## #
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # 删除线 ~~text~~
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        # 反引号 `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 多余空行合并
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    @staticmethod
    def _normalize_punctuation(text: str) -> str:
        """标准化中英文混排标点符号"""
        # CJK 字符范围
        cjk = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]'

        # 英文句号 → 中文句号（在中文之后）
        text = re.sub(f'({cjk})\\.', r'\1。', text)
        # 英文逗号 → 中文逗号（在中文之间或之后）
        text = re.sub(f'({cjk}),(?=\\s*{cjk})', r'\1，', text)
        text = re.sub(f'({cjk}),(?!\\d)', r'\1，', text)
        # 英文感叹号 → 中文感叹号
        text = re.sub(f'({cjk})!', r'\1！', text)
        # 英文问号 → 中文问号
        text = re.sub(f'({cjk})\\?', r'\1？', text)
        # 英文冒号 → 中文冒号（在中文之后）
        text = re.sub(f'({cjk}):', r'\1：', text)
        # 英文分号 → 中文分号
        text = re.sub(f'({cjk});', r'\1；', text)
        # 英文左括号 → 中文左括号（中文文本中）
        text = re.sub(f'({cjk})\\(', r'\1（', text)
        # 英文右括号 → 中文右括号
        text = re.sub(f'\\)(\\s*{cjk})', r'）\1', text)

        # 英文双引号 → 中文双引号
        LEFT = '\u201c'
        RIGHT = '\u201d'
        def _quote_repl(m):
            return m.group(1) + LEFT
        def _quote_repl2(m):
            return RIGHT + m.group(1)
        text = re.sub(f'({cjk})"', _quote_repl, text)
        text = re.sub(f'"({cjk})', _quote_repl2, text)
        # 剩余未配对的 " 也转换
        quote_count = 0
        result_chars = []
        for ch in text:
            if ch == '"' and quote_count == 0:
                result_chars.append(LEFT)
                quote_count = 1
            elif ch == '"':
                result_chars.append(RIGHT)
                quote_count = 0
            else:
                result_chars.append(ch)
        text = ''.join(result_chars)

        # 中文间多余空格移除
        text = re.sub(f'({cjk})\\s+({cjk})', r'\1\2', text)

        # 多个连续感叹号/问号 → 保留一个
        text = re.sub(r'！{2,}', '！', text)
        text = re.sub(r'？{2,}', '？', text)

        return text

    def _extract_image_descriptions(self, text: str) -> List[str]:
        """提取 AI 生成的配图描述 — 优先从 [IMG:...] 内联标记提取"""
        # 1. 优先提取内联 [IMG:description]
        inline = re.findall(r'\[IMG:(.*?)\]', text)
        if inline:
            return [d.strip()[:200] for d in inline if d.strip()][:10]

        # 2. 回退：从"配图建议"段落提取
        descriptions = []
        lines = text.split("\n")
        in_image_section = False

        for line in lines:
            line = line.strip()
            if "配图" in line and ("建议" in line or "描述" in line or "说明" in line):
                in_image_section = True
                continue
            if in_image_section and line.startswith(("-", "•", "·", "1.", "2.", "3.", "4.", "5.")):
                desc = line.lstrip("-•·1234567890. ").strip()
                if desc:
                    descriptions.append(desc)

        return descriptions[:10]


# 全局单例
ai_generator = AIGenerator()
