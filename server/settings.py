# -*- coding: utf-8 -*-
"""全局设置 —— 跨社会共享；字段与安卓端 SettingsSnapshot 兼容。存 data/settings.json。"""
import json
import os
import threading

from kcore import now_ms
from store import model_ref_json, to_model_ref

# 视觉桥接只预置接入点和模型名，Key 留空由用户自己填。
# 真实密钥一律不写进源码：仓库公开，提交即泄漏。
DEFAULT_VISION_BASE = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_VISION_KEY = ""
DEFAULT_VISION_MODEL = "glm-4v-flash"

DEFAULTS = {
    "endpoints": [],
    "savedModels": [],
    "visionEnabled": True,
    "visionBaseUrl": DEFAULT_VISION_BASE,
    "visionApiKey": DEFAULT_VISION_KEY,
    "visionModel": DEFAULT_VISION_MODEL,
    "visionNoticeAccepted": False,
    "narratorAutoAssignModel": True,
    "narratorAutoLinkRelations": True,
    "godViewEnabled": True,
    "graphLayout": "TREE",
    "themeMode": "LIGHT",
    "catalogUrl": "",
    "catalogRefreshedAt": 0,
    "usdToCnyRate": 7.2,
    "autoNarratorOnEnter": False,
    "guardEnabled": False,
    "guardUnderSpecNoticeShown": False,
    # 桌面端自有字段：内置接入点只种一次（与安卓端 KEY_BUILTIN_SEEDED 语义一致）
    "builtinSeeded": False,
}

# 内置云舟生图接入点：预置厂商与地址省去手输，Key 留空由用户填自己的
BUILTIN_YUNZHOU_ENDPOINT_ID = "builtin_yunzhou_image"
BUILTIN_YUNZHOU_BASE = "https://cli.999554.xyz/v1"
BUILTIN_YUNZHOU_KEY = ""


class AppSettings:
    def __init__(self, path: str):
        self.path = path
        # 必须可重入：upsert/remove/update 持锁期间会再调 save()，普通 Lock 会自死锁
        # （症状：保存接入点等配置请求永不返回，前端"点了没反应"）
        self.lock = threading.RLock()
        self.state = dict(DEFAULTS)
        self.load()
        self.seed_builtin_endpoints()

    def seed_builtin_endpoints(self):
        """预置内置云舟生图接入点：地址和厂商填好，Key 留空等用户补。

        只在首次启动打点时执行一次；用户之后删掉也不复活 —— 自动恢复用户明确
        删除的东西是反直觉的。注意 state 变更必须落盘（save 内部持可重入锁）。
        """
        if self.state.get("builtinSeeded"):
            return
        self.state["builtinSeeded"] = True
        if not self.endpoint(BUILTIN_YUNZHOU_ENDPOINT_ID):
            self.state["endpoints"] = self.state.get("endpoints", []) + [{
                "id": BUILTIN_YUNZHOU_ENDPOINT_ID,
                "label": "云舟API（内置）",
                "vendor": "Yunzhou",
                "kind": "IMAGE",
                "baseUrl": BUILTIN_YUNZHOU_BASE,
                "apiKey": BUILTIN_YUNZHOU_KEY,
                "createdAt": now_ms(),
            }]
        self.save()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                merged = dict(DEFAULTS)
                merged.update({k: v for k, v in raw.items() if k in DEFAULTS})
                merged["endpoints"] = [e for e in raw.get("endpoints") or [] if isinstance(e, dict)]
                merged["savedModels"] = [m for m in raw.get("savedModels") or [] if isinstance(m, dict)]
                self.state = merged
        except (OSError, ValueError):
            pass

    def save(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    # ── 接入点 ──
    def upsert_endpoint(self, ep):
        with self.lock:
            eps = [e for e in self.state["endpoints"] if e.get("id") != ep.get("id")]
            eps.append(ep)
            self.state["endpoints"] = eps
            self.save()

    def remove_endpoint(self, eid):
        with self.lock:
            self.state["endpoints"] = [e for e in self.state["endpoints"] if e.get("id") != eid]
            self.state["savedModels"] = [m for m in self.state["savedModels"] if m.get("endpointId") != eid]
            self.save()

    def endpoint(self, eid):
        return next((e for e in self.state["endpoints"] if e.get("id") == eid), None)

    # ── 已保存模型 ──
    def save_model(self, ref):
        with self.lock:
            models = [m for m in self.state["savedModels"]
                      if not (m.get("endpointId") == ref.get("endpointId") and m.get("modelId") == ref.get("modelId"))]
            models.append(model_ref_json(ref))
            self.state["savedModels"] = models
            self.save()

    def remove_saved_model(self, ref):
        with self.lock:
            self.state["savedModels"] = [
                m for m in self.state["savedModels"]
                if not (m.get("endpointId") == ref.get("endpointId") and m.get("modelId") == ref.get("modelId"))]
            self.save()

    def resolve(self, ref):
        """ModelRef → (endpoint, ref)；接入点被删掉时返回 None。"""
        if not ref:
            return None
        ep = self.endpoint(ref.get("endpointId"))
        if not ep:
            return None
        return ep, ref

    # ── 通用更新 ──
    def update(self, **kwargs):
        with self.lock:
            for k, v in kwargs.items():
                if k in DEFAULTS:
                    self.state[k] = v
            self.save()
