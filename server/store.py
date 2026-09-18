# -*- coding: utf-8 -*-
"""社会仓储 —— 每个社会一个独立文件夹，物理隔离；JSON 结构与安卓端逐字段兼容。

目录布局（与安卓端一致）：
  data/societies/
    index.json
    {societyId}/society.json / characters.json / relations.json / plot.json
    {societyId}/chats/{charId}.json
    {societyId}/logs.jsonl / stickers.json / layout.json / media/

存档 schema：kith.society/1（*.kith.json），双端可直接互导。
写入一律先写 .tmp 再 rename（writeAtomic）。
"""
import json
import os
import shutil

from kcore import new_id, now_ms, safe_file_name

ARCHIVE_SCHEMA = "kith.society/1"
APP_VERSION = "Kith Desktop 0.1.0"

ORIENTATION_META = {
    "BG": {"code": "bg", "label": "异性向"}, "BL": {"code": "bl", "label": "耽美向"},
    "GL": {"code": "gl", "label": "百合向"}, "BZ": {"code": "bz", "label": "无 CP"},
    "CUSTOM": {"code": "custom", "label": "自定义"},
}
ORIENTATION_BY_NAME = {name: meta for name, meta in ORIENTATION_META.items()}
ORIENTATION_LABEL_TO_NAME = {meta["label"]: name for name, meta in ORIENTATION_META.items()}

RELATION_KINDS = {
    "FAMILY": ("亲属", True), "LOVER": ("恋人", True), "SPOUSE": ("伴侣", True),
    "FRIEND": ("朋友", True), "BEST_FRIEND": ("挚友", True), "RIVAL": ("对手", True),
    "ENEMY": ("宿敌", True), "COLLEAGUE": ("同事", True), "CLASSMATE": ("同学", True),
    "SUPERIOR": ("上司", False), "SUBORDINATE": ("下属", False), "MENTOR": ("师长", False),
    "STUDENT": ("学生", False), "NEIGHBOR": ("邻里", True), "ACQUAINTANCE": ("点头之交", True),
    "CUSTOM": ("自定义", True),
}


# ── 安全读取（缺字段不崩、多字段忽略，与安卓端 Codecs 语义一致）─────────────

def s(o, k, d=""):
    v = o.get(k)
    return d if v is None else (v if isinstance(v, str) else str(v))


def so(o, k):
    v = o.get(k)
    return v if isinstance(v, str) and v else None


def i(o, k, d=0):
    v = o.get(k, d)
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def lnum(o, k, d=0):
    return i(o, k, d)


def dnum(o, k, d=0.0):
    v = o.get(k, d)
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def b(o, k, d=False):
    v = o.get(k, d)
    if isinstance(v, bool):
        return v
    if v is None:
        return d
    return bool(v)


def str_list(o, k):
    v = o.get(k)
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, str) and x]


# ── 领域 ↔ JSON ─────────────────────────────────────────────────────────────

def model_ref_json(ref):
    if not ref:
        return None
    return {"endpointId": ref.get("endpointId", ""), "modelId": ref.get("modelId", ""),
            "label": ref.get("label", ""), "vendor": ref.get("vendor", "")}


def to_model_ref(o):
    if not isinstance(o, dict):
        return None
    return {"endpointId": s(o, "endpointId"), "modelId": s(o, "modelId"),
            "label": s(o, "label"), "vendor": s(o, "vendor")}


def _norm_cover_image(o):
    """兼容读封面：新字段 coverImage（media 文件名）；旧桌面字段 coverUrl（media/xxx 引用）→ 剥前缀。"""
    cv = s(o, "coverImage")
    if cv:
        return cv.split("/")[-1]
    old = s(o, "coverUrl")
    if old.startswith("media/"):
        return old.split("/")[-1]
    return old if old.startswith(("http://", "https://", "data:")) else ""


def society_img_of(soc):
    """读社会的封面文件名（兼容旧 coverUrl 引用）。"""
    cv = soc.get("coverImage") or ""
    if cv:
        return cv.split("/")[-1]
    old = soc.get("coverUrl") or ""
    return old.split("/")[-1] if old.startswith("media/") else ""


def to_society(o):
    ori = s(o, "orientation", "BG")
    if ori not in ORIENTATION_META:
        # 兼容存了 code（bg/bl/gl/bz/custom）的写法
        rev = {"bg": "BG", "bl": "BL", "gl": "GL", "bz": "BZ", "custom": "CUSTOM"}
        ori = rev.get(ori.lower(), "BG")
    meta = ORIENTATION_META[ori]
    return {
        "id": s(o, "id"), "name": s(o, "name", "未命名社会"),
        "worldSetting": s(o, "worldSetting"),
        "orientation": ori,
        "orientationCode": meta["code"], "orientationLabel": meta["label"],
        "plotDirection": s(o, "plotDirection"),
        "tropes": str_list(o, "tropes"),
        "coverSeed": i(o, "coverSeed"),
        "coverImage": _norm_cover_image(o),
        "narratorModel": to_model_ref(o.get("narratorModel")) if isinstance(o.get("narratorModel"), dict) else None,
        "defaultCharacterModel": to_model_ref(o.get("defaultCharacterModel")) if isinstance(o.get("defaultCharacterModel"), dict) else None,
        "imageModel": to_model_ref(o.get("imageModel")) if isinstance(o.get("imageModel"), dict) else None,
        "createdAt": lnum(o, "createdAt"), "updatedAt": lnum(o, "updatedAt"),
        "archived": b(o, "archived"), "version": i(o, "version", 1),
    }


def society_json(soc):
    return {
        "id": soc["id"], "name": soc["name"], "worldSetting": soc.get("worldSetting", ""),
        "orientation": soc.get("orientation", "BG"),
        "plotDirection": soc.get("plotDirection", ""),
        "tropes": soc.get("tropes", []), "coverSeed": soc.get("coverSeed", 0),
        "coverImage": soc.get("coverImage", ""),
        "narratorModel": model_ref_json(soc.get("narratorModel")),
        "defaultCharacterModel": model_ref_json(soc.get("defaultCharacterModel")),
        "imageModel": model_ref_json(soc.get("imageModel")),
        "createdAt": soc.get("createdAt", 0), "updatedAt": soc.get("updatedAt", 0),
        "archived": soc.get("archived", False), "version": soc.get("version", 1),
    }


def to_character(o):
    tags = []
    for t in o.get("tags") or []:
        if isinstance(t, dict) and t.get("label"):
            tags.append({"label": s(t, "label"), "hint": s(t, "hint"), "builtin": b(t, "builtin", True)})
    model = to_model_ref(o.get("model")) if isinstance(o.get("model"), dict) else None
    return {
        "id": s(o, "id"), "name": s(o, "name", "无名"), "alias": s(o, "alias"),
        "gender": s(o, "gender", "UNKNOWN"), "age": s(o, "age"),
        "oneLiner": s(o, "oneLiner"), "personality": s(o, "personality"),
        "background": s(o, "background"), "appearance": s(o, "appearance"),
        "speechStyle": s(o, "speechStyle"), "openingLine": s(o, "openingLine"),
        "avatarUrl": s(o, "avatarUrl"), "importance": s(o, "importance", "SUPPORTING"),
        "model": model, "tags": tags,
        "isUser": b(o, "isUser"), "isGenerated": b(o, "isGenerated"),
        "createdAt": lnum(o, "createdAt"), "updatedAt": lnum(o, "updatedAt"),
    }


def character_json(c):
    return {
        "id": c["id"], "name": c.get("name", ""), "alias": c.get("alias", ""),
        "gender": c.get("gender", "UNKNOWN"), "age": c.get("age", ""),
        "oneLiner": c.get("oneLiner", ""), "personality": c.get("personality", ""),
        "background": c.get("background", ""), "appearance": c.get("appearance", ""),
        "speechStyle": c.get("speechStyle", ""), "openingLine": c.get("openingLine", ""),
        "avatarUrl": c.get("avatarUrl", ""), "importance": c.get("importance", "SUPPORTING"),
        "model": model_ref_json(c.get("model")),
        "tags": [{"label": t["label"], "hint": t.get("hint", ""), "builtin": t.get("builtin", True)}
                 for t in c.get("tags", [])],
        "isUser": c.get("isUser", False), "isGenerated": c.get("isGenerated", False),
        "createdAt": c.get("createdAt", 0), "updatedAt": c.get("updatedAt", 0),
    }


def to_relation(o):
    kind = s(o, "kind", "ACQUAINTANCE")
    if kind not in RELATION_KINDS:
        kind = "ACQUAINTANCE"
    intensity = i(o, "intensity", 50)
    return {
        "id": s(o, "id"), "fromId": s(o, "fromId"), "toId": s(o, "toId"),
        "kind": kind, "kindLabel": RELATION_KINDS[kind][0],
        "customLabel": s(o, "customLabel"),
        "intensity": max(0, min(100, intensity)), "note": s(o, "note"),
        "createdAt": lnum(o, "createdAt"),
    }


def relation_json(r):
    return {
        "id": r["id"], "fromId": r.get("fromId", ""), "toId": r.get("toId", ""),
        "kind": r.get("kind", "ACQUAINTANCE"), "customLabel": r.get("customLabel", ""),
        "intensity": r.get("intensity", 50), "note": r.get("note", ""),
        "createdAt": r.get("createdAt", 0),
    }


def to_message(o):
    segments = []
    for sg in o.get("segments") or []:
        if not isinstance(sg, dict):
            continue
        t = s(sg, "type")
        if t == "text":
            segments.append({"type": "text", "content": s(sg, "content")})
        elif t == "sticker":
            segments.append({"type": "sticker", "emotion": s(sg, "emotion"), "stickerId": s(sg, "stickerId")})
        elif t == "picture":
            state = s(sg, "state", "READY")
            segments.append({"type": "picture", "url": s(sg, "url"), "prompt": s(sg, "prompt"),
                             "searchQuery": s(sg, "searchQuery"), "style": s(sg, "style"),
                             "ratio": s(sg, "ratio"), "caption": s(sg, "caption"),
                             "state": state if state in ("READY", "GENERATING", "FAILED") else "READY"})
        elif t == "transfer":
            segments.append({"type": "transfer", "amount": dnum(sg, "amount"),
                             "to": s(sg, "to"), "note": s(sg, "note"), "confirmed": b(sg, "confirmed")})
    status = s(o, "status", "DONE")
    return {
        "id": s(o, "id"), "role": s(o, "role", "CHARACTER"),
        "charId": so(o, "charId"), "segments": segments, "raw": s(o, "raw"),
        "ts": lnum(o, "ts"), "status": status if status in ("PENDING", "STREAMING", "DONE", "FAILED") else "DONE",
        "modelLabel": s(o, "modelLabel"), "tokensIn": i(o, "tokensIn"), "tokensOut": i(o, "tokensOut"),
        "costUsd": dnum(o, "costUsd"), "error": s(o, "error"), "attachment": s(o, "attachment"),
    }


def message_json(m):
    return {
        "id": m["id"], "role": m.get("role", "CHARACTER"), "charId": m.get("charId"),
        "segments": m.get("segments", []), "raw": m.get("raw", ""), "ts": m.get("ts", 0),
        "status": m.get("status", "DONE"), "modelLabel": m.get("modelLabel", ""),
        "tokensIn": m.get("tokensIn", 0), "tokensOut": m.get("tokensOut", 0),
        "costUsd": m.get("costUsd", 0.0), "error": m.get("error", ""),
        "attachment": m.get("attachment", ""),
    }


def to_plot(o):
    if not isinstance(o, dict):
        o = {}
    beats = []
    for bt in o.get("beats") or []:
        if isinstance(bt, dict):
            beats.append({"ts": lnum(bt, "ts"), "title": s(bt, "title"), "detail": s(bt, "detail"),
                          "actorId": so(bt, "actorId"), "automatic": b(bt, "automatic")})
    return {
        "act": i(o, "act", 1), "title": s(o, "title", "序章"), "summary": s(o, "summary"),
        "mood": s(o, "mood"), "hooks": str_list(o, "hooks"), "beats": beats,
        "updatedAt": lnum(o, "updatedAt"),
    }


def plot_json(p):
    return {"act": p.get("act", 1), "title": p.get("title", "序章"), "summary": p.get("summary", ""),
            "mood": p.get("mood", ""), "hooks": p.get("hooks", []),
            "beats": p.get("beats", []), "updatedAt": p.get("updatedAt", 0)}


def to_sticker(o):
    return {"id": s(o, "id"), "name": s(o, "name"), "imageUrl": s(o, "imageUrl"),
            "emotions": str_list(o, "emotions"), "source": s(o, "source", "system_default"),
            "usageCount": i(o, "usageCount"), "createdAt": lnum(o, "createdAt")}


def sticker_json(st):
    return {"id": st["id"], "name": st.get("name", ""), "imageUrl": st.get("imageUrl", ""),
            "emotions": st.get("emotions", []), "source": st.get("source", "system_default"),
            "usageCount": st.get("usageCount", 0), "createdAt": st.get("createdAt", 0)}


def to_log(o):
    kind = s(o, "kind", "SYSTEM")
    return {"id": s(o, "id"), "ts": lnum(o, "ts"), "kind": kind, "actor": s(o, "actor"),
            "title": s(o, "title"), "detail": s(o, "detail"), "modelLabel": s(o, "modelLabel"),
            "tokensIn": i(o, "tokensIn"), "tokensOut": i(o, "tokensOut"),
            "costUsd": dnum(o, "costUsd"), "refMsgId": so(o, "refMsgId")}


def log_json(e):
    return {"id": e["id"], "ts": e.get("ts", 0), "kind": e.get("kind", "SYSTEM"),
            "actor": e.get("actor", ""), "title": e.get("title", ""), "detail": e.get("detail", ""),
            "modelLabel": e.get("modelLabel", ""), "tokensIn": e.get("tokensIn", 0),
            "tokensOut": e.get("tokensOut", 0), "costUsd": e.get("costUsd", 0.0),
            "refMsgId": e.get("refMsgId")}


# ── 仓储 ────────────────────────────────────────────────────────────────────

class SocietyStore:
    def __init__(self, root: str):
        self.root = root

    def society_dir(self, sid):
        return os.path.join(self.root, sid)

    def media_dir(self, sid):
        d = os.path.join(self.society_dir(sid), "media")
        os.makedirs(d, exist_ok=True)
        return d

    def save_media(self, sid, data: bytes, ext="png") -> str:
        """保存图片到社会自己的 media 目录，返回『media/文件名』相对引用。"""
        d = self.media_dir(sid)
        name = f"img_{now_ms()}_{new_id('s').split('_')[-1]}.{ext or 'png'}"
        with open(os.path.join(d, name), "wb") as f:
            f.write(data)
        return f"media/{name}"

    def resolve_media(self, sid, ref: str):
        """把 media/xxx 引用解析为磁盘绝对路径；其余返回 None。"""
        if ref and ref.startswith("media/"):
            p = os.path.join(self.society_dir(sid), ref.replace("/", os.sep))
            return p if os.path.exists(p) else None
        return None

    # ── 索引 ──
    def _index_file(self):
        return os.path.join(self.root, "index.json")

    def list(self):
        raw = self._read_text(self._index_file())
        if not raw:
            return []
        try:
            arr = json.loads(raw)
        except ValueError:
            return []
        out = []
        for o in arr if isinstance(arr, list) else []:
            try:
                if not os.path.isdir(self.society_dir(s(o, "id"))):
                    continue  # 幽灵条目
                out.append({
                    "id": s(o, "id"), "name": s(o, "name"),
                    "orientationCode": s(o, "orientationCode", "bg"),
                    "orientationLabel": s(o, "orientationLabel"),
                    "characterCount": i(o, "characterCount"),
                    "relationCount": i(o, "relationCount"),
                    "updatedAt": lnum(o, "updatedAt"),
                    "coverSeed": i(o, "coverSeed"),
                    "coverImage": s(o, "coverImage"),
                    "archived": b(o, "archived"),
                })
            except Exception:
                continue
        out.sort(key=lambda x: -x["updatedAt"])
        return out

    def _refresh_index(self, summary, remove=False):
        existing = [x for x in self.list() if x["id"] != summary["id"]]
        if not remove:
            existing.append(summary)
        os.makedirs(self.root, exist_ok=True)
        self._write_atomic(self._index_file(), json.dumps(existing, ensure_ascii=False))

    def _bump_index(self, sid):
        dirp = self.society_dir(sid)
        soc_o = self._read_json(os.path.join(dirp, "society.json"))
        if not soc_o:
            return
        soc = to_society(soc_o)
        chars = self._read_array(os.path.join(dirp, "characters.json"))
        rels = self._read_array(os.path.join(dirp, "relations.json"))
        self._refresh_index({
            "id": soc["id"], "name": soc["name"],
            "orientationCode": soc["orientationCode"], "orientationLabel": soc["orientationLabel"],
            "characterCount": len(chars), "relationCount": len(rels),
            "updatedAt": now_ms(), "coverSeed": soc["coverSeed"],
            "coverImage": soc.get("coverImage", ""),
            "archived": soc["archived"],
        })

    # ── 读写 ──
    def load(self, sid):
        dirp = self.society_dir(sid)
        if not os.path.isdir(dirp):
            return None
        soc_o = self._read_json(os.path.join(dirp, "society.json"))
        if not soc_o:
            return None
        society = to_society(soc_o)
        characters = [to_character(c) for c in self._read_array(os.path.join(dirp, "characters.json"))]
        relations = [to_relation(r) for r in self._read_array(os.path.join(dirp, "relations.json"))]
        plot = to_plot(self._read_json(os.path.join(dirp, "plot.json")) or {})
        stickers = [to_sticker(x) for x in self._read_array(os.path.join(dirp, "stickers.json"))]
        return {"society": society, "characters": characters, "relations": relations,
                "plot": plot, "stickers": stickers}

    def save_society(self, society):
        dirp = self.society_dir(society["id"])
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "society.json"),
                           json.dumps(society_json(society), ensure_ascii=False))
        self._refresh_index(self._summary_of(society, dirp))

    def _summary_of(self, society, dirp):
        chars = self._read_array(os.path.join(dirp, "characters.json"))
        rels = self._read_array(os.path.join(dirp, "relations.json"))
        return {"id": society["id"], "name": society["name"],
                "orientationCode": society["orientationCode"], "orientationLabel": society["orientationLabel"],
                "characterCount": len(chars), "relationCount": len(rels),
                "updatedAt": society.get("updatedAt", now_ms()),
                "coverSeed": society.get("coverSeed", 0),
                "coverImage": society.get("coverImage", ""),
                "archived": society.get("archived", False)}

    def save_characters(self, sid, characters):
        dirp = self.society_dir(sid)
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "characters.json"),
                           json.dumps([character_json(c) for c in characters], ensure_ascii=False))
        self._bump_index(sid)

    def save_relations(self, sid, relations):
        dirp = self.society_dir(sid)
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "relations.json"),
                           json.dumps([relation_json(r) for r in relations], ensure_ascii=False))
        self._bump_index(sid)

    def save_plot(self, sid, plot):
        dirp = self.society_dir(sid)
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "plot.json"),
                           json.dumps(plot_json(plot), ensure_ascii=False))

    def save_stickers(self, sid, stickers):
        dirp = self.society_dir(sid)
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "stickers.json"),
                           json.dumps([sticker_json(x) for x in stickers], ensure_ascii=False))

    # ── 关系图节点位置（layout.json）──
    def load_node_positions(self, sid):
        o = self._read_json(os.path.join(self.society_dir(sid), "layout.json"))
        if not o or not isinstance(o.get("nodes"), dict):
            return {}
        out = {}
        for k, v in o["nodes"].items():
            if isinstance(v, list) and len(v) >= 2:
                try:
                    out[k] = [float(v[0]), float(v[1])]
                except (TypeError, ValueError):
                    continue
        return out

    def save_node_positions(self, sid, positions):
        dirp = self.society_dir(sid)
        os.makedirs(dirp, exist_ok=True)
        self._write_atomic(os.path.join(dirp, "layout.json"),
                           json.dumps({"nodes": positions}, ensure_ascii=False))

    # ── 会话 ──
    def _chat_file(self, sid, cid):
        return os.path.join(self.society_dir(sid), "chats", f"{safe_file_name(cid)}.json")

    def load_thread(self, sid, cid):
        arr = self._read_array(self._chat_file(sid, cid))
        return {"charId": cid, "messages": [to_message(m) for m in arr], "updatedAt": 0}

    def save_thread(self, sid, thread):
        chats = os.path.join(self.society_dir(sid), "chats")
        os.makedirs(chats, exist_ok=True)
        self._write_atomic(
            os.path.join(chats, f"{safe_file_name(thread['charId'])}.json"),
            json.dumps([message_json(m) for m in thread["messages"]], ensure_ascii=False))

    def append_message(self, sid, cid, message):
        thread = self.load_thread(sid, cid)
        thread["messages"].append(message)
        thread["updatedAt"] = message.get("ts", now_ms())
        self.save_thread(sid, thread)

    def update_message(self, sid, cid, message):
        thread = self.load_thread(sid, cid)
        for idx, m in enumerate(thread["messages"]):
            if m["id"] == message["id"]:
                thread["messages"][idx] = message
                break
        self.save_thread(sid, thread)

    def chat_character_ids(self, sid):
        chats = os.path.join(self.society_dir(sid), "chats")
        if not os.path.isdir(chats):
            return set()
        return {os.path.splitext(f)[0] for f in os.listdir(chats) if f.endswith(".json")}

    # ── 日志 ──
    def _log_file(self, sid):
        return os.path.join(self.society_dir(sid), "logs.jsonl")

    def append_log(self, sid, entry):
        os.makedirs(self.society_dir(sid), exist_ok=True)
        try:
            with open(self._log_file(sid), "a", encoding="utf-8") as f:
                f.write(json.dumps(log_json(entry), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def append_logs(self, sid, entries):
        if not entries:
            return
        os.makedirs(self.society_dir(sid), exist_ok=True)
        try:
            with open(self._log_file(sid), "a", encoding="utf-8") as f:
                for e in entries:
                    f.write(json.dumps(log_json(e), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def read_logs(self, sid, limit=300):
        f = self._log_file(sid)
        if not os.path.exists(f):
            return []
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            return []
        out = []
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(to_log(json.loads(line)))
            except ValueError:
                continue
        out.reverse()
        return out

    # ── 删除 ──
    def delete(self, sid):
        self._refresh_index({"id": sid, "name": "", "orientationCode": "bg", "orientationLabel": "",
                             "characterCount": 0, "relationCount": 0, "updatedAt": 0,
                             "coverSeed": 0, "archived": False}, remove=True)
        d = self.society_dir(sid)
        if os.path.isdir(d):
            # Windows 下目录可能被占用（杀毒扫描等），重试几次
            import time
            for attempt in range(5):
                shutil.rmtree(d, ignore_errors=(attempt == 4))
                if not os.path.isdir(d):
                    break
                time.sleep(0.3)

    # ── 导出 / 导入 ──
    def export_archive(self, sid):
        bundle = self.load(sid)
        if not bundle:
            return None
        dirp = self.society_dir(sid)
        chats = {}
        chats_dir = os.path.join(dirp, "chats")
        if os.path.isdir(chats_dir):
            for f in sorted(os.listdir(chats_dir)):
                if f.endswith(".json"):
                    msgs = [to_message(m) for m in self._read_array(os.path.join(chats_dir, f))]
                    if msgs:
                        chats[os.path.splitext(f)[0]] = [message_json(m) for m in msgs]
        logs = []
        lf = self._log_file(sid)
        if os.path.exists(lf):
            with open(lf, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except ValueError:
                            continue
        archive = {
            "schema": ARCHIVE_SCHEMA,
            "exportedAt": now_ms(),
            "appVersion": APP_VERSION,
            "society": society_json(bundle["society"]),
            "characters": [character_json(c) for c in bundle["characters"]],
            "relations": [relation_json(r) for r in bundle["relations"]],
            "plot": plot_json(bundle["plot"]),
            "stickers": [sticker_json(x) for x in bundle["stickers"]],
            "chats": chats,
            "logs": logs,
        }
        # 封面随档同步：与安卓端同约定 —— 顶层 coverImageB64 = 裸 base64（NO_WRAP）
        cover = society_img_of(bundle["society"])
        cover_path = self.resolve_media(sid, "media/" + cover) if cover else None
        if cover_path:
            import base64 as _b64
            with open(cover_path, "rb") as f:
                archive["coverImageB64"] = _b64.b64encode(f.read()).decode("ascii")
        return json.dumps(archive, ensure_ascii=False, indent=2)

    def _normalize_archive(self, raw):
        text = (raw or "").strip()
        if not text:
            raise ValueError("文件是空的，没有可导入的内容")
        if text.startswith("["):
            raise ValueError(
                "这是一份「社会列表索引」，不是可以导入的存档。\n\n"
                "要导入的应该是「导出社会」时生成的 *.kith.json 文件——"
                "它的顶层包含 society、characters、relations、chats 等字段。")
        try:
            obj = json.loads(text)
        except ValueError as e:
            raise ValueError(f"这个文件不是合法的 JSON：{e}")
        if not isinstance(obj, dict):
            raise ValueError("这个文件不是合法的社会存档 JSON")
        if isinstance(obj.get("society"), dict):
            return obj
        looks_like_society = bool(so(obj, "id")) or ("name" in obj and "worldSetting" in obj)
        if looks_like_society:
            return {"society": obj, "characters": [], "relations": [], "plot": {},
                    "stickers": [], "chats": {}, "logs": []}
        raise ValueError(
            "这个 JSON 里找不到社会数据。\n\n"
            "可导入的是「导出社会」生成的存档文件（顶层含 society / characters / relations）。"
            "如果你手上是社会目录里的某个文件，请改用导出的 *.kith.json。")

    def import_archive(self, raw):
        root = self._normalize_archive(raw)
        new_id_ = new_id("soc")
        dirp = self.society_dir(new_id_)
        os.makedirs(dirp, exist_ok=True)

        placeholder = to_society(root["society"])
        id_map = {}
        for c in root.get("characters") or []:
            if isinstance(c, dict) and c.get("id"):
                id_map[s(c, "id")] = new_id("chr")

        society = dict(placeholder)
        society["id"] = new_id_
        society["createdAt"] = now_ms()
        society["updatedAt"] = now_ms()

        # 封面随档同步：coverData(data URI) 落到本机 media；裸 coverUrl 只接受 http/data 远程引用
        src = root["society"] if isinstance(root.get("society"), dict) else {}
        cover_data = src.get("coverData")
        if isinstance(cover_data, str) and cover_data.startswith("data:image"):
            import base64 as _b64
            header, b64 = cover_data.split(",", 1)
            ext = "png"
            if "jpeg" in header:
                ext = "jpg"
            elif "webp" in header:
                ext = "webp"
            elif "gif" in header:
                ext = "gif"
            society["coverUrl"] = self.save_media(new_id_, _b64.b64decode(b64), ext)
        else:
            cv = s(src, "coverUrl")
            society["coverUrl"] = cv if cv.startswith(("http://", "https://", "data:")) else ""

        characters = []
        for c in root.get("characters") or []:
            if not isinstance(c, dict):
                continue
            ch = to_character(c)
            ch["id"] = id_map.get(ch["id"], ch["id"])
            characters.append(ch)

        relations = []
        for r in root.get("relations") or []:
            if not isinstance(r, dict):
                continue
            rel = to_relation(r)
            frm = id_map.get(rel["fromId"])
            to = id_map.get(rel["toId"])
            if not frm or not to:
                continue
            rel["id"] = new_id("rel")
            rel["fromId"] = frm
            rel["toId"] = to
            relations.append(rel)

        plot = to_plot(root.get("plot") or {})
        stickers = [to_sticker(x) for x in root.get("stickers") or [] if isinstance(x, dict)]

        self._write_atomic(os.path.join(dirp, "society.json"),
                           json.dumps(society_json(society), ensure_ascii=False))
        self._write_atomic(os.path.join(dirp, "characters.json"),
                           json.dumps([character_json(c) for c in characters], ensure_ascii=False))
        self._write_atomic(os.path.join(dirp, "relations.json"),
                           json.dumps([relation_json(r) for r in relations], ensure_ascii=False))
        self._write_atomic(os.path.join(dirp, "plot.json"), json.dumps(plot_json(plot), ensure_ascii=False))
        self._write_atomic(os.path.join(dirp, "stickers.json"),
                           json.dumps([sticker_json(x) for x in stickers], ensure_ascii=False))

        chats = root.get("chats")
        if isinstance(chats, dict):
            chat_dir = os.path.join(dirp, "chats")
            os.makedirs(chat_dir, exist_ok=True)
            for old_cid, msgs in chats.items():
                new_cid = id_map.get(old_cid)
                if not new_cid or not isinstance(msgs, list):
                    continue
                out_msgs = []
                for m in msgs:
                    if not isinstance(m, dict):
                        continue
                    mm = to_message(m)
                    mm["id"] = new_id("msg")
                    if mm["charId"] and mm["charId"] in id_map:
                        mm["charId"] = id_map[mm["charId"]]
                    out_msgs.append(mm)
                self._write_atomic(os.path.join(chat_dir, f"{safe_file_name(new_cid)}.json"),
                                   json.dumps([message_json(m) for m in out_msgs], ensure_ascii=False))

        logs = root.get("logs")
        if isinstance(logs, list) and logs:
            lines = []
            for o in logs:
                if not isinstance(o, dict):
                    continue
                actor = s(o, "actor")
                if actor and actor in id_map:
                    o = dict(o)
                    o["actor"] = id_map[actor]
                lines.append(json.dumps(o, ensure_ascii=False))
            if lines:
                self._write_atomic(self._log_file(new_id_), "\n".join(lines) + "\n")

        self._refresh_index({
            "id": new_id_, "name": society["name"],
            "orientationCode": society["orientationCode"], "orientationLabel": society["orientationLabel"],
            "characterCount": len(characters), "relationCount": len(relations),
            "updatedAt": society["updatedAt"], "coverSeed": society["coverSeed"],
            "coverImage": society.get("coverImage", ""),
            "archived": society["archived"],
        })
        return society

    # ── 底层 IO ──
    @staticmethod
    def _read_text(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _read_json(path):
        raw = SocietyStore._read_text(path)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    @staticmethod
    def _read_array(path):
        raw = SocietyStore._read_text(path)
        if not raw:
            return []
        try:
            arr = json.loads(raw)
            return arr if isinstance(arr, list) else []
        except ValueError:
            return []

    @staticmethod
    def _write_atomic(target, content):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass
        try:
            os.replace(tmp, target)
        except OSError:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            try:
                os.remove(tmp)
            except OSError:
                pass
