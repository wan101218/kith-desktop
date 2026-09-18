# -*- coding: utf-8 -*-
"""OpenAI 兼容对话客户端（流式/非流式/多模态）—— 与安卓端 LlmClient.kt 同构。

- 刻意不发送 stream_options.include_usage（部分厂商会因该字段直接 400）
- 思维链模型的 reasoning_content 刻意丢弃
- 鉴权差异显式建模：Bearer / x-api-key(Anthropic) / x-goog-api-key
"""
import base64
import json
import mimetypes
import os
import socket
import ssl
import urllib.error
import urllib.request


def _http_error_message(code, raw):
    detail = ""
    try:
        detail = ((json.loads(raw).get("error") or {}).get("message")) or ""
    except (ValueError, AttributeError):
        detail = (raw or "")[:200]
    heads = {
        400: "请求被拒绝（400）", 401: "密钥无效或未填写（401）", 402: "账户余额不足（402）",
        403: "没有访问该模型的权限（403）", 404: "模型不存在或地址不对（404）",
        422: "参数不合法（422）", 429: "请求过于频繁，稍后再试（429）",
    }
    if code in heads:
        head = heads[code]
    elif 500 <= code <= 599:
        head = f"服务端错误（{code}），通常是厂商临时故障"
    else:
        head = f"请求失败（{code}）"
    return f"{head}：{detail}" if detail else head


def friendly_error(e) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return _http_error_message(e.code, body)
    if isinstance(e, urllib.error.URLError):
        reason = e.reason
        if isinstance(reason, socket.gaierror):
            return "无法解析域名，检查网络或接入地址"
        if isinstance(reason, ssl.SSLError):
            return "HTTPS 握手失败，检查接入地址是否正确"
        if isinstance(reason, socket.timeout):
            return "请求超时，可能是上下文太长或厂商响应慢"
        return f"网络不通：{reason}"
    if isinstance(e, socket.timeout):
        return "请求超时，可能是上下文太长或厂商响应慢"
    if isinstance(e, ssl.SSLError):
        return "HTTPS 握手失败，检查接入地址是否正确"
    return str(e) or e.__class__.__name__



# ── 接入点模型名校验（与安卓端 wireModelId / fetchEndpointModels 同构）────────

_ENDPOINT_MODELS_CACHE = {}  # endpointId -> [裸名, ...] | None（拉取失败不缓存）


def wire_model_id(endpoint, model_id):
    """目录里的 id 带厂商前缀（deepseek/deepseek-v4），非 OpenRouter 的接入点
    在线上要用裸名 —— OpenRouter 保留全名。"""
    vendor = (endpoint.get("vendor") or "").strip().lower()
    if vendor == "openrouter":
        return model_id
    slash = model_id.find("/")
    return model_id[slash + 1:] if slash > 0 else model_id


def fetch_endpoint_models(endpoint):
    """GET {root}/models，返回排序后的裸名列表；失败抛异常由调用方决定放行。"""
    base = (endpoint.get("baseUrl") or "").strip().rstrip("/")
    root = base[:-len("/chat/completions")] if base.endswith("/chat/completions") else base
    url = root + "/models"
    code, raw = None, ""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "KithDesktop/1.0")
    for k, v in auth_headers(endpoint).items():
        if v:
            req.add_header(k, v)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
        code = resp.getcode()
        raw = resp.read().decode("utf-8", errors="replace")
    if not (200 <= code <= 299):
        raise RuntimeError(f"HTTP {code}")
    data = json.loads(raw).get("data") or []
    names = sorted(x.get("id") or "" for x in data if isinstance(x, dict) and x.get("id"))
    return names


def reject_if_model_unknown(endpoint, wire_id):
    """发送前防呆：已拉到真实模型列表且 wire_id 不在其中 → 给可操作的错误信息。"""
    cached = _ENDPOINT_MODELS_CACHE.get(endpoint.get("id"))
    known = cached
    if known is None:
        try:
            known = fetch_endpoint_models(endpoint)
            _ENDPOINT_MODELS_CACHE[endpoint.get("id")] = known
        except Exception:
            known = []  # 拉取失败 → 放行，交给服务端判
    if not known or wire_id in known:
        return None
    return ("模型「" + wire_id + "」不被该接入点支持。它只支持：" + "、".join(known[:12]) +
            ("…" if len(known) > 12 else "") + "。请到模型选择页最顶上「此接入点支持的模型」区重新选择。")


def endpoint_models_cached(endpoint):
    """供选择器展示：返回缓存的模型名列表；未拉取过则现场拉一次（带 8 秒超时）。"""
    eid = endpoint.get("id")
    if eid in _ENDPOINT_MODELS_CACHE:
        return _ENDPOINT_MODELS_CACHE[eid]
    try:
        names = fetch_endpoint_models(endpoint)
        _ENDPOINT_MODELS_CACHE[eid] = names
        return names
    except Exception:
        return []

def chat_url(endpoint):
    base = (endpoint.get("baseUrl") or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def auth_headers(endpoint):
    key = (endpoint.get("apiKey") or "").strip()
    if not key:
        return {}
    if endpoint.get("vendor") == "Anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {key}"}


def normalize_image(input_path):
    """本地文件路径 → data URI；http/data 开头的原样返回。"""
    if input_path.startswith("http") or input_path.startswith("data:"):
        return input_path
    if not os.path.exists(input_path):
        return input_path
    ext = os.path.splitext(input_path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
    with open(input_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_body(model_id, turns, temperature, max_tokens, stream, json_mode=False):
    messages = []
    for t in turns:
        msg = {"role": t["role"]}
        images = t.get("images") or []
        if not images:
            msg["content"] = t["content"]
        else:
            parts = []
            if t.get("content"):
                parts.append({"type": "text", "text": t["content"]})
            for img in images:
                parts.append({"type": "image_url", "image_url": {"url": normalize_image(img)}})
            msg["content"] = parts
        messages.append(msg)
    body = {"model": model_id, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "stream": stream}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


def _post_json(url, body, headers, timeout=(30, 300)):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        if v:
            req.add_header(k, v)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout[1], context=ctx) as resp:
        return resp.getcode(), resp.read().decode("utf-8", errors="replace")


def complete(endpoint, model_id, turns, temperature=0.85, max_tokens=2048, json_mode=False):
    """非流式补全。旁白、重要性判断、视觉描述这类「要完整结果」的调用走这里。"""
    wire_id = wire_model_id(endpoint, model_id)
    reject = reject_if_model_unknown(endpoint, wire_id)
    if reject:
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": wire_id, "error": reject}
    url = chat_url(endpoint)
    body = build_body(wire_id, turns, temperature, max_tokens, stream=False, json_mode=json_mode)
    try:
        code, raw = _post_json(url, body, auth_headers(endpoint))
    except Exception as e:
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": wire_id,
                "error": friendly_error(e)}
    return parse_completion(code, raw, wire_id)


def parse_completion(code, raw, model_id):
    if not (200 <= code <= 299):
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": model_id,
                "error": _http_error_message(code, raw)}
    try:
        root = json.loads(raw)
    except ValueError:
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": model_id,
                "error": f"返回内容不是合法 JSON：{raw[:200]}"}
    err = root.get("error")
    if isinstance(err, dict):
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": model_id,
                "error": err.get("message") or "模型返回错误"}
    choices = root.get("choices") or []
    choice = choices[0] if choices else None
    text = ""
    if isinstance(choice, dict):
        msg = choice.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):  # 少数厂商把 content 拆成片段数组
            text = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    usage = root.get("usage") or {}
    in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if not text and choice is None:
        return {"text": "", "inputTokens": 0, "outputTokens": 0, "modelId": model_id,
                "error": "模型没有返回任何内容"}
    return {"text": text, "inputTokens": in_tok, "outputTokens": out_tok,
            "modelId": model_id, "error": ""}


def stream_chat(endpoint, model_id, turns, temperature=0.9, max_tokens=2048):
    """流式补全生成器：yield {"type":"delta","text":...} / {"type":"usage",...} / {"type":"finished"}。

    抛异常时由上层捕获转成 Failed 事件。
    """
    wire_id = wire_model_id(endpoint, model_id)
    reject = reject_if_model_unknown(endpoint, wire_id)
    if reject:
        raise RuntimeError(reject)
    model_id = wire_id
    url = chat_url(endpoint)
    body = build_body(model_id, turns, temperature, max_tokens, stream=True)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    for k, v in auth_headers(endpoint).items():
        if v:
            req.add_header(k, v)

    ctx = ssl.create_default_context()
    finish = ""
    with urllib.request.urlopen(req, timeout=600, context=ctx) as resp:
        if not (200 <= resp.getcode() <= 299):
            raw = resp.read().decode("utf-8", errors="replace")
            raise RuntimeError(_http_error_message(resp.getcode(), raw))
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload:
                continue
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except ValueError:
                continue
            err = chunk.get("error")
            if isinstance(err, dict):
                raise RuntimeError(err.get("message") or "模型在流中返回了错误")
            usage = chunk.get("usage")
            if isinstance(usage, dict):
                in_tok = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                out_tok = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
                if in_tok > 0 or out_tok > 0:
                    yield {"type": "usage", "inputTokens": in_tok, "outputTokens": out_tok}
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0] or {}
            fr = choice.get("finish_reason")
            if fr and fr != "null":
                finish = fr
            delta = choice.get("delta") or {}
            piece = delta.get("content") or ""
            if piece:
                yield {"type": "delta", "text": piece}
    yield {"type": "finished", "reason": finish or "stop"}


def get_text(url, headers=None, timeout=30):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "KithDesktop/1.0")
    for k, v in (headers or {}).items():
        if v:
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"code": resp.getcode(), "body": resp.read().decode("utf-8", errors="replace"), "ok": True}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {"code": e.code, "body": body, "ok": False}
    except Exception as e:
        return {"code": 0, "body": friendly_error(e), "ok": False}


def download_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "KithDesktop/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def sniff_ext(data: bytes) -> str:
    if len(data) > 8 and data[0] == 0x89 and data[1] == ord("P"):
        return "png"
    if len(data) > 3 and data[0] == 0xFF and data[1] == 0xD8:
        return "jpg"
    if len(data) > 12 and data[:4] == b"RIFF":
        return "webp"
    return "png"
