"""
Cookie 解析工具 — 将浏览器 Cookie 字符串解析为 Playwright StorageState 格式
支持格式：
  - Netscape cookie.txt 格式（curl -b cookies.txt 导出）
  - 浏览器开发者工具复制的 "name=value; name2=value2" 格式
  - document.cookie 输出的 "name=value; name2=value2" 格式
"""
from typing import List, Dict, Any, Optional
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse


# 平台 → 默认 domain 映射（当无法从 cookie 字符串推断时使用）
PLATFORM_DOMAINS = {
    "xiaohongshu": ".xiaohongshu.com",
    "zhihu":        ".zhihu.com",
    "weibo":        ".weibo.com",
    "wechat":       ".qq.com",
    "toutiao":      ".toutiao.com",
    "douyin":       ".douyin.com",
}


def _is_netscape_format(lines: list) -> bool:
    """检测是否为 Netscape (tab分隔) 格式，无论有无 # Netscape 头"""
    if not lines:
        return False
    # 有 # Netscape 头 → 肯定是 Netscape 格式
    if lines[0].startswith("# Netscape"):
        return True
    # 无头：检查第一有效行的tab数（Netscape格式至少7列）
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tabs = line.count("\t")
        if tabs >= 6:
            return True
        return False  # 第一有效行不像 Netscape，整体判定为非 Netscape
    return False


_DOMAIN_RE = re.compile(r"^(\.?[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


def _is_domain(s: str) -> bool:
    """判断字符串是否像域名"""
    return bool(_DOMAIN_RE.match(s)) or s.startswith(".")


def _detect_tab_format(first_data_line: str) -> str:
    """
    检测 tab 分隔格式的列顺序。
    返回 "netscape" 或 "export"。
    - "netscape":  domain, flag, path, secure, expires, name, value
    - "export":    name, value, domain, path, expires, ...
    """
    parts = first_data_line.split("\t")
    if len(parts) < 7:
        return "netscape"  # 回退到默认
    # 如果第1列像域名（以.开头或匹配域名正则），则是标准 Netscape
    if _is_domain(parts[0].strip()):
        return "netscape"
    # 如果第3列像域名，则是浏览器导出格式 (name, value, domain, ...)
    if _is_domain(parts[2].strip()):
        return "export"
    return "netscape"


def _parse_netscape_lines(lines: list, cookies: list):
    """解析 Netscape (tab分隔) 格式的 Cookie 行，自动检测列顺序"""
    # 先确定格式
    fmt = "netscape"
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fmt = _detect_tab_format(line)
        break

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue

        if fmt == "export":
            # name, value, domain, path, expires, ...
            name, value, domain, path, expires = parts[0], parts[1], parts[2], parts[3], parts[4]
            secure = False
            # 检查 expires 后的 httpOnly/secure 列（如果存在）
            if len(parts) >= 7:
                secure = "✓" in (parts[5] + parts[6])  # 浏览器导出常有 ✓ 标记
        else:
            # domain, flag, path, secure, expires, name, value
            domain, _, path, secure, expires, name, value = parts[:7]

        # 去重（同一name+domain只保留一条）
        if not any(c["name"] == name and c["domain"] == domain for c in cookies):
            cookies.append(_build_cookie(
                name=name,
                value=value,
                domain=domain,
                path=path,
                expires=_parse_expires(expires),
                secure=(secure.upper() == "TRUE") if isinstance(secure, str) else secure,
                http_only=False,
            ))


def parse_cookie_string(cookie_str: str, platform: str) -> Dict[str, Any]:
    """
    将 Cookie 字符串解析为 Playwright StorageState 格式。

    参数:
        cookie_str: 浏览器 Cookie 字符串
                     支持格式1（Netscape / Tab分隔）:
                         # Netscape HTTP Cookie File
                         .example.com\tTRUE\t/\tFALSE\t1234567890\tname\tvalue
                     支持格式1b（无头 Netscape，如浏览器 Export 或 Data 列导出）:
                         name\tvalue\tdomain\t/path\tSession/expires\t...\t...\tMedium
                     支持格式2（HTTP Header / document.cookie）:
                         name1=value1; name2=value2; ...
        platform:    平台标识，用于格式2推断 domain

    返回:
        Playwright StorageState 字典，可直接 json.dumps 后存入文件
    """
    cookies: List[Dict[str, Any]] = []
    default_domain = PLATFORM_DOMAINS.get(platform, "")

    lines = cookie_str.strip().splitlines()

    # ── 格式检测：是否为 Netscape/Tab分隔 格式 ──
    if _is_netscape_format(lines):
        _parse_netscape_lines(lines, cookies)
    # ── 格式2: HTTP Header / document.cookie 格式 ──
    else:
        # 合并所有行（处理换行的情况），然后按 ";" 分割
        merged = " ".join(lines)
        # 去掉可能的前导 # 注释行
        merged = re.sub(r"^#.*$", "", merged, flags=re.MULTILINE).strip()
        if not merged:
            raise ValueError("无法解析 Cookie 字符串：内容为空或格式不支持")

        # 按分号分割
        raw_parts = [p.strip() for p in merged.split(";") if p.strip()]

        for part in raw_parts:
            if "=" not in part:
                continue
            name, _, value = part.partition("=")
            name = name.strip()
            value = value.strip()

            # 跳过元信息字段
            if name.lower() in ("domain", "path", "expires", "max-age", "secure", "httponly", "samesite"):
                continue

            cookies.append(_build_cookie(
                name=name,
                value=value,
                domain=default_domain,
                path="/",
                expires=_one_year_from_now(),
                secure=True,
                http_only=False,
            ))

    if not cookies:
        raise ValueError("未能解析出任何 Cookie，请检查输入格式")

    return {
        "cookies": cookies,
        "origins": [],
    }


def _build_cookie(
    name: str, value: str, domain: str,
    path: str, expires: float,
    secure: bool, http_only: bool,
) -> Dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "expires": expires,
        "httpOnly": http_only,
        "secure": secure,
        "sameSite": "Lax",
    }


def _parse_expires(expires_str: str) -> float:
    """Netscape 格式 expires 是 Unix 时间戳"""
    try:
        return float(expires_str)
    except (ValueError, TypeError):
        return _one_year_from_now()


def _one_year_from_now() -> float:
    dt = datetime.now(timezone.utc) + timedelta(days=365)
    return dt.timestamp()
