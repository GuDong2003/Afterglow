"""时间相关工具。

为了让 ingestion / retrieval 中的时间逻辑可单元测试，
所有时间换算都集中在这里，外部禁止直接使用 datetime.now / time.time。
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def now_ms() -> int:
    """返回当前 UTC 时间戳（毫秒）。"""
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def local_now(timezone_name: str = "") -> datetime:
    """返回指定时区的当前时间；配置无效时退回系统本地时区。"""
    if timezone_name.strip():
        try:
            return datetime.now(tz=ZoneInfo(timezone_name.strip()))
        except ZoneInfoNotFoundError:
            pass
    return datetime.now().astimezone()


def ms_to_datetime(ts_ms: int) -> datetime:
    """将毫秒时间戳转为 UTC datetime。"""
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC)


def gap_minutes(prev_ms: int, curr_ms: int) -> float:
    """两条消息之间的间隔（分钟，可能为负数）。"""
    return (curr_ms - prev_ms) / 1000.0 / 60.0


def age_days(ts_ms: int, now: int | None = None) -> float:
    """某时间戳距离 now 的天数（now 默认取系统当前时间）。"""
    if now is None:
        now = now_ms()
    return max(0.0, (now - ts_ms) / 1000.0 / 86400.0)


def recency_weight(
    ts_ms: int,
    *,
    half_life_days: float,
    max_boost: float,
    now: int | None = None,
) -> float:
    """计算时间衰减的权重。

    公式：1.0 + max_boost * exp(-age_days / half_life_days)。
    - 当 age=0 时，返回 1 + max_boost（最大权重）。
    - 当 age 远大于 half_life 时，趋近 1.0。
    - 半衰期越短，越偏好最近的内容。
    """
    if half_life_days <= 0:
        return 1.0
    days = age_days(ts_ms, now=now)
    decay = math.exp(-days / half_life_days)
    return 1.0 + max_boost * decay


def is_session_break(prev_ms: int, curr_ms: int, gap: timedelta) -> bool:
    """判断两条消息间是否应该切断 session。"""
    return (curr_ms - prev_ms) > int(gap.total_seconds() * 1000)
