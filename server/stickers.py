# -*- coding: utf-8 -*-
"""表情包三级匹配 + 系统 emoji 表 —— 与安卓端 StickerLibrary.kt 同构。

系统表情用 emoji 字形渲染而非位图：emoji 在系统字体下就是用户平时在
微信里看到的样子。每个情绪词映射多个字形，命中时按 seed 取一个。
"""
from kcore import new_id, now_ms

EMOTION_GLYPHS = {
    # 开心
    "大笑": ["😄", "😆"], "偷笑": ["🤭", "😏"], "嘿嘿": ["😁", "😏"],
    "得意": ["😎", "😏"], "开心": ["😊", "😄"], "耶": ["✌️", "🙌"],
    "雀跃": ["🤗", "🙌"],
    # 笑哭
    "笑哭": ["😂", "🤣"], "笑尿": ["🤣", "😹"], "笑死": ["😂", "💀"],
    "笑不活了": ["🤣", "🫠"], "笑到打鸣": ["🤣", "🐔"],
    # 拥抱安慰
    "抱抱": ["🫂", "🤗"], "摸摸": ["🫳", "🥺"], "拍拍": ["🫂", "🤚"],
    "安慰": ["🥺", "🫂"], "心疼": ["🥺", "💔"],
    # 点赞
    "点赞": ["👍", "👏"], "棒": ["👍", "⭐"], "牛": ["🐮", "💪"],
    "666": ["🔥", "👏"], "太强了": ["💪", "🔥"], "服": ["🙇", "👍"],
    # 尴尬
    "尴尬": ["😅", "😬"], "汗": ["😓", "💧"], "捂脸": ["🤦", "🫣"],
    "无语": ["😑", "🙃"], "裂开": ["🫠", "💥"],
    # 委屈
    "委屈": ["🥺", "😞"], "可怜": ["🥺", "😢"], "哭": ["😭", "😢"],
    "嘤嘤": ["🥺", "😿"], "泪目": ["🥹", "😢"],
    # 调侃
    "狗头": ["🐶", "🐕"], "吃瓜": ["🍉", "👀"], "看热闹": ["👀", "🍿"],
    "坏笑": ["😏", "😼"], "阴阳怪气": ["🙃", "😏"],
    # 生气
    "生气": ["😠", "😤"], "怒": ["😡", "💢"], "哼": ["😤", "😾"],
    "不服": ["😤", "🙄"], "气鼓鼓": ["😤", "😠"],
    # 可爱
    "比心": ["🫰", "💕"], "飞吻": ["😘", "💋"], "萌萌哒": ["🥰", "🐰"],
    "可爱": ["🥰", "😊"], "啾咪": ["😘", "✨"],
    # 思考
    "思考": ["🤔", "🧐"], "嗯": ["🤔", "😶"], "让我想想": ["🤔", "💭"],
    "琢磨": ["🧐", "🤔"], "沉吟": ["😶", "🤔"],
    # 惊讶
    "哇": ["😲", "🤩"], "卧槽": ["😱", "🤯"], "震惊": ["😱", "🤯"],
    "不会吧": ["😳", "😲"], "离谱": ["🤯", "🫠"],
    # 再见
    "拜拜": ["👋", "🙋"], "溜了": ["🏃", "💨"], "撤": ["🏃", "👋"],
    "跑路": ["🏃", "💨"],
}

FALLBACK_GLYPHS = ["🙂", "😊", "💬"]


def system_resolve(emotion: str):
    key = (emotion or "").strip()
    if not key:
        return None
    if key in EMOTION_GLYPHS:
        return EMOTION_GLYPHS[key]
    fuzzy = [k for k in EMOTION_GLYPHS if key in k or k in key]
    if fuzzy:
        best = max(fuzzy, key=len)
        return EMOTION_GLYPHS[best]
    return None


def resolve(library, emotion="", sticker_id="", seed=0):
    """三级匹配：id 指定 → 精确 → 模糊 → 系统 emoji 兜底。

    返回 {"kind":"image","sticker":{...}} 或 {"kind":"emoji","glyph":..,"emotion":..}
    """
    if sticker_id:
        for s in library:
            if s.get("id") == sticker_id:
                return {"kind": "image", "sticker": s}
    key = (emotion or "").strip()
    if key:
        exact = [s for s in library if key in (s.get("emotions") or [])]
        if exact:
            return _pick(exact, seed)
    if key:
        fuzzy = [s for s in library
                 if any(key in e or e in key for e in (s.get("emotions") or []))]
        if fuzzy:
            return _pick(fuzzy, seed)
    glyphs = system_resolve(key) or FALLBACK_GLYPHS
    idx = 0 if not seed else abs(seed) % len(glyphs)
    return {"kind": "emoji", "glyph": glyphs[idx], "emotion": key}


def _pick(candidates, seed):
    if len(candidates) == 1:
        return {"kind": "image", "sticker": candidates[0]}
    top = sorted(candidates, key=lambda s: -s.get("usageCount", 0))[:3]
    idx = 0 if not seed else abs(seed) % len(top)
    return {"kind": "image", "sticker": top[idx]}


def add(library, name, image_url, emotions, source="user_upload"):
    return library + [{
        "id": new_id("stk"), "name": name, "imageUrl": image_url,
        "emotions": [e.strip() for e in emotions if e and e.strip()],
        "source": source, "usageCount": 0, "createdAt": now_ms(),
    }]


def remove(library, sticker_id):
    return [s for s in library if s.get("id") != sticker_id]
