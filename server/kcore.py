# -*- coding: utf-8 -*-
"""短 id 生成、稳定哈希、时间格式化 —— 与安卓端 Ids.kt 完全同构。"""
import re
import time
import random

_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"


def new_id(prefix: str) -> str:
    t = format(int(time.time() * 1000), "x")  # 任意基36等价即可，仅要求唯一性
    r = "".join(random.SystemRandom().choice(_ALPHABET) for _ in range(4))
    return f"{prefix}_{t}_{r}"


def stable_seed(text: str) -> int:
    """FNV-1a 32bit —— 与安卓端一致，保证同名同配色。"""
    h = 2166136261
    for ch in text:
        h ^= ord(ch) & 0xFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def initials(name: str) -> str:
    t = (name or "").strip()
    if not t:
        return "?"
    first = t[0]
    if ord(first) > 0x2E80:
        return first
    parts = re.split(r"\s+", t)
    out = "".join(p[0] for p in parts[:2] if p)
    return out.upper() or first.upper()


def safe_file_name(raw: str, fallback: str = "item") -> str:
    cleaned = re.sub(r'[\\/:*?"<>\r\n\t]', "_", raw or "").strip().strip(".")
    cleaned = cleaned or fallback
    return cleaned[:64]


def now_ms() -> int:
    return int(time.time() * 1000)


def clock(ts) -> str:
    return time.strftime("%H:%M", time.localtime(int(ts) / 1000))


def short_date_time(ts) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(int(ts) / 1000))


def full_date_time(ts) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts) / 1000))


def relative(ts, now=None) -> str:
    now = now or now_ms()
    diff = max(0, now - int(ts))
    if diff < 60_000:
        return "刚刚"
    if diff < 3_600_000:
        return f"{diff // 60_000} 分钟前"
    if diff < 86_400_000:
        return f"{diff // 3_600_000} 小时前"
    if diff < 7 * 86_400_000:
        return f"{diff // 86_400_000} 天前"
    return short_date_time(ts)


def money_cny(usd: float, rate: float = 7.2) -> str:
    """美元记账 → 人民币展示（与安卓端 Money.cny 同规则）。"""
    v = usd * (rate if rate and rate > 0 else 7.2)
    if v <= 0.0:
        return "¥0"
    if v < 0.01:
        return "<¥0.01"
    if v < 10.0:
        return "¥" + f"{v:.3f}".rstrip("0").rstrip(".") if False else f"¥{v:.3f}"
    if v < 1000.0:
        return f"¥{v:.2f}"
    return f"¥{v:.0f}"


def token_count(v: int) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}k"
    return str(v)
