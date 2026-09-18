# -*- coding: utf-8 -*-
"""Kith Desktop 服务 —— 零依赖标准库 HTTP 服务器。

- REST API 供桌面前端使用（仅允许本机回环访问，保护密钥）
- /sync 同步页对局域网开放：手机浏览器上传/下载社会存档，实现双端数据互通
- /media/{sid}/{file} 提供社会媒体文件
- SSE 流式推送：旁白推进 / 人物回复 / 上帝视角
"""
import json
import os
import re
import socket
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chat_protocol  # noqa: E402
import engine  # noqa: E402
import guard as guard_mod  # noqa: E402
import importer as importer_mod  # noqa: E402
import stickers as stickers_mod  # noqa: E402
import templates as templates_mod  # noqa: E402
import vendors as vendors_mod  # noqa: E402
import vision as vision_mod  # noqa: E402
from catalog import ModelCatalog  # noqa: E402
from kcore import new_id, now_ms, safe_file_name  # noqa: E402
from settings import AppSettings  # noqa: E402
from store import (ORIENTATION_META, RELATION_KINDS, SocietyStore,  # noqa: E402
                   to_character, to_relation, to_society)

APP_VERSION = "0.2.0"

# 路径解析（兼容三种运行形态）：
#   1. 开发态  python server/main.py           → 一切相对项目根
#   2. 冻结态  kith-server.exe 独立运行         → exe 目录为根（便携 zip 同样适用）
#   3. 安装态  Kith.exe 拉起，注入 KITH_* 环境变量 → 资源在 resources/，数据在 %APPDATA%/Kith
_FROZEN = getattr(sys, "frozen", False)
_HERE = os.path.dirname(os.path.abspath(__file__)) if not _FROZEN else os.path.dirname(sys.executable)
APP_ROOT = os.environ.get("KITH_APP_ROOT") or (os.path.dirname(sys.executable) if _FROZEN else os.path.dirname(_HERE))
RES_DIR = os.environ.get("KITH_RES_DIR") or (os.path.dirname(sys.executable) if _FROZEN else APP_ROOT)
DATA_DIR = os.environ.get("KITH_DATA_DIR") or os.path.join(APP_ROOT, "data")
WEB_DIR = os.path.join(RES_DIR, "web")
# sync 页在冻结时打进 _MEIPASS，其余形态在 server/ 下
if _FROZEN and not os.environ.get("KITH_RES_DIR"):
    SYNC_PAGE = os.path.join(sys._MEIPASS, "sync_page.html")
elif _FROZEN:
    SYNC_PAGE = os.path.join(RES_DIR, "server", "sync_page.html")
else:
    SYNC_PAGE = os.path.join(APP_ROOT, "server", "sync_page.html")
_CATALOG_PATH = os.path.join(RES_DIR, "assets", "model_catalog.json")

_mime = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
    ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
}

_store = SocietyStore(os.path.join(DATA_DIR, "societies"))
_settings = AppSettings(os.path.join(DATA_DIR, "settings.json"))
_catalog = ModelCatalog(_CATALOG_PATH, os.path.join(DATA_DIR, "catalog"))


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("223.5.5.5", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _json_bytes(obj, pretty=False):
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "KithDesktop/" + APP_VERSION

    # ── 基础工具 ──
    def log_message(self, fmt, *args):
        pass

    def _client(self):
        return self.client_address[0]

    def _is_local(self):
        return self._client() in ("127.0.0.1", "::1")

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, obj, code=200, pretty=False):
        self._send(code, _json_bytes(obj, pretty))

    def _send_error_json(self, code, msg):
        self._send_json({"error": msg}, code)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self):
        raw = self._read_body()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ValueError("请求体不是合法 JSON")

    def _sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse_send(self, obj):
        try:
            self.wfile.write(b"data: " + _json_bytes(obj) + b"\n\n")
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    # ── 路由 ──
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if method == "GET" and (path == "/" or path == "/index.html"):
                return self._serve_file(os.path.join(WEB_DIR, "index.html"))
            if method == "GET" and path.startswith("/web/"):
                return self._serve_file(os.path.normpath(os.path.join(WEB_DIR, path[len("/web/"):])))
            if method == "GET" and path == "/favicon.ico":
                return self._serve_file(os.path.join(WEB_DIR, "favicon.ico"), cache=True)

            if method == "GET" and path == "/api/ping":
                return self._send_json({"ok": True, "app": "KithDesktop", "version": APP_VERSION})

            # 局域网开放面：同步页 + 存档上传下载 + 媒体
            if method == "GET" and path == "/sync":
                return self._serve_file(SYNC_PAGE)
            if method == "GET" and path == "/sync/list":
                lst = self.store.list()
                return self._send_json({"societies": lst})
            if method == "GET" and path.startswith("/sync/download/"):
                return self._sync_download(path.rsplit("/", 1)[-1])
            if method == "POST" and path == "/sync/upload":
                return self._sync_upload()
            if method == "GET" and path.startswith("/media/"):
                return self._serve_media(path)

            # 其余 API 仅限本机
            if path.startswith("/api/") and not self._is_local():
                return self._send_error_json(403, "桌面 API 仅允许本机访问；手机同步请使用 /sync 页面")

            if path == "/api/societies":
                if method == "GET":
                    return self._list_societies()
                if method == "POST":
                    return self._create_society()
            m = self._re_society(path)
            if m:
                sid, rest = m
                if method == "GET" and rest == "":
                    return self._get_bundle(sid)
                if method == "DELETE" and rest == "":
                    return self._delete_society(sid)
                if method == "GET" and rest == "export":
                    return self._export_society(sid)
                if method == "PUT" and rest == "society":
                    return self._update_society(sid)
                if method == "GET" and rest == "logs":
                    return self._get_logs(sid, qs)
                if method == "POST" and rest == "characters":
                    return self._save_character(sid)
                if method == "POST" and rest == "import-characters":
                    return self._import_characters(sid)
                if method == "DELETE" and rest.startswith("characters/"):
                    return self._delete_character(sid, rest.split("/", 1)[1])
                if method == "POST" and rest == "relations":
                    return self._save_relation(sid)
                if method == "DELETE" and rest.startswith("relations/"):
                    return self._delete_relation(sid, rest.split("/", 1)[1])
                if method == "PUT" and rest == "layout":
                    return self._save_layout(sid)
                if method == "GET" and rest.startswith("chats/") and rest.count("/") == 1:
                    return self._get_thread(sid, rest.split("/", 1)[1])
                if method == "DELETE" and rest.startswith("chats/") and rest.count("/") == 1:
                    return self._delete_thread(sid, rest.split("/", 1)[1])
                if method == "POST" and rest == "narrate":
                    return self._narrate(sid)
                if method == "POST" and rest.startswith("chat/") and rest.endswith("/send"):
                    cid = rest[len("chat/"):-len("/send")]
                    return self._chat_send(sid, cid)
                if method == "POST" and rest == "confirm-transfer":
                    return self._confirm_transfer(sid)
                if method == "POST" and rest == "update-message":
                    return self._update_message(sid)
                if method == "POST" and rest == "generate-image":
                    return self._generate_image(sid)
                if method == "POST" and rest == "stickers":
                    return self._add_sticker(sid)
                if method == "DELETE" and rest.startswith("stickers/"):
                    return self._delete_sticker(sid, rest.split("/", 1)[1])
                if method == "POST" and rest == "godview":
                    return self._godview(sid)

            if path == "/api/import" and method == "POST":
                return self._import_archive()
            if path == "/api/upload-image" and method == "POST":
                return self._upload_image()
            if path == "/api/settings" and method == "GET":
                return self._send_json(self.settings.state)
            if path == "/api/settings" and method == "PUT":
                return self._put_settings()
            if path == "/api/endpoints" and method == "POST":
                return self._upsert_endpoint()
            if path == "/api/endpoints/delete" and method == "POST":
                return self._delete_endpoint()
            if path == "/api/saved-models/delete" and method == "POST":
                return self._delete_saved_model()
            if path == "/api/catalog" and method == "GET":
                return self._catalog_query(qs)
            if path == "/api/catalog/vendors" and method == "GET":
                return self._send_json({"vendors": self.catalog.vendors_in_use(),
                                        "all": vendors_mod.all_vendors()})
            if path == "/api/catalog/refresh" and method == "POST":
                return self._catalog_refresh()
            if path == "/api/catalog/import" and method == "POST":
                return self._catalog_import()
            if path == "/api/catalog/reset" and method == "POST":
                snap = self.catalog.reset_to_bundled()
                return self._send_json({"ok": True, "origin": snap["origin"],
                                        "count": len(snap["models"])})
            if path == "/api/templates" and method == "GET":
                return self._send_json({
                    "plots": templates_mod.PLOT_TEMPLATES,
                    "orientations": templates_mod.ORIENTATIONS,
                    "tropes": templates_mod.TROPE_SUGGESTIONS,
                    "tags": [{"label": l, "hint": h} for l, h in templates_mod.TAG_TEMPLATES],
                })
            if path == "/api/vendors" and method == "GET":
                return self._send_json({"vendors": vendors_mod.all_vendors()})
            if path == "/api/image-presets" and method == "GET":
                return self._send_json({"presets": vision_mod.image_presets_payload()})
            if path == "/api/endpoint-models" and method == "GET":
                eid = (qs.get("endpointId") or [""])[0]
                ep = self.settings.endpoint(eid)
                if not ep:
                    return self._send_error_json(404, "接入点不存在")
                return self._send_json({"endpointId": eid, "models": llm.endpoint_models_cached(ep)})
            if path == "/api/sync-info" and method == "GET":
                port = self.server.server_address[1]
                return self._send_json({"ip": lan_ip(), "port": port,
                                        "lanUrl": f"http://{lan_ip()}:{port}/sync",
                                        "localUrl": f"http://127.0.0.1:{port}/sync"})
            if path == "/api/quit" and method == "POST":
                self._send_json({"ok": True})
                threading.Timer(0.4, lambda: os._exit(0)).start()
                return

            return self._send_error_json(404, "接口不存在")
        except ValueError as e:
            return self._send_error_json(400, str(e))
        except BrokenPipeError:
            return
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc(file=sys.stderr)
            return self._send_error_json(500, f"{e.__class__.__name__}: {e}")

    _re_cache = {}

    def _re_society(self, path):
        if not path.startswith("/api/societies/"):
            return None
        rest = path[len("/api/societies/"):]
        parts = rest.split("/", 1)
        sid = urllib.parse.unquote(parts[0])
        sub = parts[1] if len(parts) > 1 else ""
        return sid, sub

    # ── 静态与媒体 ──
    def _serve_file(self, path, cache=False):
        path = os.path.abspath(path)
        allow_roots = {os.path.abspath(WEB_DIR), os.path.abspath(APP_ROOT), os.path.abspath(RES_DIR)}
        if getattr(sys, "frozen", False):
            allow_roots.add(os.path.abspath(sys._MEIPASS))
        if not any(path.startswith(r) for r in allow_roots):
            return self._send_error_json(403, "禁止访问")
        if not os.path.isfile(path):
            return self._send_error_json(404, "文件不存在")
        ext = os.path.splitext(path)[1].lower()
        ctype = _mime.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        extra = {"Cache-Control": "max-age=3600" if cache else "no-cache"}
        self._send(200, body, ctype, extra)

    def _serve_media(self, path):
        # /media/{sid}/{file...}
        parts = path[len("/media/"):].split("/")
        if len(parts) < 2:
            return self._send_error_json(404, "路径不合法")
        sid = urllib.parse.unquote(parts[0])
        fname = "/".join(urllib.parse.unquote(p) for p in parts[1:])
        base = os.path.abspath(self.store.society_dir(sid))
        full = os.path.abspath(os.path.join(base, fname))
        if not full.startswith(base) or not os.path.isfile(full):
            return self._send_error_json(404, "文件不存在")
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as f:
            body = f.read()
        self._send(200, body, _mime.get(ext, "application/octet-stream"), {"Cache-Control": "max-age=3600"})

    # ── 社会 ──
    @property
    def store(self):
        return _store

    @property
    def settings(self):
        return _settings

    @property
    def catalog(self):
        return _catalog

    def _list_societies(self):
        lst = self.store.list()
        chars = sum(x["characterCount"] for x in lst)
        rels = sum(x["relationCount"] for x in lst)
        return self._send_json({"societies": lst, "stats": {
            "societies": len(lst), "characters": chars, "relations": rels}})

    def _create_society(self):
        body = self._read_json()
        name = (body.get("name") or "").strip()
        if not name:
            raise ValueError("社会名称不能为空")
        ori = body.get("orientation", "BG")
        if ori not in ORIENTATION_META:
            ori = "BG"
        meta = ORIENTATION_META[ori]
        now = now_ms()
        society = {
            "id": new_id("soc"), "name": name,
            "worldSetting": body.get("worldSetting") or "",
            "orientation": ori, "orientationCode": meta["code"], "orientationLabel": meta["label"],
            "plotDirection": body.get("plotDirection") or "",
            "tropes": [t for t in (body.get("tropes") or []) if isinstance(t, str)],
            "coverSeed": int(body.get("coverSeed") or 0),
            "narratorModel": body.get("narratorModel") or None,
            "defaultCharacterModel": body.get("defaultCharacterModel") or None,
            "imageModel": body.get("imageModel") or None,
            "createdAt": now, "updatedAt": now, "archived": False, "version": 1,
        }
        self.store.save_society(society)

        characters = []
        for c in body.get("characters") or []:
            if not isinstance(c, dict) or not (c.get("name") or "").strip():
                continue
            ch = to_character(c)
            ch["id"] = new_id("chr")
            ch["createdAt"] = now
            ch["updatedAt"] = now
            ch["isUser"] = bool(ch.get("isUser"))
            characters.append(ch)
        if characters:
            # 最多一个 isUser
            seen_user = False
            for c in characters:
                if c.get("isUser"):
                    if seen_user:
                        c["isUser"] = False
                    seen_user = True
            self.store.save_characters(society["id"], characters)

        self.store.append_log(society["id"], engine.make_log(
            "SYSTEM", "系统", "创建了社会", detail=f"「{name}」· {meta['label']} · {len(characters)} 位初始人物"))
        return self._send_json({"society": society, "characters": characters})

    # 旁白叙述的落盘会话 id（与安卓端 SocietyViewModel.NARRATOR_THREAD 一致）
    NARRATOR_THREAD = "__narrator__"

    def _get_bundle(self, sid):
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        # 模型引用清洗：目录按实测裁剪后，存档里保存的旧 id（老目录的日期后缀名）
        # 会悬空 —— 面板显示旧名、调用直接 400。能对齐的更新 id 并刷新显示名。
        if self._sanitize_model_refs(bundle):
            self.store.save_society(bundle["society"])
            self.store.save_characters(sid, bundle["characters"])
        bundle["positions"] = self.store.load_node_positions(sid)
        bundle["chatIds"] = sorted(self.store.chat_character_ids(sid) - {self.NARRATOR_THREAD})
        # 头部统计（与安卓端 SocietyUiState 同源）：花费/tokens 取最近 400 条日志，
        # isolatedCount 供「N 人未连线」提示
        logs = self.store.read_logs(sid, 400)
        linked = {r["fromId"] for r in bundle["relations"]} | {r["toId"] for r in bundle["relations"]}
        bundle["stats"] = {
            "totalCostUsd": round(sum(l.get("costUsd") or 0 for l in logs), 6),
            "tokensIn": sum(l.get("tokensIn") or 0 for l in logs),
            "tokensOut": sum(l.get("tokensOut") or 0 for l in logs),
            "isolatedCount": sum(1 for c in bundle["characters"] if c["id"] not in linked),
        }
        return self._send_json(bundle)

    _DATE_SUFFIX_RE = re.compile(r"-(?:\d{8}|\d{2}-\d{4}|\d{4})$")

    def _sanitize_model_refs(self, bundle):
        """把存档里的模型引用对齐到现存目录条目。无变化返回 False 避免无谓落盘。

        匹配顺序与安卓端一致（id 原样 → deepseek/ 前缀裸名 → 裸名），并额外
        用「裸名 → 完整 id」索引兜底跨厂商前缀的旧引用（如 cohere/xxx 的档
        案在目录里已变成 other-vendor/xxx 的场景）。
        """
        models = self.catalog.current().get("models") or []
        ids = {m.get("id") for m in models}
        if not ids:
            return False
        bare_index = {}
        for mid in ids:
            bare_index.setdefault(str(mid).split("/", 1)[-1], mid)

        def name_of(mid):
            mm = self.catalog.find(mid)
            return mm.get("name") if mm else None

        def fix(ref):
            if not isinstance(ref, dict):
                return ref
            mid = ref.get("modelId") or ""
            if mid in ids:
                fresh = name_of(mid)
                if fresh and fresh != ref.get("label"):
                    return {**ref, "label": fresh}
                return ref
            bare = mid.split("/", 1)[1] if "/" in mid else ""
            stripped = self._DATE_SUFFIX_RE.sub("", bare)
            target = next((c for c in (f"deepseek/{stripped}", stripped,
                                       bare_index.get(stripped), mid)
                           if c and c in ids), None)
            if not target:
                return ref
            return {**ref, "modelId": target, "label": name_of(target) or ref.get("label")}

        changed = False
        soc = bundle["society"]
        for key in ("narratorModel", "defaultCharacterModel", "imageModel"):
            nf = fix(soc.get(key))
            if nf != soc.get(key):
                soc[key] = nf
                changed = True
        for c in bundle["characters"]:
            nf = fix(c.get("model"))
            if nf != c.get("model"):
                c["model"] = nf
                changed = True
        return changed

    def _delete_society(self, sid):
        self.store.delete(sid)
        return self._send_json({"ok": True})

    def _export_society(self, sid):
        raw = self.store.export_archive(sid)
        if raw is None:
            return self._send_error_json(404, "社会不存在")
        bundle = self.store.load(sid)
        fname = safe_file_name(bundle["society"]["name"] if bundle else sid, sid) + ".kith.json"
        self._send(200, raw.encode("utf-8"), "application/json; charset=utf-8",
                   {"Content-Disposition": f'attachment; filename="{fname}"'})

    def _import_archive(self):
        raw = self._read_body().decode("utf-8", errors="replace")
        society = self.store.import_archive(raw)
        return self._send_json({"society": society})

    def _update_society(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        soc = bundle["society"]
        for key in ("name", "worldSetting", "plotDirection"):
            if key in body:
                soc[key] = str(body[key] or "")
        if "coverImage" in body:
            # 与安卓端同约定：存 media/ 下的裸文件名
            soc["coverImage"] = str(body["coverImage"] or "").replace("\\", "/").split("/")[-1]
        if "coverUrl" in body:  # 兼容旧字段
            soc["coverImage"] = str(body["coverUrl"] or "").split("/")[-1]
        if "tropes" in body:
            soc["tropes"] = [t for t in body["tropes"] if isinstance(t, str)]
        if "orientation" in body and body["orientation"] in ORIENTATION_META:
            meta = ORIENTATION_META[body["orientation"]]
            soc["orientation"] = body["orientation"]
            soc["orientationCode"] = meta["code"]
            soc["orientationLabel"] = meta["label"]
        if "coverSeed" in body:
            soc["coverSeed"] = int(body["coverSeed"] or 0)
        for key in ("narratorModel", "defaultCharacterModel", "imageModel"):
            if key in body:
                soc[key] = body[key] or None
        soc["updatedAt"] = now_ms()
        self.store.save_society(soc)
        return self._send_json({"society": soc})

    def _get_logs(self, sid, qs):
        limit = int((qs.get("limit") or ["300"])[0])
        return self._send_json({"logs": self.store.read_logs(sid, limit)})

    # ── 人物 ──
    def _save_character(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        characters = bundle["characters"]
        ch = to_character(body)
        now = now_ms()
        if ch["id"]:
            found = False
            for idx, c in enumerate(characters):
                if c["id"] == ch["id"]:
                    ch["createdAt"] = c["createdAt"]
                    found = True
                    break
            if not found:
                return self._send_error_json(404, "人物不存在")
            ch["updatedAt"] = now
            characters[idx] = ch
            action = "更新了人物"
        else:
            ch["id"] = new_id("chr")
            ch["createdAt"] = now
            ch["updatedAt"] = now
            characters.append(ch)
            action = "引入了新人物"
        # isUser 唯一
        if ch.get("isUser"):
            for c in characters:
                if c["id"] != ch["id"]:
                    c["isUser"] = False
        self.store.save_characters(sid, characters)
        self.store.append_log(sid, engine.make_log("SYSTEM", "系统", f"{action}「{ch['name']}」"))
        return self._send_json({"character": ch, "characters": characters})

    def _import_characters(self, sid):
        """从文件导入人物（Kith 自家格式 / 喵咚角色卡），按名字去重。"""
        body = self._read_json()
        raw = body.get("raw")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("文件是空的，没有可导入的内容")
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        chars, skipped = importer_mod.import_characters(raw)
        existing = bundle["characters"]
        existing_names = {c["name"] for c in existing}
        fresh = [c for c in chars if c["name"] not in existing_names]
        if fresh:
            self.store.save_characters(sid, existing + fresh)
        added = len(fresh)
        dup = len(chars) - added
        msg = "没有新增人物（社会里已有同名人物）" if not fresh else f"已导入 {added} 位人物"
        if skipped:
            msg += f"，跳过 {skipped} 个无效项"
        elif dup:
            msg += f"，{dup} 位与社会里已有的人物同名"
        return self._send_json({"added": added, "skipped": skipped, "message": msg,
                                "characters": self.store.load(sid)["characters"]})

    def _delete_character(self, sid, cid):
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        name = next((c["name"] for c in bundle["characters"] if c["id"] == cid), cid)
        characters = [c for c in bundle["characters"] if c["id"] != cid]
        relations = [r for r in bundle["relations"] if r["fromId"] != cid and r["toId"] != cid]
        self.store.save_characters(sid, characters)
        self.store.save_relations(sid, relations)
        chat_path = os.path.join(self.store.society_dir(sid), "chats", safe_file_name(cid) + ".json")
        if os.path.exists(chat_path):
            try:
                os.remove(chat_path)
            except OSError:
                pass
        self.store.append_log(sid, engine.make_log(
            "SYSTEM", "系统", f"删除了人物「{name}」",
            detail="关联的会话与关系连线已一并移除"))
        return self._send_json({"ok": True, "characters": characters, "relations": relations})

    # ── 关系 ──
    def _save_relation(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        relations = bundle["relations"]
        rel = to_relation(body)
        now = now_ms()
        if rel["id"]:
            idx = next((k for k, r in enumerate(relations) if r["id"] == rel["id"]), -1)
            if idx < 0:
                return self._send_error_json(404, "关系不存在")
            rel["createdAt"] = relations[idx]["createdAt"]
            relations[idx] = rel
        else:
            rel["id"] = new_id("rel")
            rel["createdAt"] = now
            relations.append(rel)
        self.store.save_relations(sid, relations)
        return self._send_json({"relation": rel, "relations": relations})

    def _delete_relation(self, sid, rid):
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        relations = [r for r in bundle["relations"] if r["id"] != rid]
        self.store.save_relations(sid, relations)
        return self._send_json({"ok": True, "relations": relations})

    def _save_layout(self, sid):
        body = self._read_json()
        positions = body.get("positions") or {}
        clean = {}
        for k, v in positions.items():
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                clean[k] = [float(v[0]), float(v[1])]
        self.store.save_node_positions(sid, clean)
        return self._send_json({"ok": True})

    # ── 会话 ──
    def _get_thread(self, sid, cid):
        cid = urllib.parse.unquote(cid)
        return self._send_json(self.store.load_thread(sid, cid))

    def _delete_thread(self, sid, cid):
        cid = urllib.parse.unquote(cid)
        path = os.path.join(self.store.society_dir(sid), "chats", safe_file_name(cid) + ".json")
        if os.path.exists(path):
            os.remove(path)
        return self._send_json({"ok": True})

    def _chat_send(self, sid, cid):
        cid = urllib.parse.unquote(cid)
        body = self._read_json()
        text = str(body.get("text") or "")
        attachment = str(body.get("attachment") or "")

        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        speaker = next((c for c in bundle["characters"] if c["id"] == cid), None)
        if not speaker:
            return self._send_error_json(404, "人物不存在")
        if not engine.IMPORTANCE_META.get(speaker.get("importance"), {}).get("chatEnabled"):
            return self._send_error_json(400, "该人物是背景人物（次要/路人），不参与对话")
        user = bundle.get("userCharacter") or next((c for c in bundle["characters"] if c.get("isUser")), None)
        thread = self.store.load_thread(sid, cid)

        # 先落盘用户消息（快照不含它，避免上下文重复）
        user_msg = {
            "id": new_id("msg"), "role": "USER", "charId": cid,
            "segments": chat_protocol.parse(text) if text else [],
            "raw": text, "ts": now_ms(), "status": "DONE", "modelLabel": "",
            "tokensIn": 0, "tokensOut": 0, "costUsd": 0.0, "error": "", "attachment": attachment,
        }
        self.store.append_message(sid, cid, user_msg)

        self._sse_start()
        gen = engine.character_reply_generator(self.store, self.catalog, self.settings,
                                               bundle, speaker, user, thread, text, attachment)
        try:
            for ev in gen:
                if ev["type"] == "done":
                    self.store.append_message(sid, cid, ev["message"])
                    self.store.append_log(sid, ev["log"])
                    payload = {"type": "done", "message": ev["message"], "userMessage": user_msg}
                elif ev["type"] == "failed":
                    self.store.append_log(sid, ev["log"])
                    payload = {"type": "failed", "error": ev["error"], "userMessage": user_msg}
                elif ev["type"] == "delta":
                    payload = {"type": "delta", "buffer": ev["buffer"]}
                else:
                    payload = ev
                if not self._sse_send(payload):
                    return
        except Exception as e:  # noqa: BLE001
            self._sse_send({"type": "failed", "error": str(e), "userMessage": user_msg})

    def _update_message(self, sid):
        """整条替换消息（用于异步生图回填 url / 转账确认后的状态更新）。"""
        body = self._read_json()
        cid = body.get("charId")
        msg = body.get("message") or {}
        if not cid or not msg.get("id"):
            return self._send_error_json(400, "缺少 charId 或 message.id")
        from store import to_message, message_json
        thread = self.store.load_thread(sid, cid)
        for idx, m in enumerate(thread["messages"]):
            if m["id"] == msg["id"]:
                thread["messages"][idx] = to_message(msg)
                self.store.save_thread(sid, thread)
                return self._send_json({"ok": True})
        return self._send_error_json(404, "消息不存在")

    def _confirm_transfer(self, sid):
        body = self._read_json()
        cid = body.get("charId")
        msg_id = body.get("msgId")
        thread = self.store.load_thread(sid, cid)
        changed = False
        for m in thread["messages"]:
            if m["id"] != msg_id:
                continue
            for seg in m["segments"]:
                if seg.get("type") == "transfer":
                    seg["confirmed"] = True
                    changed = True
        if changed:
            self.store.save_thread(sid, thread)
            self.store.append_log(sid, engine.make_log(
                "SYSTEM", "系统", "转账已确认",
                detail=f"消息 {msg_id} 的转账卡片被点击「收下」（模拟支付，无真实资金流动）"))
        return self._send_json({"ok": changed})

    # ── 旁白 ──
    def _narrate(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        self._sse_start()
        self._sse_send({"type": "started"})
        outcome = engine.narrator_advance(
            self.store, self.catalog, self.settings, bundle,
            user_hint=str(body.get("userHint") or ""),
            need_new_npc=bool(body.get("needNewNpc")),
            max_new_npcs=int(body.get("maxNewNpcs") or 2))
        if outcome["ok"]:
            # 持久化
            if outcome["newCharacters"]:
                chars = bundle["characters"] + outcome["newCharacters"]
                self.store.save_characters(sid, chars)
            if outcome["newRelations"]:
                rels = bundle["relations"] + outcome["newRelations"]
                self.store.save_relations(sid, rels)
            self.store.save_plot(sid, outcome["plot"])
            self.store.append_logs(sid, outcome["logs"])
            # 旁白叙述单独存一条会话（__narrator__），保证日志之外还能回看；
            # chatIds 已把它从人物会话列表里排除
            narrative = outcome.get("narrative") or ""
            if narrative:
                self.store.append_message(sid, self.NARRATOR_THREAD, {
                    "id": new_id("msg"), "role": "NARRATOR", "charId": self.NARRATOR_THREAD,
                    "segments": [{"type": "text", "content": narrative}], "raw": narrative,
                    "ts": now_ms(), "status": "DONE", "modelLabel": "",
                    "tokensIn": outcome.get("inputTokens") or 0,
                    "tokensOut": outcome.get("outputTokens") or 0,
                    "costUsd": outcome.get("costUsd") or 0.0, "error": "", "attachment": "",
                })
            # 本地审核（可选，默认关）：对旁白叙述跑最低层次体检。未通过也保留
            # 内容并写日志（绝不静默丢弃），只给用户明确提示。桌面端不做
            # Qwen3Guard 模型分类（那是安卓端 MediaPipe 端上推理的能力）。
            if self.settings.state.get("guardEnabled"):
                guard_err = guard_mod.sanity_check(narrative)
                if guard_err is not None:
                    self.store.append_logs(sid, [engine.make_log(
                        "SYSTEM", "审核", "旁白内容未通过本地体检",
                        detail=f"{guard_err}\n原文已保留在旁白会话中")])
                    outcome["guardNotice"] = f"⚠️ {guard_err}"
        else:
            self.store.append_logs(sid, outcome["logs"])
        self._sse_send({"type": "done", "outcome": outcome})

    def _godview(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        aid, bid = body.get("aId"), body.get("bId")
        topic = str(body.get("topic") or "随便聊聊最近的近况")
        a = next((c for c in bundle["characters"] if c["id"] == aid), None)
        b = next((c for c in bundle["characters"] if c["id"] == bid), None)
        if not a or not b:
            return self._send_error_json(400, "请选择两个有效的人物")
        self._sse_start()
        gen = engine.god_dialogue_generator(self.store, self.catalog, self.settings,
                                            bundle, a, b, topic)
        try:
            for ev in gen:
                if ev["type"] == "done":
                    self.store.append_log(sid, ev["log"])
                elif ev["type"] == "failed":
                    self.store.append_log(sid, ev["log"])
                self._sse_send(ev)
        except Exception as e:  # noqa: BLE001
            self._sse_send({"type": "failed", "error": str(e)})

    # ── 生图 ──
    def _generate_image(self, sid):
        body = self._read_json()
        bundle = self.store.load(sid)
        if not bundle:
            return self._send_error_json(404, "社会不存在")
        society = bundle["society"]
        kind = body.get("kind", "scene")
        prompt = str(body.get("prompt") or "")
        ratio = str(body.get("ratio") or "1:1")
        style = str(body.get("style") or "")

        # 模型解析：显式传入 → 社会配置的 imageModel → 任一已配置的生图接入点
        ref = body.get("model") or society.get("imageModel")
        endpoint = None
        model_id = ""
        if ref:
            endpoint = self.settings.endpoint(ref.get("endpointId"))
            model_id = ref.get("modelId") or ""
        if not endpoint:
            eps = [e for e in self.settings.state.get("endpoints") or [] if e.get("kind") == "IMAGE"]
            if not eps:
                return self._send_error_json(400, "还没有配置文生图接入点。请到「设置 → 模型接入点」里添加一个生图模型的 Key。")
            endpoint = eps[0]
            model_id = model_id or body.get("modelId") or ""
        if not model_id:
            return self._send_error_json(400, "没有指定生图模型")

        result, err = vision_mod.generate_image(self.store, sid, endpoint, model_id,
                                                prompt, ratio, style)
        if err:
            self.store.append_log(sid, engine.make_log("IMAGE", "生图", "生成失败", detail=err))
            return self._send_error_json(400, err)
        url = result["localPath"] or result["remoteUrl"]
        self.store.append_log(sid, engine.make_log(
            "IMAGE", "生图", "生成了一张图片",
            detail=f"模型：{model_id}\n提示词：{prompt}", model_label=model_id))
        return self._send_json({"url": url, "localPath": result["localPath"],
                                "remoteUrl": result["remoteUrl"]})

    # ── 表情包 ──
    def _add_sticker(self, sid):
        body = self._read_json()
        import base64 as _b64
        data = _b64.b64decode(body.get("dataBase64") or "")
        ext = body.get("ext") or "png"
        if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
            ext = "png"
        ref = self.store.save_media(sid, data, ext)
        bundle = self.store.load(sid)
        library = stickers_mod.add(bundle["stickers"], str(body.get("name") or "表情"),
                                   ref, body.get("emotions") or [])
        self.store.save_stickers(sid, library)
        return self._send_json({"stickers": library, "url": ref})

    def _delete_sticker(self, sid, sticker_id):
        bundle = self.store.load(sid)
        library = stickers_mod.remove(bundle["stickers"], urllib.parse.unquote(sticker_id))
        self.store.save_stickers(sid, library)
        return self._send_json({"stickers": library})

    # ── 图片上传 ──
    def _upload_image(self):
        import base64 as _b64
        body = self._read_json()
        sid = body.get("societyId")
        if not sid or not self.store.society_dir(sid):
            return self._send_error_json(400, "缺少社会上下文")
        data = _b64.b64decode(body.get("dataBase64") or "")
        ext = (body.get("ext") or "png").lower()
        if ext == "jpeg":
            ext = "jpg"
        if ext not in ("png", "jpg", "webp", "gif"):
            ext = "png"
        ref = self.store.save_media(sid, data, ext)
        return self._send_json({"url": ref})

    # ── 设置 ──
    def _put_settings(self):
        body = self._read_json()
        allowed = {k: v for k, v in body.items()
                   if k in ("visionEnabled", "visionBaseUrl", "visionApiKey", "visionModel",
                            "visionNoticeAccepted", "narratorAutoAssignModel",
                            "narratorAutoLinkRelations", "godViewEnabled", "graphLayout",
                            "themeMode", "usdToCnyRate", "autoNarratorOnEnter",
                            "catalogUrl", "catalogRefreshedAt", "guardEnabled",
                            "guardUnderSpecNoticeShown")}
        if isinstance(body.get("savedModels"), list):
            self.settings.state["savedModels"] = body["savedModels"]
        self.settings.update(**allowed)
        if isinstance(body.get("savedModels"), list):
            self.settings.save()
        return self._send_json(self.settings.state)

    def _upsert_endpoint(self):
        body = self._read_json()
        ep = {
            "id": str(body.get("id") or "") or new_id("ep"),
            "label": str(body.get("label") or ""),
            "vendor": str(body.get("vendor") or ""),
            "kind": body.get("kind") if body.get("kind") in ("LLM", "IMAGE") else "LLM",
            "baseUrl": str(body.get("baseUrl") or "").strip().rstrip("/"),
            "apiKey": str(body.get("apiKey") or "").strip(),
            "createdAt": int(body.get("createdAt") or now_ms()),
        }
        if not ep["vendor"]:
            raise ValueError("厂商不能为空")
        if not ep["baseUrl"] and ep["kind"] == "LLM":
            raise ValueError("接入地址不能为空")
        if not ep["label"]:
            ep["label"] = ep["vendor"]
        self.settings.upsert_endpoint(ep)
        return self._send_json({"endpoint": ep, "settings": self.settings.state})

    def _delete_endpoint(self):
        body = self._read_json()
        self.settings.remove_endpoint(str(body.get("id") or ""))
        return self._send_json({"settings": self.settings.state})

    def _delete_saved_model(self):
        body = self._read_json()
        ref = body.get("ref") or {}
        self.settings.remove_saved_model(ref)
        return self._send_json({"settings": self.settings.state})

    # ── 目录 ──
    def _catalog_query(self, qs):
        vendors = set(qs.get("vendor", []))
        res = self.catalog.query(
            keyword=(qs.get("q") or [""])[0], vendors=vendors,
            only_free=qs.get("free") == ["1"], only_vision=qs.get("vision") == ["1"],
            only_text_only=qs.get("text") == ["1"], sort=(qs.get("sort") or ["PRICE_ASC"])[0],
            limit=min(200, int((qs.get("limit") or ["60"])[0])),
            offset=int((qs.get("offset") or ["0"])[0]))
        snap = self.catalog.current()
        return self._send_json({**res, "origin": snap["origin"], "generatedAt": snap["generatedAt"],
                                "totalModels": len(snap["models"]),
                                "freeCount": snap["freeCount"], "visionCount": snap["visionCount"]})

    def _catalog_refresh(self):
        body = self._read_json()
        url = str(body.get("url") or "").strip()
        if not url:
            raise ValueError("请填写目录刷新地址")
        snap = self.catalog.refresh_from_url(url)
        self.settings.update(catalogUrl=url, catalogRefreshedAt=now_ms())
        return self._send_json({"ok": True, "origin": snap["origin"], "count": len(snap["models"])})

    def _catalog_import(self):
        raw = self._read_body().decode("utf-8", errors="replace")
        snap = self.catalog.import_from_json(raw)
        return self._send_json({"ok": True, "origin": snap["origin"], "count": len(snap["models"])})

    # ── 手机同步 ──
    def _sync_download(self, sid):
        raw = self.store.export_archive(sid)
        if raw is None:
            return self._send_error_json(404, "社会不存在")
        bundle = self.store.load(sid)
        fname = safe_file_name((bundle or {}).get("society", {}).get("name", sid), sid) + ".kith.json"
        self._send(200, raw.encode("utf-8"), "application/json; charset=utf-8",
                   {"Content-Disposition": f'attachment; filename="{fname}"'})

    def _sync_upload(self):
        raw = self._read_body().decode("utf-8", errors="replace")
        try:
            society = self.store.import_archive(raw)
        except ValueError as e:
            return self._send_error_json(400, str(e))
        return self._send_json({"ok": True, "name": society["name"], "id": society["id"]})


def serve(port):
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    print(f"[Kith] serving on http://127.0.0.1:{port}  (LAN: http://{lan_ip()}:{port}/sync)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 19287
    serve(port)
