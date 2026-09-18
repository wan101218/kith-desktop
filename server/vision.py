# -*- coding: utf-8 -*-
"""视觉桥接（GLM-4V）+ 文生图客户端 —— 与安卓端 VisionBridge / ImageGenClient 同构。

看图能力的透明补齐：角色模型支持读图 → 直接多模态；不支持 → 先由视觉模型
转述，再把描述注入对话；桥接也关着 → 明确告诉模型「你看不到这张图」。
"""
import base64
import json
import os

import llm
from kcore import now_ms

DEFAULT_QUESTION = ("请详细描述这张图片：画面主体、场景、人物外观与表情、色调氛围。"
                    "如果图中有文字，请原样读出。用中文回答，控制在 200 字以内。")
CHAT_QUESTION = ("这张图里有什么？请描述主体、场景、人物外观情绪和氛围，以及任何文字。"
                 "如果看起来是自拍、照片或截图，说明它大致是什么类型的画面。用中文，150 字以内。")


def describe(settings, image, question=DEFAULT_QUESTION):
    """描述一张图。成功返回 (text, None)，失败返回 (None, 中文原因)。"""
    try:
        if not settings.state.get("visionEnabled"):
            raise ValueError("视觉桥接未启用")
        key = (settings.state.get("visionApiKey") or "").strip()
        if not key:
            raise ValueError("没有配置视觉模型的 API Key")
        base = (settings.state.get("visionBaseUrl") or "").strip().rstrip("/")
        url = base + "/chat/completions"
        body = {
            "model": (settings.state.get("visionModel") or "").strip() or DEFAULT_VISION_MODEL_KEY,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": _normalize(image)}},
            ]}],
            "temperature": 0.3,
            "max_tokens": 900,
        }
        code, raw = llm._post_json(url, body, {"Authorization": f"Bearer {key}"}, timeout=(30, 120))
        if not (200 <= code <= 299):
            raise ValueError(_friendly_http(code, raw))
        root = json.loads(raw)
        err = root.get("error")
        if isinstance(err, dict):
            raise ValueError(err.get("message") or "视觉模型返回错误")
        choices = root.get("choices") or []
        text = ""
        if choices:
            text = ((choices[0].get("message") or {}).get("content")) or ""
        if not text:
            raise ValueError("视觉模型没有返回内容")
        return text.strip(), None
    except Exception as e:
        msg = str(e) if str(e) else e.__class__.__name__
        if isinstance(e, ValueError):
            msg = str(e)
        else:
            msg = llm.friendly_error(e)
        return None, msg


def as_injection(description, sender_name):
    return (f"[{sender_name} 发来了一张图片。你看不到图本身，但有人帮你描述了它的内容：{description}]"
            " 请像真的看到了一样自然地回应，不要提及「描述」「转述」这类字眼。")


def _normalize(image):
    if image.startswith("http") or image.startswith("data:"):
        return image
    if not os.path.exists(image):
        raise ValueError(f"找不到图片文件：{image}")
    if os.path.getsize(image) > 4 * 1024 * 1024:
        raise ValueError("图片超过 4MB，视觉模型无法处理，请压缩后重试")
    return llm.normalize_image(image)


def _friendly_http(code, raw):
    detail = ""
    try:
        detail = ((json.loads(raw).get("error") or {}).get("message")) or ""
    except (ValueError, AttributeError):
        detail = (raw or "")[:200]
    heads = {401: "视觉模型密钥无效（401），可在设置里换成你自己的 Key",
             429: "视觉模型额度用尽或请求过频（429），可在设置里换成你自己的 Key"}
    head = heads.get(code, f"视觉模型调用失败（{code}）")
    return f"{head}：{detail}" if detail else head


DEFAULT_VISION_MODEL_KEY = "glm-4v-flash"


# ── 文生图 ──────────────────────────────────────────────────────────────────

# 人工维护的预设表（modelwatch 的 modalities 是输入模态，不能用来筛生图模型）
IMAGE_PRESETS = {
    "gpt-image-2": {"name": "GPT Image 2（云舟）", "vendorKey": "Yunzhou", "priceHint": "按云舟站点计价", "style": "OPENAI", "note": "云舟中转站的生图通道，内置接入点开箱即用；返回图床 URL，由应用自动转存到社会媒体目录"},
    "black-forest-labs/FLUX.1-schnell": {"name": "FLUX.1 schnell", "vendorKey": "SiliconFlow", "priceHint": "免费", "free": True, "style": "OPENAI", "note": "硅基流动提供的免费 FLUX 快速版，出图块、质量够用，适合批量生成 NPC 头像"},
    "cogview-3-flash": {"name": "CogView-3-Flash", "vendorKey": "CogView", "priceHint": "免费", "free": True, "style": "ZHIPU", "note": "智谱免费生图，中文提示词理解好"},
    "doubao-seedream-3-0-t2i-250415": {"name": "即梦 Seedream 3.0", "vendorKey": "Seedream", "priceHint": "约 ¥0.26 / 张", "style": "OPENAI", "ratios": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"], "note": "中文写实与国风表现最好的一档，豆包同源"},
    "wanx2.1-t2i-turbo": {"name": "通义万相 2.1 Turbo", "vendorKey": "Wanx", "priceHint": "约 ¥0.14 / 张", "style": "DASHSCOPE_ASYNC", "note": "便宜、稳定，适合给路人 NPC 批量出图"},
    "cogview-4": {"name": "CogView-4", "vendorKey": "CogView", "priceHint": "约 ¥0.1 / 张", "style": "ZHIPU", "note": "中文语义准确，指令跟随好"},
    "Kwai-Kolors/Kolors": {"name": "可图 Kolors", "vendorKey": "Kolors", "priceHint": "约 ¥0.1 / 张", "style": "OPENAI", "note": "人像质感好，画角色立绘比较稳"},
    "gpt-image-1": {"name": "GPT Image 1", "vendorKey": "OpenAI", "priceHint": "约 $0.04 / 张起", "style": "OPENAI", "returnsBase64": True, "note": "指令跟随最强，适合精确描述的角色外观"},
    "dall-e-3": {"name": "DALL·E 3", "vendorKey": "OpenAI", "priceHint": "约 $0.04 / 张", "style": "OPENAI", "ratios": ["1:1", "16:9", "9:16"]},
    "flux-pro-1.1": {"name": "FLUX 1.1 Pro", "vendorKey": "BlackForest", "priceHint": "约 $0.04 / 张", "style": "VENDOR_NATIVE", "note": "写实细节与光影最好的一档"},
    "dall-e-3-hd": {"name": "Stable Image Core", "vendorKey": "Stability", "priceHint": "约 $0.03 / 张", "style": "VENDOR_NATIVE"},
    "V_2": {"name": "Ideogram V2", "vendorKey": "Ideogram", "priceHint": "约 $0.08 / 张", "style": "VENDOR_NATIVE", "note": "图内文字渲染最准，适合带字的场景图"},
    "recraftv3": {"name": "Recraft V3", "vendorKey": "Recraft", "priceHint": "约 $0.04 / 张", "style": "VENDOR_NATIVE"},
    "imagen-4.0-generate-001": {"name": "Imagen 4", "vendorKey": "Google", "baseUrl": "https://generativelanguage.googleapis.com/v1beta/openai", "priceHint": "约 $0.04 / 张", "style": "OPENAI"},
    "sd3.5-large": {"name": "Stable Diffusion 3.5 Large", "vendorKey": "Stability", "priceHint": "约 $0.065 / 张", "style": "VENDOR_NATIVE"},
    "midjourney": {"name": "Midjourney（需中转）", "vendorKey": "Midjourney", "priceHint": "按中转商计价", "style": "VENDOR_NATIVE", "note": "官方无公开 API，需填入第三方中转地址"},
}

DEFAULT_RATIOS = ["1:1", "3:4", "4:3", "16:9", "9:16"]


def image_presets_payload():
    out = []
    for mid, p in IMAGE_PRESETS.items():
        out.append({"modelId": mid, "name": p["name"], "vendorKey": p["vendorKey"],
                    "vendor": {"key": p["vendorKey"]}, "baseUrl": p.get("baseUrl", ""),
                    "priceHint": p["priceHint"], "free": p.get("free", False),
                    "ratios": p.get("ratios", DEFAULT_RATIOS), "style": p["style"],
                    "note": p.get("note", "")})
    return out


def size_for(ratio, long_edge=1024):
    dims = {"1:1": (1, 1), "3:4": (3, 4), "4:3": (4, 3), "16:9": (16, 9),
            "9:16": (9, 16), "3:2": (3, 2), "2:3": (2, 3)}
    w, h = dims.get(ratio, (1, 1))
    if w >= h:
        return f"{long_edge}x{long_edge * h // w}"
    return f"{long_edge * w // h}x{long_edge}"


def generate_image(store, sid, endpoint, model_id, prompt, ratio="1:1", style=""):
    """生成图片并落盘到社会 media 目录。返回 (GeneratedImage, error)。"""
    try:
        if not (prompt or "").strip():
            raise ValueError("提示词为空")
        if not (endpoint.get("apiKey") or "").strip():
            raise ValueError("没有配置生图模型的 API Key")
        preset = IMAGE_PRESETS.get(model_id)
        api_style = (preset or {}).get("style", "OPENAI")
        base = ((preset or {}).get("baseUrl") or endpoint.get("baseUrl") or "").strip().rstrip("/")
        full_prompt = f"{prompt}，{style}" if style else prompt

        if api_style == "VENDOR_NATIVE":
            raise ValueError(
                f"「{model_id}」用的是厂商私有接口，Kith 暂未内置适配。"
                "可以在设置里换用 OpenAI 兼容的生图模型（如硅基流动 FLUX、智谱 CogView）。")
        elif api_style == "OPENAI":
            body = {"model": model_id, "prompt": full_prompt, "n": 1, "size": size_for(ratio)}
            if not (preset or {}).get("returnsBase64"):
                body["response_format"] = "url"
            code, raw = llm._post_json(base + "/images/generations", body,
                                       {"Authorization": f"Bearer {(endpoint.get('apiKey') or '').strip()}"},
                                       timeout=(30, 300))
            if not (200 <= code <= 299):
                raise ValueError(_img_http_err(code, raw))
            root = json.loads(raw)
            data = root.get("data") or []
            if not data:
                raise ValueError("生图没有返回任何图片")
            first = data[0] or {}
            remote = first.get("url") or ""
            if not remote and first.get("b64_json"):
                remote = _write_b64_tmp(store, first["b64_json"])
            if not remote:
                raise ValueError("生图返回里既没有 url 也没有 b64_json")
        elif api_style == "ZHIPU":
            body = {"model": model_id, "prompt": full_prompt, "n": 1, "size": "1024x1024"}
            code, raw = llm._post_json(base + "/images/generations", body,
                                       {"Authorization": f"Bearer {(endpoint.get('apiKey') or '').strip()}"},
                                       timeout=(30, 300))
            if not (200 <= code <= 299):
                raise ValueError(_img_http_err(code, raw))
            root = json.loads(raw)
            data = root.get("data") or []
            remote = (data[0].get("url") if data and isinstance(data[0], dict) else "") or ""
            if not remote:
                raise ValueError("智谱生图没有返回图片地址")
        elif api_style == "DASHSCOPE_ASYNC":
            auth = {"Authorization": f"Bearer {(endpoint.get('apiKey') or '').strip()}",
                    "X-DashScope-Async": "enable"}
            size = size_for(ratio).replace("x", "*")
            submit_body = {"model": model_id, "input": {"prompt": full_prompt},
                           "parameters": {"size": size, "n": 1}}
            code, raw = llm._post_json(base + "/services/aigc/text2image/image-synthesis",
                                       submit_body, auth, timeout=(30, 120))
            if not (200 <= code <= 299):
                raise ValueError(_img_http_err(code, raw))
            task_id = ((json.loads(raw).get("output") or {}).get("task_id")) or ""
            if not task_id:
                raise ValueError(f"万相没有返回 task_id：{raw[:200]}")
            import time
            deadline = now_ms() + 90_000
            remote = ""
            while now_ms() < deadline:
                time.sleep(2.0)
                poll = llm.get_text(base + "/tasks/" + task_id, auth, timeout=30)
                if not poll["ok"]:
                    continue
                try:
                    out = json.loads(poll["body"]).get("output") or {}
                except ValueError:
                    continue
                status = out.get("task_status") or ""
                if status == "SUCCEEDED":
                    results = out.get("results") or []
                    remote = (results[0].get("url") if results and isinstance(results[0], dict) else "") or ""
                    if not remote:
                        raise ValueError("万相任务成功但没有返回图片地址")
                    break
                if status in ("FAILED", "CANCELED"):
                    raise ValueError(f"万相生成失败：{out.get('message') or out.get('code') or ''}")
            if not remote:
                raise ValueError("万相生成超时（超过 90 秒）")
        else:
            raise ValueError(f"不支持的生图接口形态：{api_style}")

        local = _persist(store, sid, remote)
        return {"localPath": local, "remoteUrl": remote if remote.startswith("http") else ""}, None
    except Exception as e:
        msg = llm.friendly_error(e) if not isinstance(e, ValueError) else str(e)
        return None, msg


def _write_b64_tmp(store, b64):
    data = base64.b64decode(b64)
    d = store.media_dir("_tmp")
    path = os.path.join(d, f"gen_{now_ms()}.png")
    with open(path, "wb") as f:
        f.write(data)
    return path


def _persist(store, sid, src):
    """把图片保存到社会目录。已是本地文件则直接搬过来；下载失败退回远程地址。"""
    if not src.startswith("http"):
        if not os.path.exists(src):
            return src
        with open(src, "rb") as f:
            data = f.read()
        ref = store.save_media(sid, data, os.path.splitext(src)[1].lstrip(".") or "png")
        try:
            os.remove(src)
        except OSError:
            pass
        return ref
    try:
        data = llm.download_bytes(src)
        return store.save_media(sid, data, llm.sniff_ext(data))
    except Exception:
        return src


def _img_http_err(code, raw):
    detail = ""
    try:
        detail = ((json.loads(raw).get("error") or {}).get("message")) or ""
    except (ValueError, AttributeError):
        detail = (raw or "")[:200]
    heads = {401: "生图密钥无效（401）", 402: f"生图额度不足或请求过频（{code}）",
             404: "生图模型不存在（404），确认模型名与接入地址",
             429: f"生图额度不足或请求过频（{code}）"}
    head = heads.get(code, f"生图请求失败（{code}）")
    return f"{head}：{detail}" if detail else head
