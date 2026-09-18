# -*- coding: utf-8 -*-
"""旁白输出体检（桌面端 guard）。

与安卓端 ContentGuard 同源：两级检查里的第一级「最低层次体检」——不需要模型
就能跑：空输出、过短、退化的重复内容、协议标签未闭合。这是「旁白没有出错」
的兜底。

安卓端的第二级（Qwen3Guard 0.6B 本地安全分类）依赖 MediaPipe 端上推理，
桌面端不移植；guardEnabled 开关在桌面端只控制本体检。

项目约定：未通过也保留内容并写日志（绝不静默丢弃），只给用户明确提示。
"""

_TAGS = ("<transfer>", "<sticker>")


def sanity_check(text):
    """最低层次检查。返回错误说明字符串；None 表示通过。"""
    t = (text or "").strip()
    if not t:
        return "旁白没有输出任何内容"
    if len(t) < 20:
        return f"旁白输出过短（{len(t)} 字），疑似生成失败"
    # 退化检测：同一行重复刷屏（温度失控时会出现）
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) >= 4 and len(set(lines)) == 1:
        return "旁白输出为同一行反复重复，疑似生成异常"
    # 协议标签没闭合（半截 <transfer>、<sticker>）说明流被截断
    for tag in _TAGS:
        opens = t.count(tag)
        closes = t.count(tag.replace("<", "</"))
        if opens > closes:
            return f"旁白输出里的 {tag} 标签没有闭合，疑似流被截断"
    return None
