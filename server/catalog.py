# -*- coding: utf-8 -*-
"""模型目录 —— 三层数据（在线刷新缓存 > 内置快照），价格分位划分档位。

与安卓端 ModelCatalog.kt 同构：ECONOMY 取最便宜的前 1/3，STANDARD 中 1/3，
PREMIUM 最贵的 1/3；同档内优先上下文更长。
"""
import json
import os
import threading
import urllib.request

from kcore import now_ms
from vendors import vendor_of, normalize


class ModelCatalog:
    def __init__(self, bundled_path: str, cache_dir: str):
        self.bundled_path = bundled_path
        self.cache_file = os.path.join(cache_dir, "model_catalog.json")
        self.lock = threading.Lock()
        self.snapshot = None
        self.index = {}

    def ensure_loaded(self):
        if self.snapshot:
            return self.snapshot
        with self.lock:
            if self.snapshot:
                return self.snapshot
            loaded = self._read_best_source()
            self.index = {m["id"]: m for m in loaded["models"]}
            self.snapshot = loaded
            return loaded

    def current(self):
        return self.ensure_loaded()

    def find(self, model_id):
        self.ensure_loaded()
        return self.index.get(model_id)

    def display_name(self, model_id):
        self.ensure_loaded()
        m = self.index.get(model_id)
        return (m or {}).get("name") or model_id

    def _read_best_source(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    parsed = self._parse(f.read(), "在线刷新")
                if parsed["models"]:
                    return parsed
            except Exception:
                pass
        if os.path.exists(self.bundled_path):
            try:
                with open(self.bundled_path, "r", encoding="utf-8") as f:
                    parsed = self._parse(f.read(), "内置快照")
                if parsed["models"]:
                    return parsed
            except Exception:
                pass
        return {"models": [], "generatedAt": "", "origin": "无可用目录", "freeCount": 0, "visionCount": 0}

    def _parse(self, raw, origin):
        root = json.loads(raw)
        arr = root.get("models") or []
        models = []
        for o in arr:
            if not isinstance(o, dict):
                continue
            mid = (o.get("id") or "").strip()
            if not mid:
                continue
            vendor_raw = o.get("vendor") or ""
            pricing = o.get("pricing") or {}

            def price_of(key):
                if key in pricing and pricing[key] is not None:
                    try:
                        return float(pricing[key])
                    except (TypeError, ValueError):
                        return None
                return None

            mods = [m for m in (o.get("modalities") or []) if isinstance(m, str)]
            expiration = o.get("expiration_ts")
            models.append({
                "id": mid,
                "name": (o.get("name") or "").strip() or mid,
                "vendorKey": normalize(vendor_raw) or (vendor_raw.strip() or "Unknown"),
                "vendor": vendor_of(vendor_raw),
                "contextLength": int(o.get("context_length") or 0),
                "modalities": mods,
                "promptPerM": price_of("prompt_per_m"),
                "completionPerM": price_of("completion_per_m"),
                "releasedTs": int(o.get("released_ts") or 0),
                "expirationTs": int(expiration) if expiration else None,
                "sourceKey": o.get("source_key") or "",
                "url": o.get("url") or "",
            })
        for m in models:
            m["supportsVision"] = any(x in ("image", "video") for x in m["modalities"])
            m["isFree"] = ":free" in m["id"]
            m["priceKnown"] = m["promptPerM"] is not None or m["completionPerM"] is not None
            m["blendedPrice"] = (m["promptPerM"] or 0.0) + (m["completionPerM"] or 0.0)
            exp = m["expirationTs"]
            m["isExpired"] = bool(exp and 1 <= exp < now_ms())
            m["expiringSoon"] = bool(exp and now_ms() < exp < now_ms() + 30 * 86_400_000)
        return {
            "models": models,
            "generatedAt": root.get("generated_at") or "",
            "origin": origin,
            "freeCount": sum(1 for m in models if m["isFree"]),
            "visionCount": sum(1 for m in models if m["supportsVision"]),
        }

    # ── 刷新 / 导入 / 重置 ──
    def refresh_from_url(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "KithDesktop/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return self._accept(raw, f"在线刷新 {url}")

    def import_from_json(self, raw):
        return self._accept(raw, "手动导入")

    def _accept(self, raw, origin):
        parsed = self._parse(raw, origin)
        if not parsed["models"]:
            raise ValueError("解析后没有任何模型，请确认是 modelwatch 导出的 JSON")
        with self.lock:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                f.write(raw)
            self.index = {m["id"]: m for m in parsed["models"]}
            self.snapshot = parsed
        return parsed

    def reset_to_bundled(self):
        with self.lock:
            if os.path.exists(self.cache_file):
                try:
                    os.remove(self.cache_file)
                except OSError:
                    pass
            self.snapshot = None
            self.index = {}
        return self.ensure_loaded()

    def export_json(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return f.read()
        if os.path.exists(self.bundled_path):
            with open(self.bundled_path, "r", encoding="utf-8") as f:
                return f.read()
        return "{}"

    # ── 价格与档位 ──
    def estimate_cost_usd(self, model_id, tokens_in, tokens_out):
        m = self.find(model_id)
        if not m:
            return 0.0
        return (m["promptPerM"] or 0.0) * tokens_in / 1_000_000.0 + \
               (m["completionPerM"] or 0.0) * tokens_out / 1_000_000.0

    def candidates_for_tier(self, tier, require_vision=False, vendor_key=None):
        allm = self.ensure_loaded()["models"]
        pool = [m for m in allm
                if (m["priceKnown"] or m["isFree"]) and not m["isExpired"]
                and (not require_vision or m["supportsVision"])
                and (vendor_key is None or m["vendorKey"] == vendor_key)]
        if not pool:
            return [m for m in allm if not require_vision or m["supportsVision"]][:20]
        pool.sort(key=lambda m: m["blendedPrice"])
        n = len(pool)
        if tier == "ECONOMY":
            lo, hi = 0, max(1, n // 3)
        elif tier == "STANDARD":
            lo, hi = n // 3, max(n // 3 + 1, 2 * n // 3)
        else:
            lo, hi = 2 * n // 3, n
        return pool[max(0, min(lo, n)):max(0, min(hi, n))]

    def pick_for_tier(self, tier, require_vision=False, vendor_key=None):
        cands = self.candidates_for_tier(tier, require_vision, vendor_key)
        if not cands:
            return None
        return max(cands, key=lambda m: m["contextLength"])

    # ── 检索 ──
    def query(self, keyword="", vendors=None, only_free=False, only_vision=False,
              only_text_only=False, sort="PRICE_ASC", limit=60, offset=0):
        allm = self.ensure_loaded()["models"]
        kw = (keyword or "").strip().lower()
        out = []
        for m in allm:
            if kw and not (kw in m["name"].lower() or kw in m["id"].lower()
                           or kw in (m["vendor"].get("name") or "").lower()):
                continue
            if vendors and m["vendorKey"] not in vendors:
                continue
            if only_free and not m["isFree"]:
                continue
            if only_vision and not m["supportsVision"]:
                continue
            if only_text_only and m["supportsVision"]:
                continue
            out.append(m)
        if sort == "PRICE_ASC":
            out.sort(key=lambda m: m["blendedPrice"])
        elif sort == "PRICE_DESC":
            out.sort(key=lambda m: -m["blendedPrice"])
        elif sort == "NEWEST":
            out.sort(key=lambda m: -m["releasedTs"])
        elif sort == "CONTEXT":
            out.sort(key=lambda m: -m["contextLength"])
        elif sort == "NAME":
            out.sort(key=lambda m: m["name"].lower())
        total = len(out)
        return {"total": total, "models": out[offset:offset + limit]}

    def vendors_in_use(self):
        allm = self.ensure_loaded()["models"]
        groups = {}
        for m in allm:
            groups.setdefault(m["vendorKey"], []).append(m)
        out = []
        for key, lst in groups.items():
            out.append({"vendor": lst[0]["vendor"], "count": len(lst)})
        out.sort(key=lambda x: -x["count"])
        return out
