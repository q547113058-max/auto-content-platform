"""
时区工具 — 统一使用东八区 (Asia/Shanghai, UTC+8)
"""
from datetime import datetime, timezone, timedelta
import functools

TZ_SHANGHAI = timezone(timedelta(hours=8))


def now_utc() -> datetime:
    """返回带 tzinfo 的 UTC 当前时间"""
    return datetime.now(timezone.utc)


def now_shanghai() -> datetime:
    """返回东八区当前时间 (Asia/Shanghai)"""
    return datetime.now(TZ_SHANGHAI)


def to_shanghai(dt: datetime) -> datetime:
    """将任意 datetime 转为东八区"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_SHANGHAI)


# 便捷别名，项目中统一用这个
now = now_shanghai
