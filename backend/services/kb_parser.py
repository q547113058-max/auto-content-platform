"""
知识库 Markdown 解析器
将 knowledge_base.raw 中的非结构化 Markdown 解析为 AI prompt 可用的结构化字段
"""
import re
from typing import Dict, List, Optional


def parse_knowledge_base(raw_markdown: str, category: str = "") -> Dict[str, str]:
    """
    解析知识库 Markdown 为结构化字段。
    返回字典包含：price, key_ingredients, claims, key_points,
              target_audience, industry_context
    """
    if not raw_markdown or not raw_markdown.strip():
        return _empty_result()

    sections = _split_sections(raw_markdown)
    if not sections:
        return _empty_result()

    return {
        "price": _extract_price(sections),
        "key_ingredients": _extract_key_features(sections),
        "claims": _extract_advantages(sections),
        "key_points": _extract_key_points(sections),
        "target_audience": _extract_audience(sections),
        "industry_context": _build_industry_context(sections, category),
    }


def _empty_result() -> Dict[str, str]:
    return {
        "price": "",
        "key_ingredients": "",
        "claims": "",
        "key_points": "",
        "target_audience": "",
        "industry_context": "",
    }


# ── Section splitting ──────────────────────────────────────────

def _split_sections(raw: str) -> Dict[str, str]:
    """按 ## 标题拆分为 {标题: 正文} 字典，含子标题 ### 内容"""
    sections: Dict[str, str] = {}
    current_title: Optional[str] = None
    current_lines: List[str] = []

    for line in raw.split("\n"):
        stripped = line.strip()
        # 匹配 ## 标题（不含 ###）
        m = re.match(r"^##\s+(.+)", stripped)
        if m and not stripped.startswith("###"):
            # 保存上一节
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = m.group(1).strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


# ── Field extractors ───────────────────────────────────────────

def _match_sections(sections: Dict[str, str], keywords: List[str]) -> Dict[str, str]:
    """从 sections 中选出标题包含任意关键词的章节"""
    matched: Dict[str, str] = {}
    for title, content in sections.items():
        for kw in keywords:
            if kw in title:
                matched[title] = content
                break
    return matched


def _extract_price(sections: Dict[str, str]) -> str:
    """提取价格信息：售价、套餐、收费相关章节"""
    price_sections = _match_sections(sections, ["售价", "套餐", "收费", "价格"])

    if not price_sections:
        return ""

    # 提取所有带数字的行，合并成简洁摘要
    items: List[str] = []
    for content in price_sections.values():
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            # 跳过标题行
            if line.startswith("#"):
                continue
            # 提取「名称：价格」或「名称 + 价格」格式
            items.append(line)

    if not items:
        return ""

    # 去重去空，合并
    seen = set()
    clean = []
    for item in items:
        item = item.strip("，,。.")
        if item and item not in seen:
            seen.add(item)
            clean.append(item)

    return "；".join(clean)


def _extract_key_features(sections: Dict[str, str]) -> str:
    """提取核心功能/配置：功能、配置、规格、传感器、硬件等"""
    feat_sections = _match_sections(sections, [
        "功能", "配置", "规格", "传感器品类", "核心硬件", "硬件配置",
        "产品功能", "兼容"
    ])

    if not feat_sections:
        return ""

    lines: List[str] = []
    for content in feat_sections.values():
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 清理 Markdown 标记
            line = re.sub(r"\*\*", "", line)
            line = re.sub(r"^\d+\.\s*", "", line)
            if len(line) > 3:
                lines.append(line)

    return "\n".join(lines[:20])  # 最多 20 行


def _extract_advantages(sections: Dict[str, str]) -> str:
    """提取产品优势/卖点"""
    adv_sections = _match_sections(sections, ["优势", "亮点", "卖点"])

    if not adv_sections:
        return ""

    lines: List[str] = []
    for content in adv_sections.values():
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = re.sub(r"\*\*", "", line)
            if len(line) > 3:
                lines.append(line)

    return "\n".join(lines)


def _extract_key_points(sections: Dict[str, str]) -> str:
    """
    提取简短核心卖点（给微博/头条/抖音等短文案平台）
    融合 features + advantages 的最精简版本
    """
    features = _extract_key_features(sections)
    advantages = _extract_advantages(sections)

    combined = f"{features}\n{advantages}".strip()
    if not combined:
        return ""

    # 取前 8 行，每行不超过 30 字
    lines = [l.strip() for l in combined.split("\n") if l.strip() and not l.strip().startswith("#")]
    short_lines = [l for l in lines if len(l) <= 60][:8]
    return "；".join(short_lines) if short_lines else combined[:200]


def _extract_audience(sections: Dict[str, str]) -> str:
    """提取目标人群/适用场景"""
    aud_sections = _match_sections(sections, ["场景", "适用", "人群", "养殖对象", "目标"])

    if not aud_sections:
        return ""

    lines: List[str] = []
    for content in aud_sections.values():
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = re.sub(r"\*\*", "", line)
            if len(line) > 2:
                lines.append(line)

    return "；".join(lines)


def _build_industry_context(sections: Dict[str, str], category: str) -> str:
    """
    构建行业背景。
    从 category + 知识库中推断行业上下文。
    """
    parts = [category] if category else []

    # 从 FAQ / 说明中找行业相关描述
    ctx_sections = _match_sections(sections, ["问题", "安装", "规范", "说明", "背景"])
    if ctx_sections:
        # 提取关键信息摘要
        summary_lines: List[str] = []
        for content in ctx_sections.values():
            count = 0
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 10:
                    summary_lines.append(line)
                    count += 1
                    if count >= 3:
                        break
            if count >= 3:
                break

        if summary_lines:
            parts.append("相关说明：" + "；".join(summary_lines))

    return "\n".join(parts)
