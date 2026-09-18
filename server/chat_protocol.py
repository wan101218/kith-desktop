# -*- coding: utf-8 -*-
"""Human Chat Protocol 解析器 —— 与安卓端 ChatProtocol.kt 行为一致。

AI 回复是纯文本，内嵌自闭合 XML 风格标签：
  <sticker emotion="笑哭" />
  <chat_image prompt="橘猫晒太阳" style="写实" ratio="3:4" caption="今天路过的" />
  <transfer amount="5.20" to="小明" note="请你喝奶茶" />

解析器刻意比规范更宽容：单引号属性、漏掉斜杠的闭合、流式半截标签截断保护。
解析失败一律降级为纯文本，绝不静默丢弃模型输出的内容。

产出的 segment dict 与安卓端 Codecs.kt 的 JSON 完全同构：
  {"type":"text","content":...}
  {"type":"sticker","emotion":...,"stickerId":...}
  {"type":"picture","url":...,"prompt":...,"searchQuery":...,"style":...,"ratio":...,"caption":...,"state":...}
  {"type":"transfer","amount":...,"to":...,"note":...,"confirmed":false}
"""
import re

TAG_RE = re.compile(r"<(chat_image|sticker|transfer)\b[^>]*?/?>", re.IGNORECASE)
ATTR_RE = re.compile(r"""([A-Za-z_][\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
NAME_RE = re.compile(r"^<\s*(chat_image|sticker|transfer)", re.IGNORECASE)
OPEN_TAG_TAIL_RE = re.compile(r"<[a-z_]*$", re.IGNORECASE)


def parse_tag(tag: str):
    m = NAME_RE.match(tag)
    if not m:
        return None
    name = m.group(1).lower()
    attrs = {}
    for am in ATTR_RE.finditer(tag):
        key = am.group(1).lower()
        val = am.group(2) if am.group(2) else am.group(3)
        attrs[key] = val or ""

    if name == "sticker":
        emotion = attrs.get("emotion", "")
        sid = attrs.get("id", "")
        if not emotion and not sid:
            return None
        return {"type": "sticker", "emotion": emotion, "stickerId": sid}

    if name == "chat_image":
        url = attrs.get("url", "")
        prompt = attrs.get("prompt", "")
        query = attrs.get("search_query", "")
        if not url and not prompt and not query:
            return None
        return {"type": "picture", "url": url, "prompt": prompt, "searchQuery": query,
                "style": attrs.get("style", ""), "ratio": attrs.get("ratio", ""),
                "caption": attrs.get("caption", ""),
                "state": "READY" if url else "GENERATING"}

    if name == "transfer":
        try:
            amount = float(attrs.get("amount", ""))
        except (TypeError, ValueError):
            return None
        to = attrs.get("to", "")
        if not to:
            return None
        if amount != amount or amount < 0 or amount > 1_000_000:  # NaN / 越界
            return None
        return {"type": "transfer", "amount": amount, "to": to,
                "note": attrs.get("note", ""), "confirmed": False}
    return None


def _merge_adjacent(segments):
    if len(segments) < 2:
        return segments
    out = []
    for seg in segments:
        if seg.get("type") == "text" and out and out[-1].get("type") == "text":
            out[-1] = {"type": "text", "content": out[-1]["content"] + seg["content"]}
        else:
            out.append(seg)
    return out


def parse(raw: str):
    if not raw:
        return []
    out = []
    cursor = 0
    for m in TAG_RE.finditer(raw):
        plain = raw[cursor:m.start()]
        if plain:
            out.append({"type": "text", "content": plain})
        seg = parse_tag(m.group(0))
        if seg is None:
            out.append({"type": "text", "content": m.group(0)})  # 认不出原样保留
        else:
            out.append(seg)
        cursor = m.end()
    if cursor < len(raw):
        out.append({"type": "text", "content": raw[cursor:]})
    return _merge_adjacent(out)


def strip_tags(raw: str) -> str:
    t = TAG_RE.sub(" ", raw or "")
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def parse_streaming(buffer: str):
    """流式渲染安全截断：把未闭合的尾部标签切掉，等完整再显示。"""
    m = OPEN_TAG_TAIL_RE.search(buffer or "")
    safe = buffer[:m.start()] if m else buffer
    return parse(safe)


def plain_text(segments) -> str:
    return "".join(s.get("content", "") for s in segments if s.get("type") == "text")


def protocol_text(segments) -> str:
    """还原成带协议标签的纯文本 —— 给模型看的形态（历史轮次必须用它）。"""
    parts = []
    for s in segments:
        t = s.get("type")
        if t == "text":
            parts.append(s.get("content", ""))
        elif t == "sticker":
            a = "<sticker"
            if s.get("stickerId"):
                a += f' id="{s["stickerId"]}"'
            if s.get("emotion"):
                a += f' emotion="{s["emotion"]}"'
            parts.append(a + " />")
        elif t == "transfer":
            a = f'<transfer amount="{s.get("amount", 0):.2f}" to="{s.get("to", "")}"'
            if s.get("note"):
                a += f' note="{s["note"]}"'
            parts.append(a + " />")
        # picture 不进文本（走 attachment/视觉桥接通道）
    return "".join(parts)


def preview(segments, max_len=60) -> str:
    text = " ".join(s.get("content", "").strip() for s in segments if s.get("type") == "text")
    text = re.sub(r"\s+", " ", text).strip()
    extras = []
    if any(s.get("type") == "sticker" for s in segments):
        extras.append("[表情]")
    if any(s.get("type") == "picture" for s in segments):
        extras.append("[图片]")
    for s in segments:
        if s.get("type") == "transfer":
            extras.append(f"[转账 ¥{s.get('amount', 0):.2f}]")
            break
    combined = " ".join([t for t in [text] + extras if t])
    return combined if len(combined) <= max_len else combined[: max_len - 1] + "…"
