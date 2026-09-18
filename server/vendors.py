# -*- coding: utf-8 -*-
"""厂商注册表 —— 品牌色磁贴 + 字母徽记 + 默认 baseUrl + 别名归一化。

与安卓端 VendorRegistry.kt 同构；颜色由名称哈希派生（FNV-1a），
用户手填的新厂商也能得到稳定一致的视觉身份。
"""
import colorsys

from kcore import stable_seed

VENDORS = [
    # key, 展示名, 颜色, 徽记, baseUrl, console, 国内直连
    ("DeepSeek", "深度求索 DeepSeek", "#4D6BFE", "DS", "https://api.deepseek.com/v1", "https://platform.deepseek.com", True),
    ("Alibaba", "阿里通义 Qwen", "#615CED", "Q", "https://dashscope.aliyuncs.com/compatible-mode/v1", "https://bailian.console.aliyun.com", True),
    ("Zhipu", "智谱 GLM", "#3859FF", "ZP", "https://open.bigmodel.cn/api/paas/v4", "https://open.bigmodel.cn", True),
    ("Moonshot", "月之暗面 Kimi", "#1F1F27", "K", "https://api.moonshot.cn/v1", "https://platform.moonshot.cn", True),
    ("ByteDance", "字节豆包 Doubao", "#1868F0", "DB", "https://ark.cn-beijing.volces.com/api/v3", "https://console.volcengine.com/ark", True),
    ("MiniMax", "MiniMax 海螺", "#E8455F", "MM", "https://api.minimax.chat/v1", "https://platform.minimaxi.com", True),
    ("Tencent", "腾讯混元 Hunyuan", "#0052D9", "HY", "https://api.hunyuan.cloud.tencent.com/v1", "https://console.cloud.tencent.com/hunyuan", True),
    ("Baidu", "百度文心 ERNIE", "#2932E1", "BD", "https://qianfan.baidubce.com/v2", "https://console.bce.baidu.com/qianfan", True),
    ("Xiaomi", "小米 MiMo", "#FF6900", "MI", "", "https://xiaomi.com", True),
    ("StepFun", "阶跃星辰 Step", "#16A5A5", "SF", "https://api.stepfun.com/v1", "https://platform.stepfun.com", True),
    ("01.AI", "零一万物 Yi", "#0E4F3C", "01", "https://api.lingyiwanwu.com/v1", "https://platform.lingyiwanwu.com", True),
    ("SiliconFlow", "硅基流动 SiliconFlow", "#6E29F7", "SF", "https://api.siliconflow.cn/v1", "https://cloud.siliconflow.cn", True),
    ("OpenAI", "OpenAI", "#10A37F", "OA", "https://api.openai.com/v1", "https://platform.openai.com", False),
    ("Anthropic", "Anthropic Claude", "#D97757", "AN", "https://api.anthropic.com/v1", "https://console.anthropic.com", False),
    ("Google", "Google Gemini", "#4285F4", "G", "https://generativelanguage.googleapis.com/v1beta/openai", "https://aistudio.google.com", False),
    ("Meta", "Meta Llama", "#0866FF", "∞", "", "https://llama.com", False),
    ("Mistral", "Mistral AI", "#FA520F", "MS", "https://api.mistral.ai/v1", "https://console.mistral.ai", False),
    ("xAI", "xAI Grok", "#1A1A1A", "X", "https://api.x.ai/v1", "https://console.x.ai", False),
    ("NVIDIA", "NVIDIA NIM", "#76B900", "NV", "https://integrate.api.nvidia.com/v1", "https://build.nvidia.com", False),
    ("Microsoft", "Microsoft Azure", "#00A4EF", "AZ", "", "https://portal.azure.com", False),
    ("Amazon", "Amazon Bedrock", "#FF9900", "AWS", "", "https://console.aws.amazon.com/bedrock", False),
    ("Cohere", "Cohere", "#39594D", "CO", "https://api.cohere.ai/compatibility/v1", "https://dashboard.cohere.com", False),
    ("Perplexity", "Perplexity", "#20808D", "PP", "https://api.perplexity.ai", "https://www.perplexity.ai/settings/api", False),
    ("NousResearch", "Nous Research", "#6B5BD2", "NR", "", "https://portal.nousresearch.com", False),
    ("OpenRouter", "OpenRouter（聚合）", "#6566F1", "OR", "https://openrouter.ai/api/v1", "https://openrouter.ai/keys", False),
    ("Groq", "Groq", "#F55036", "GQ", "https://api.groq.com/openai/v1", "https://console.groq.com", False),
    ("Together", "Together AI", "#0F6FFF", "TG", "https://api.together.xyz/v1", "https://api.together.ai", False),
    ("Fireworks", "Fireworks AI", "#E4572E", "FW", "https://api.fireworks.ai/inference/v1", "https://fireworks.ai", False),
    ("Ollama", "Ollama（本地）", "#333333", "OL", "http://127.0.0.1:11434/v1", "https://ollama.com", False),
    ("LMStudio", "LM Studio（本地）", "#5A5AE6", "LM", "http://127.0.0.1:1234/v1", "https://lmstudio.ai", False),
    ("vLLM", "vLLM（自建）", "#FFB000", "vL", "http://127.0.0.1:8000/v1", "https://docs.vllm.ai", False),
    ("NewAPI", "New API / one-api 中转", "#4C8BF5", "NA", "", "", False),
    ("Seedream", "字节即梦 Seedream", "#1868F0", "SD", "https://ark.cn-beijing.volces.com/api/v3", "https://console.volcengine.com/ark", True),
    ("Wanx", "通义万相 Wanx", "#615CED", "WX", "https://dashscope.aliyuncs.com/api/v1", "https://bailian.console.aliyun.com", True),
    ("Kolors", "快手可图 Kolors", "#FF4E1F", "KO", "https://api.siliconflow.cn/v1", "", True),
    ("CogView", "智谱 CogView", "#3859FF", "CG", "https://open.bigmodel.cn/api/paas/v4", "https://open.bigmodel.cn", True),
    ("Stability", "Stability AI", "#8B5CF6", "ST", "https://api.stability.ai", "https://platform.stability.ai", False),
    ("BlackForest", "Black Forest Labs (FLUX)", "#FFD23F", "BF", "https://api.bfl.ai/v1", "https://api.bfl.ai", False),
    ("Ideogram", "Ideogram", "#EE4444", "ID", "https://api.ideogram.ai", "https://ideogram.ai", False),
    ("Recraft", "Recraft", "#F97316", "RC", "https://external.api.recraft.ai/v1", "https://recraft.ai", False),
    ("Midjourney", "Midjourney（中转）", "#1E1E24", "MJ", "", "https://midjourney.com", False),
    ("Yunzhou", "云舟API（中转）", "#1677FF", "云", "https://cli.999554.xyz/v1", "https://cli.999554.xyz/", True),
]

_BY_KEY = {v[0]: v for v in VENDORS}

ALIASES = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "alphabet": "Google",
    "alibaba": "Alibaba", "qwen": "Alibaba", "tongyi": "Alibaba",
    "meta": "Meta", "meta-llama": "Meta",
    "mistralai": "Mistral", "x-ai": "xAI", "xai": "xAI",
    "deepseek": "DeepSeek", "zhipu": "Zhipu", "z-ai": "Zhipu", "thudm": "Zhipu",
    "minimax": "MiniMax", "moonshot": "Moonshot", "moonshotai": "Moonshot",
    "bytedance": "ByteDance", "doubao": "ByteDance", "volcengine": "ByteDance",
    "tencent": "Tencent", "hunyuan": "Tencent",
    "baidu": "Baidu", "ernie": "Baidu",
    "xiaomi": "Xiaomi", "nvidia": "NVIDIA",
    "amazon": "Amazon", "aws": "Amazon",
    "microsoft": "Microsoft", "azure": "Microsoft",
    "perplexity": "Perplexity", "cohere": "Cohere",
    "nousresearch": "NousResearch", "nous": "NousResearch",
    "openrouter": "OpenRouter", "groq": "Groq",
    "together": "Together", "togethercomputer": "Together",
    "fireworks": "Fireworks", "stabilityai": "Stability",
    "black-forest-labs": "BlackForest", "bfl": "BlackForest", "ideogram-ai": "Ideogram",
    "yunzhou": "Yunzhou", "云舟": "Yunzhou",
}

_derived_cache = {}


def normalize(raw):
    key = (raw or "").strip()
    if not key or key.lower() == "unknown":
        return None
    if key in _BY_KEY:
        return key
    if key.lower() in ALIASES:
        return ALIASES[key.lower()]
    squashed = re_nonalnum(key)
    for v in VENDORS:
        if re_nonalnum(v[0]) == squashed:
            return v[0]
    return None


import re as _re


def re_nonalnum(s):
    return _re.sub(r"[^a-z0-9]", "", (s or "").lower())


def monogram_of(name: str) -> str:
    t = (name or "").strip()
    if not t:
        return "··"
    if ord(t[0]) > 0x2E80:
        return t[0]
    words = [w for w in _re.split(r"[\s._-]+", t) if w]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return (words[0][:2] if words else t[:2]).upper()


def _hsl_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5))


def vendor_of(raw):
    """返回 {key,name,color,monogram,baseUrl,console,domestic}。识别不出则按名称派生。"""
    key = normalize(raw)
    if key and key in _BY_KEY:
        v = _BY_KEY[key]
        return {"key": v[0], "name": v[1], "color": v[2], "monogram": v[3],
                "baseUrl": v[4], "console": v[5], "domestic": v[6]}
    name = (raw or "").strip()
    if not name:
        return {"key": "custom", "name": "自定义", "color": "#7A8291", "monogram": "··",
                "baseUrl": "", "console": "", "domestic": False}
    if name not in _derived_cache:
        seed = stable_seed(name)
        hue = seed % 360
        _derived_cache[name] = {"key": name, "name": name,
                                "color": _hsl_hex(hue, 0.52, 0.46),
                                "monogram": monogram_of(name),
                                "baseUrl": "", "console": "", "domestic": False}
    return _derived_cache[name]


def all_vendors():
    return [{"key": v[0], "name": v[1], "color": v[2], "monogram": v[3],
             "baseUrl": v[4], "console": v[5], "domestic": v[6]} for v in VENDORS]
