# -*- coding: utf-8 -*-
"""人物文件导入解析（与安卓端 CharacterImporter 同构）。

支持两种来源，自动识别、不需要用户选格式：

  1. **Kith 自家格式** —— 单个人物对象、人物数组、或带 characters 字段的存档；
  2. **喵咚平台的角色卡** —— 单卡响应（{"code":200,"data":{...}}）、
     列表响应（{"data":{"list":[...]}}）、或裸的卡对象数组。

字段映射（喵咚 → Kith）::

    name         → name
    gender       → gender
    tagList      → tags（标签直接沿用）
    introduction → personality   人设正文本来就是给模型看的设定
    openingLine  → openingLine   开场白作为空会话的第一条消息素材

这样用户手上的角色卡语料不用改一个字就能进应用。
"""
import json
import re

from kcore import new_id, now_ms
from store import to_character

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json_block(raw):
    """从任意包裹文本里挖出第一个平衡的 {...} / [...] 块（与安卓端同规则）。"""
    text = (raw or "").strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start < 0:
        return None
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for idx in range(start, len(text)):
        c = text[idx]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def _objects_of(arr):
    """收集数组里所有「看起来像人物卡」的对象。"""
    if not isinstance(arr, list):
        return []
    return [x for x in arr if isinstance(x, dict) and "name" in x]


def _extract_cards(root):
    """从任意一层包裹里把人物卡对象挖出来（data.list / data 单卡 / characters / list / 顶层）。"""
    data = root.get("data")
    if isinstance(data, dict):
        lst = _objects_of(data.get("list"))
        if lst:
            return lst
        if "name" in data:
            return [data]
    lst = _objects_of(root.get("characters"))
    if lst:
        return lst
    lst = _objects_of(root.get("list"))
    if lst:
        return lst
    if "name" in root:
        return [root]
    return []


def _map_card(card):
    """单卡 → Kith 人物 dict；解析不出有效人物返回 None（计入跳过数）。"""
    # 已经是 Kith 格式的直接走自家解码
    if "personality" in card and "importance" in card:
        try:
            ch = to_character(card)
        except Exception:
            return None
        if not ch.get("name"):
            return None
        ch["id"] = new_id("chr")
        ch["updatedAt"] = now_ms()
        return ch

    name = str(card.get("name") or "").strip()
    if not name:
        return None
    intro = str(card.get("introduction") or "").strip()
    opening = str(card.get("openingLine") or "").strip()

    tag_names = []
    for t in card.get("tagList") or []:
        if isinstance(t, dict) and str(t.get("name") or "").strip():
            tag_names.append(str(t["name"]).strip())

    gender = str(card.get("gender") or "").upper()
    if gender not in ("MALE", "FEMALE"):
        gender = "UNKNOWN"

    return {
        "id": new_id("chr"),
        "name": name,
        "alias": "",
        "gender": gender,
        "age": "",
        # 一句话简介用标签拼出来 —— 比起空着，至少在关系图和列表里有辨识度
        "oneLiner": " · ".join(tag_names[:4]) if tag_names else "（尚未填写简介）",
        # 喵咚的 introduction 本身就是给模型看的人设文本，放 personality 正好
        "personality": intro,
        "background": "",
        "appearance": "",
        "speechStyle": "",
        "openingLine": opening,
        "avatarUrl": "",
        "importance": "SUPPORTING",
        "model": None,
        "tags": [{"label": t, "hint": "", "builtin": False} for t in tag_names],
        "isUser": False,
        "isGenerated": False,
        "createdAt": now_ms(),
        "updatedAt": now_ms(),
    }


def import_characters(raw):
    """解析一段 JSON，返回 (人物列表, 跳过数)。

    跳过的原因通常是：缺少名字、或者不是人物对象。
    解析失败抛 ValueError，报错文案与安卓端一致。
    """
    text = (extract_json_block(raw) or (raw or "").strip()).strip()
    if not text:
        raise ValueError("文件是空的，没有可导入的内容")

    try:
        root = json.loads(text)
    except ValueError as e:
        raise ValueError(f"这个文件不是合法的 JSON：{e}")

    if isinstance(root, list):
        cards = _objects_of(root)
    elif isinstance(root, dict):
        cards = _extract_cards(root)
    else:
        cards = []
    if not cards:
        raise ValueError("这个 JSON 里找不到人物卡。\n\n"
                         "支持两种格式：Kith 的人物数组，或喵咚的角色卡"
                         "（含 name / introduction / openingLine / tagList 字段）。")

    out = []
    for card in cards:
        ch = _map_card(card)
        if ch:
            out.append(ch)
    if not out:
        raise ValueError(f"解析到了 {len(cards)} 个对象，但没有一个是有效的人物卡")
    return out, len(cards) - len(out)
