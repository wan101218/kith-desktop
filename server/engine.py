# -*- coding: utf-8 -*-
"""AI 引擎 —— 与安卓端 ImportanceScorer / ModelResolver / NarratorEngine / CharacterAgent 同构。

设计要点（沿用安卓端的判断）：
- 重要性不能只信模型给的分：模型判断 0.55 权重 + 结构信号 0.60 权重，取融合后较大值
- 新人物关系对齐顺序：已有角色 id → 本批次新人姓名 → 已有角色姓名；解析不出丢弃并记日志
- 消息闭塞：每个角色独立会话，system prompt 只出现该角色自己的关系
"""
import json
import random
import re

import chat_protocol
import llm
import prompts
import vision as vision_mod
from kcore import new_id, now_ms
from store import RELATION_KINDS

MODEL_WEIGHT = 0.55
STRUCTURE_WEIGHT = 0.60
DEFAULT_PROPOSED = 45
HISTORY_TURNS = 24

IMPORTANCE_META = {
    "LEAD": {"label": "核心", "tier": "PREMIUM", "chatEnabled": True},
    "MAJOR": {"label": "重要", "tier": "STANDARD", "chatEnabled": True},
    "SUPPORTING": {"label": "配角", "tier": "ECONOMY", "chatEnabled": True},
    "MINOR": {"label": "次要", "tier": "ECONOMY", "chatEnabled": False},
    "EXTRA": {"label": "路人", "tier": "ECONOMY", "chatEnabled": False},
}

TIER_LABEL = {"PREMIUM": "旗舰", "STANDARD": "标准", "ECONOMY": "经济"}


def importance_of_score(score):
    if score >= 85:
        return "LEAD"
    if score >= 65:
        return "MAJOR"
    if score >= 45:
        return "SUPPORTING"
    if score >= 25:
        return "MINOR"
    return "EXTRA"


def final_score(proposed_by_model, relations, tagged_by_user=False, plot_mentions=0):
    model = max(0, min(100, proposed_by_model))
    structure = 0.0
    structure += min(len(relations), 4) * 11.0
    strong = sum(1 for r in relations if (r.get("intensity") or 0) >= 70)
    structure += min(strong, 2) * 9.0
    if tagged_by_user:
        structure += 22.0
    structure += min(plot_mentions, 3) * 6.0
    if relations and all(r.get("kind") == "ACQUAINTANCE" for r in relations):
        structure *= 0.7
    blended = model * MODEL_WEIGHT + min(structure, 100.0) * STRUCTURE_WEIGHT
    return int(max(0.0, min(100.0, blended)))


def tokens_estimate(text):
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        cp = ord(ch)
        if 0x2E80 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF or 0xFF00 <= cp <= 0xFFEF:
            cjk += 1
        else:
            other += 1
    return max(1, int(cjk * 0.7 + other / 4.0))


def extract_json_block(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        end = text.rfind("```")
        if end >= 0:
            text = text[:end]
    text = text.strip()
    start = -1
    for idx, ch in enumerate(text):
        if ch in "{[":
            start = idx
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


def make_log(kind, actor, title, detail="", model_label="", tokens_in=0, tokens_out=0,
             cost_usd=0.0, ref_msg_id=None):
    return {"id": new_id("log"), "ts": now_ms(), "kind": kind, "actor": actor, "title": title,
            "detail": detail, "modelLabel": model_label, "tokensIn": tokens_in,
            "tokensOut": tokens_out, "costUsd": cost_usd, "refMsgId": ref_msg_id}


def model_ref_display(ref):
    if not ref:
        return ""
    return ref.get("label") or ref.get("modelId") or ""


# ── 模型解析器 ──────────────────────────────────────────────────────────────

def resolve_model(catalog, settings, tier, require_vision=False, preferred_vendor=None):
    """按档位挑一个用户可用的模型；必须限定在已配好 Key 的厂商范围内。"""
    configured = {}
    for ep in settings.state.get("endpoints") or []:
        if ep.get("kind", "LLM") == "LLM":
            configured[ep.get("vendor")] = ep
    if not configured:
        return None

    order = []
    if preferred_vendor and preferred_vendor in configured:
        order.append(preferred_vendor)
    saved = settings.state.get("savedModels") or []
    if saved:
        v = saved[0].get("vendor")
        if v and v in configured and v not in order:
            order.append(v)
    for ep in settings.state.get("endpoints") or []:
        if ep.get("kind", "LLM") == "LLM" and ep.get("vendor") not in order:
            order.append(ep.get("vendor"))

    for vendor in order:
        endpoint = configured.get(vendor)
        if not endpoint:
            continue
        picked = catalog.pick_for_tier(tier, require_vision, vendor_key=vendor)
        if picked:
            return {"endpointId": endpoint.get("id"), "modelId": picked["id"],
                    "label": picked["name"], "vendor": picked["vendorKey"]}

    endpoint_ids = {e.get("id") for e in settings.state.get("endpoints") or []}
    for m in saved:
        if m.get("endpointId") in endpoint_ids:
            return m
    return None


# ── 旁白引擎 ────────────────────────────────────────────────────────────────

def narrator_advance(store, catalog, settings, bundle, user_hint="", need_new_npc=False, max_new_npcs=2):
    """旁白推进剧情。返回 outcome dict；持久化由调用方负责。"""
    society = bundle["society"]
    resolved = settings.resolve(society.get("narratorModel"))
    if not resolved:
        return {"ok": False, "error": "还没有给旁白配置模型。请到「设置 → 模型配置」里为这个社会指定旁白使用的模型。",
                "narrative": "", "newCharacters": [], "newRelations": [], "plot": bundle["plot"],
                "logs": [], "inputTokens": 0, "outputTokens": 0, "costUsd": 0.0}
    endpoint, ref = resolved

    system = prompts.narrator_system(society, bundle["characters"], bundle["plot"])
    task = prompts.narrator_task(user_hint, need_new_npc, max_new_npcs)
    result = llm.complete(endpoint, ref["modelId"],
                          [{"role": "system", "content": system}, {"role": "user", "content": task}],
                          temperature=0.9, max_tokens=3000, json_mode=True)

    logs = []
    if result["error"]:
        logs.append(make_log("NARRATOR", "旁白", "推进剧情失败", detail=result["error"],
                             model_label=model_ref_display(ref),
                             tokens_in=result["inputTokens"], tokens_out=result["outputTokens"]))
        return {"ok": False, "error": result["error"], "narrative": "",
                "newCharacters": [], "newRelations": [], "plot": bundle["plot"], "logs": logs,
                "inputTokens": result["inputTokens"], "outputTokens": result["outputTokens"],
                "costUsd": 0.0}

    js = extract_json_block(result["text"])
    if not js:
        return {"ok": False, "error": "旁白返回的内容不是合法 JSON，无法解析剧情推进结果。",
                "narrative": "", "newCharacters": [], "newRelations": [], "plot": bundle["plot"],
                "logs": logs, "inputTokens": result["inputTokens"],
                "outputTokens": result["outputTokens"], "costUsd": 0.0}
    try:
        root = json.loads(js)
    except ValueError as e:
        return {"ok": False, "error": f"旁白返回的 JSON 解析失败：{e}",
                "narrative": "", "newCharacters": [], "newRelations": [], "plot": bundle["plot"],
                "logs": logs, "inputTokens": result["inputTokens"],
                "outputTokens": result["outputTokens"], "costUsd": 0.0}

    if not isinstance(root, dict):
        root = {}

    cost = catalog.estimate_cost_usd(ref["modelId"], result["inputTokens"], result["outputTokens"])
    narrative = root.get("narrative") or ""
    logs.append(make_log("NARRATOR", "旁白", "推进了剧情", detail=narrative,
                         model_label=model_ref_display(ref),
                         tokens_in=result["inputTokens"], tokens_out=result["outputTokens"],
                         cost_usd=cost))

    # 4. 新人物
    pending, char_logs = _build_new_characters(root, bundle, settings, catalog, ref)
    logs.extend(char_logs)

    # 5. 关系
    relations, rel_logs = _build_relations(root, bundle, pending, settings)
    logs.extend(rel_logs)

    # 6. 回填分数
    scored = []
    for p in pending:
        c = p["character"]
        rels = [r for r in relations if r["fromId"] == c["id"] or r["toId"] == c["id"]]
        score = final_score(p["importanceScoreHint"], rels, tagged_by_user=bool(c.get("tags")))
        c = dict(c)
        c["importance"] = importance_of_score(score)
        scored.append(c)

    # 7. 剧情状态
    plot = _merge_plot(root, bundle["plot"], scored)

    return {"ok": True, "error": "", "narrative": narrative, "plot": plot,
            "newCharacters": scored, "newRelations": relations, "logs": logs,
            "inputTokens": result["inputTokens"], "outputTokens": result["outputTokens"],
            "costUsd": cost}


def _build_new_characters(root, bundle, settings, catalog, narrator_ref):
    arr = root.get("newCharacters")
    if not isinstance(arr, list) or not arr:
        return [], []
    out, logs = [], []
    for o in arr:
        if not isinstance(o, dict):
            continue
        name = (o.get("name") or "").strip()
        if not name:
            continue
        try:
            proposed = int(o.get("importanceScore", DEFAULT_PROPOSED))
        except (TypeError, ValueError):
            proposed = DEFAULT_PROPOSED
        proposed = max(0, min(100, proposed))
        reason = o.get("importanceReason") or ""

        specs = []
        for r in o.get("relations") or []:
            if not isinstance(r, dict):
                continue
            target = (r.get("toCharacterId") or "").strip()
            if not target:
                continue
            try:
                intensity = max(0, min(100, int(r.get("intensity", 50))))
            except (TypeError, ValueError):
                intensity = 50
            kind = r.get("kind") or "ACQUAINTANCE"
            specs.append({"targetKey": target, "kind": kind if kind in RELATION_KINDS else "ACQUAINTANCE",
                          "customLabel": r.get("customLabel") or "", "intensity": intensity,
                          "note": r.get("note") or ""})

        imp = importance_of_score(proposed)
        tier = IMPORTANCE_META[imp]["tier"]
        if settings.state.get("narratorAutoAssignModel", True):
            model = resolve_model(catalog, settings, tier, preferred_vendor=(narrator_ref or {}).get("vendor"))
        else:
            model = bundle["society"].get("defaultCharacterModel")

        now = now_ms()
        char = {
            "id": new_id("chr"), "name": name, "alias": o.get("alias") or "",
            "gender": o.get("gender") or "UNKNOWN", "age": o.get("age") or "",
            "oneLiner": o.get("oneLiner") or "", "personality": o.get("personality") or "",
            "background": o.get("background") or "", "appearance": o.get("appearance") or "",
            "speechStyle": o.get("speechStyle") or "", "openingLine": "",
            "avatarUrl": "", "importance": imp, "model": model, "tags": [],
            "isUser": False, "isGenerated": True, "createdAt": now, "updatedAt": now,
        }
        out.append({"character": char, "importanceScoreHint": proposed, "relationSpecs": specs})

        tier_label = TIER_LABEL[tier]
        detail_lines = [o.get("oneLiner") or ""]
        if reason:
            detail_lines.append(f"重要性判断依据：{reason}")
        detail_lines.append(f"拟定档位：{tier_label}")
        detail_lines.append(f"分配模型：{model_ref_display(model) or '未配置（可在人物详情里手动指定）'}")
        logs.append(make_log("NARRATOR", "旁白", f"引入了新人物「{name}」",
                             detail="\n".join(detail_lines), model_label=model_ref_display(narrator_ref)))
    return out, logs


def _build_relations(root, bundle, pending, settings):
    out = []
    logs = []
    characters = bundle["characters"]
    by_id = {c["id"]: c for c in characters}
    by_name = {c["name"]: c for c in characters}
    new_by_name = {p["character"]["name"]: p for p in pending}

    for p in pending:
        self_c = p["character"]
        for spec in p["relationSpecs"]:
            target = None
            t = by_id.get(spec["targetKey"])
            if not t:
                np = new_by_name.get(spec["targetKey"])
                t = np["character"] if np else None
            if not t:
                t = by_name.get(spec["targetKey"])
            if t is None:
                logs.append(make_log(
                    "NARRATOR", "旁白", "丢弃了一条无法解析的关系",
                    detail=f"「{self_c['name']}」→「{spec['targetKey']}」：找不到对应的人物，"
                           "可能是旁白编造了一个不存在的人。这条连线已跳过。"))
                continue
            if t["id"] == self_c["id"]:
                continue
            exists = any((r["fromId"] == self_c["id"] and r["toId"] == t["id"]) or
                         (r["toId"] == self_c["id"] and r["fromId"] == t["id"]) for r in out) or \
                any((r["fromId"] == self_c["id"] and r["toId"] == t["id"]) or
                    (r["toId"] == self_c["id"] and r["fromId"] == t["id"]) for r in bundle["relations"])
            if exists:
                continue
            out.append({"id": new_id("rel"), "fromId": self_c["id"], "toId": t["id"],
                        "kind": spec["kind"], "kindLabel": RELATION_KINDS[spec["kind"]][0],
                        "customLabel": spec["customLabel"], "intensity": spec["intensity"],
                        "note": spec["note"], "createdAt": now_ms()})

        if settings.state.get("narratorAutoLinkRelations", True) and \
                not any(r["fromId"] == self_c["id"] or r["toId"] == self_c["id"] for r in out):
            logs.append(make_log(
                "NARRATOR", "旁白", f"新人物「{self_c['name']}」没有接上任何关系",
                detail="旁白没有为 TA 指定有效的关系，这个人现在在关系图上是孤立的。"
                       "可以在人物详情里手动补一条连线，或让旁白重新生成。"))
    return out, logs


def _merge_plot(root, old, new_chars):
    upd = root.get("plotUpdate") if isinstance(root.get("plotUpdate"), dict) else {}
    beats = []
    for b in root.get("beats") or []:
        if not isinstance(b, dict):
            continue
        title = (b.get("title") or "").strip()
        if not title:
            continue
        actor_raw = b.get("actorId")
        actor_id = actor_raw
        for c in new_chars:
            if c.get("name") == actor_raw:
                actor_id = c["id"]
                break
        beats.append({"ts": now_ms(), "title": title, "detail": b.get("detail") or "",
                      "actorId": actor_id, "automatic": True})
    hooks = [h for h in (root.get("hooks") or []) if isinstance(h, str) and h] or old.get("hooks", [])

    def nonempty(key, fallback):
        v = upd.get(key) or ""
        return v if v else fallback

    return {
        "act": upd.get("act", root.get("act", old.get("act", 1))) if upd else old.get("act", 1),
        "title": nonempty("title", old.get("title", "序章")),
        "summary": nonempty("summary", old.get("summary", "")),
        "mood": nonempty("mood", old.get("mood", "")),
        "hooks": hooks,
        "beats": (old.get("beats", []) + beats)[-60:],
        "updatedAt": now_ms(),
    }


# ── 人物智能体 ──────────────────────────────────────────────────────────────

def character_reply_generator(store, catalog, settings, bundle, speaker, user, thread,
                              user_text, attachment=""):
    """人物回复的事件生成器。yield 事件 dict：
    {"type":"started"} / {"type":"delta","buffer":...} / {"type":"vision_used","description":...}
    / {"type":"done","message":...,"log":...} / {"type":"failed","error":...,"log":...}
    """
    society = bundle["society"]
    ref = speaker.get("model") or society.get("defaultCharacterModel")
    resolved = settings.resolve(ref)
    if not resolved:
        msg = (f"「{speaker.get('name')}」还没有分配模型，也没有设置社会默认模型。"
               "请到人物详情或设置里指定。")
        yield {"type": "failed", "error": msg, "log": make_log("CHARACTER", speaker.get("name", ""), "回复失败", detail=msg)}
        return
    endpoint, model_ref = resolved

    yield {"type": "started"}

    catalog_model = catalog.find(model_ref["modelId"])
    model_supports_vision = bool(catalog_model and catalog_model.get("supportsVision"))

    effective_text = user_text
    image_for_model = []
    user_name = (user or {}).get("name") or "对方"

    if attachment:
        if model_supports_vision:
            path = store.resolve_media(society["id"], attachment)
            image_for_model = [path or attachment]
        elif settings.state.get("visionEnabled"):
            path = store.resolve_media(society["id"], attachment)
            described, err = vision_mod.describe(settings, path or attachment, vision_mod.CHAT_QUESTION)
            if described:
                yield {"type": "vision_used", "description": described}
                effective_text = vision_mod.as_injection(described, user_name) + \
                    (("\n\n" + user_text) if (user_text or "").strip() else "")
        else:
            effective_text = user_text + ("\n\n" if user_text else "") + \
                "[对方发来了一张图片，但你当前的模型不支持看图，视觉桥接也未开启，" \
                "所以你看不到这张图。请自然地表示你没看清，不要编造图片内容。]"

    system = prompts.character_system(
        society=society, self_c=speaker, user=user,
        relations=[r for r in bundle["relations"]
                   if r.get("fromId") == speaker["id"] or r.get("toId") == speaker["id"]],
        all_characters=bundle["characters"], recent=[],
        sticker_library=bundle.get("stickers") or [])

    history = [m for m in thread["messages"]
               if m.get("status") == "DONE" and m.get("role") != "SYSTEM"][-HISTORY_TURNS:]

    turns = [{"role": "system", "content": system}]
    for m in history:
        role = m.get("role")
        if role == "USER":
            text = chat_protocol.protocol_text(m.get("segments", [])) or \
                chat_protocol.plain_text(m.get("segments", []))
            turns.append({"role": "user", "content": text})
        elif role == "CHARACTER":
            turns.append({"role": "assistant", "content": m.get("raw") or
                          chat_protocol.plain_text(m.get("segments", []))})
        elif role == "NARRATOR":
            turns.append({"role": "user", "content": "（旁白）" + chat_protocol.plain_text(m.get("segments", []))})

    turns.append({"role": "user", "content": effective_text, "images": image_for_model})

    sb = []
    in_tok = out_tok = 0
    usage_reported = False
    failure = None
    try:
        for ev in llm.stream_chat(endpoint, model_ref["modelId"], turns,
                                  temperature=0.95, max_tokens=1500):
            if ev["type"] == "delta":
                sb.append(ev["text"])
                yield {"type": "delta", "buffer": "".join(sb)}
            elif ev["type"] == "usage":
                in_tok, out_tok = ev["inputTokens"], ev["outputTokens"]
                usage_reported = True
    except Exception as e:
        failure = llm.friendly_error(e) if not isinstance(e, RuntimeError) else str(e)

    raw = "".join(sb).strip()

    if failure and not raw:
        yield {"type": "failed", "error": failure,
               "log": make_log("CHARACTER", speaker.get("name", ""), "回复失败",
                               detail=failure, model_label=model_ref_display(model_ref))}
        return

    estimated = not usage_reported
    if estimated:
        in_tok = tokens_estimate("".join(t["content"] for t in turns) + str(len(image_for_model)))
        out_tok = tokens_estimate(raw)
    cost = catalog.estimate_cost_usd(model_ref["modelId"], in_tok, out_tok)

    segments = chat_protocol.parse(raw)
    message = {
        "id": new_id("msg"), "role": "CHARACTER", "charId": speaker["id"],
        "segments": segments, "raw": raw, "ts": now_ms(),
        "status": "DONE" if not failure else "FAILED",
        "modelLabel": model_ref_display(model_ref), "tokensIn": in_tok, "tokensOut": out_tok,
        "costUsd": cost, "error": failure or "", "attachment": attachment,
    }

    detail_lines = [f"模型：{model_ref_display(model_ref)}"]
    if attachment:
        detail_lines.append("收到图片：" + ("直接多模态识别" if model_supports_vision else "经视觉桥接转述"))
    detail_lines.append(f"发送：{user_text or '（仅图片）'}")
    detail_lines.append(f"回复：{raw}")
    if estimated:
        detail_lines.append("（token 为估算值，该厂商未返回用量）")
    log = make_log("CHARACTER", speaker.get("name", ""), "回复了消息" if not failure else "回复失败",
                   detail="\n".join(detail_lines), model_label=model_ref_display(model_ref),
                   tokens_in=in_tok, tokens_out=out_tok, cost_usd=cost, ref_msg_id=message["id"])

    if failure:
        yield {"type": "failed", "error": failure, "log": log}
    else:
        yield {"type": "done", "message": message, "log": log, "costUsd": cost}


def god_dialogue_generator(store, catalog, settings, bundle, speaker, listener, topic):
    """上帝视角：让两个 NPC 之间对话。与用户对话共用同一套人格逻辑。"""
    rel = next((r for r in bundle["relations"]
                if r.get("fromId") == listener["id"] or r.get("toId") == listener["id"]), None)
    label = ""
    if rel:
        label = rel.get("customLabel") or rel.get("kindLabel") or rel.get("kind", "")
        if rel.get("note"):
            label += f"（{rel['note']}）"
    opening_lines = [
        f"（你现在在和「{listener['name']}」说话，不是在和用户说话。）",
        "对方与你的关系：",
        f"  {label}" if label else "  尚无明确关系，按初次接触处理。",
        "",
        f"话题：{topic}",
    ]
    fresh_thread = {"charId": speaker["id"], "messages": [], "updatedAt": 0}
    return character_reply_generator(store, catalog, settings, bundle, speaker, listener,
                                     fresh_thread, "\n".join(opening_lines))
