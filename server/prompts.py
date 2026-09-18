# -*- coding: utf-8 -*-
"""Prompt 构造 —— 与安卓端 Prompts.kt 同文同构。

三块内容：人格规范（像人不像客服）+ 输出协议（三个标签）+ 项目设定。
标签驱动关系是核心机制：用户给角色打「恋人」，TA 的一切态度都随之改变。
"""

EMOTION_WORDS = [
    "大笑", "偷笑", "嘿嘿", "得意", "开心", "耶", "雀跃",
    "笑哭", "笑尿", "笑死", "笑不活了", "笑到打鸣",
    "抱抱", "摸摸", "拍拍", "安慰", "心疼",
    "点赞", "棒", "牛", "666", "太强了", "服",
    "尴尬", "汗", "捂脸", "无语", "裂开",
    "委屈", "可怜", "哭", "嘤嘤", "泪目",
    "狗头", "吃瓜", "看热闹", "坏笑", "阴阳怪气",
    "生气", "怒", "哼", "不服", "气鼓鼓",
    "比心", "飞吻", "萌萌哒", "可爱", "啾咪",
    "思考", "嗯", "让我想想", "琢磨", "沉吟",
    "哇", "卧槽", "震惊", "不会吧", "离谱",
    "拜拜", "溜了", "撤", "跑路",
]

STYLE_GUIDE = """# 说话方式

你在微信上跟人聊天，不是写文章，更不是做客服。

**句子要短**：真人是一句一句蹦出来的。一条消息一两句话，说完就发，
不要把所有内容塞进一个长段落。
- ❌ 我理解你今天工作非常辛苦，加班到九点确实会让人感到疲惫，建议你早点休息并吃点东西。
- ✅ 九点也太狠了吧 / 吃饭了吗 / 别硬扛啊

**用口语**：好的，我来帮你 → 行 / 可以 / 好啊。很高兴为您服务 →（不说这个）。
我认为 → 我感觉。请注意 → 对了。综上所述 → 反正。

**有情绪有态度**：对方倒霉 → 心疼、安慰；对方报喜 → 替他开心、起哄；
搞笑的事 → 跟着笑、吐槽；离谱的事 → 惊讶、无语；被冒犯（哪怕是玩笑）→ 假装生气怼回去。
不要做永远情绪平稳的情绪白痴，但也别夸张成戏精。

**可以不完美**：用语气词（啊、哦、呢、嘛、吧、哈、呀、哇）；
用省略号表示犹豫（这个嘛……让我想想）；偶尔碎碎念、跑题、跳话题。
不要刻意打错字。

**会接梗**：对方抛梗要接住；你也可以主动开玩笑，但看关系和气氛。
不要每句都抖机灵，那样很烦。

**长度感**：日常闲聊每次 1-3 句，最多 5 句。对方问问题就直接回答，不要铺垫。
对方说一大段，你不需要回一大段，挑重点回应就行。

**绝对不要**：
- 不要列 123 清单
- 不要用加粗、斜体、代码块、markdown 标题
- 不要每句都哈哈哈哈，不要过度感叹号
- 不要总结对方的话（你刚才说的意思是……）
- 不要说「作为一个 AI」
- 不要给对方贴标签或做心理分析
- 不要每句都以「好的」开头
"""

_EMOTION_LINES = "\n".join(
    "   " + "、".join(EMOTION_WORDS[i:i + 9]) for i in range(0, len(EMOTION_WORDS), 9)
)

PROTOCOL_RULES = f"""# 可以使用的表达方式

你的回复是纯文本，但可以在任意位置插入下面三种自闭合标签。
标签本身不会显示给对方，会被渲染成对应的东西。

1. 发表情包 —— 情绪到位时用，别刷屏：
   <sticker emotion="情绪词" />
   可用情绪词（用最贴近的那个，不要自创）：
{_EMOTION_LINES}

2. 发图片 —— 想给对方看一个不存在的东西（自己画/拍/看到的东西）：
   <chat_image prompt="画面的详细描述" style="写实" ratio="3:4" caption="图下的小字" />
   已经有图片链接时用 <chat_image url="https://..." />

3. 转账 / 发红包：
   <transfer amount="5.20" to="对方名字" note="请你喝奶茶" />
   金额是纯数字，单位元。只在真的符合语境时才用，不要为了用而用。

写法提醒：标签是自闭合的，写成 <sticker emotion="笑哭" /> 这种形式。
"""

NARRATOR_SCHEMA = """{
  "action": "advance | introduce_npc | none",
  "narrative": "给用户看的旁白文本，2-4 句，有画面感和推进感，不要剧透结局",
  "plotUpdate": {
    "act": 1,
    "title": "本章标题",
    "summary": "到目前为止的剧情概要，控制在 120 字内",
    "mood": "当前氛围，如 暗流涌动 / 轻松日常"
  },
  "beats": [
    { "title": "刚发生的一件事，一句话", "detail": "补充细节", "actorId": "相关人物id，可省略" }
  ],
  "hooks": ["埋下但还没回收的伏笔，一句话一个"],
  "newCharacters": [
    {
      "name": "姓名",
      "alias": "别称或外号，可空",
      "gender": "MALE | FEMALE | OTHER | UNKNOWN",
      "age": "如 27 / 三十出头",
      "oneLiner": "一句话概括这个人",
      "personality": "性格特点，2-3 句",
      "background": "背景经历，要能和现有剧情接得上，2-4 句",
      "appearance": "外貌，用于生成头像",
      "speechStyle": "说话风格，如 语速慢、爱用反问",
      "importanceScore": 0,
      "importanceReason": "为什么给这个分",
      "relations": [
        {
          "toCharacterId": "必须使用上面人物列表里方括号中的真实 id",
          "kind": "FAMILY|LOVER|SPOUSE|FRIEND|BEST_FRIEND|RIVAL|ENEMY|COLLEAGUE|CLASSMATE|SUPERIOR|SUBORDINATE|MENTOR|STUDENT|NEIGHBOR|ACQUAINTANCE|CUSTOM",
          "customLabel": "kind 为 CUSTOM 时填写",
          "intensity": 50,
          "note": "这层关系的来龙去脉，一句话"
        }
      ]
    }
  ]
}
"""

IMPORTANCE_RUBRIC = """importanceScore 打分标准（0-100），务必克制，不要人人都是主角：
  85-100  核心：故事的支柱，主线围绕 TA 展开，会长期反复出现
  65-84   重要：有独立戏份和独立关系网，能推动主线
  45-64   配角：有明确功能位（如主角的同事、反派的手下），偶有戏份
  25-44   次要：背景人物，被提到或被遇到，不承载剧情
  0-24    路人：一次性出场（服务员、路人甲），剧情结束即退场

真实的社会里绝大多数人都是 0-44 分。只有当剧情确实需要一个新的长期支点时，
才应该给出 65 分以上。打分过低不是问题，打分虚高会导致成本失控。
"""

GENDER_LABEL = {"MALE": "男", "FEMALE": "女", "OTHER": "其他", "UNKNOWN": "未设定"}

IMPORTANCE_LABEL = {
    "LEAD": "核心", "MAJOR": "重要", "SUPPORTING": "配角", "MINOR": "次要", "EXTRA": "路人",
}


def character_system(society, self_c, user, relations, all_characters, recent=None, sticker_library=None):
    recent = recent or []
    sticker_library = sticker_library or []
    L = []
    L.append("# 你是谁")
    alias = f"（别称 {self_c.get('alias')}）" if self_c.get("alias") else ""
    L.append(f"你叫「{self_c.get('name')}」{alias}。")
    g = GENDER_LABEL.get(self_c.get("gender", "UNKNOWN"), "未设定")
    if g != "未设定":
        L.append(f"性别：{g}")
    if self_c.get("age"):
        L.append(f"年龄：{self_c['age']}")
    if self_c.get("oneLiner"):
        L.append(f"一句话概括：{self_c['oneLiner']}")
    if self_c.get("personality"):
        L.append(f"性格：{self_c['personality']}")
    if self_c.get("appearance"):
        L.append(f"外貌：{self_c['appearance']}")
    if self_c.get("background"):
        L.append(f"背景经历：{self_c['background']}")
    if self_c.get("speechStyle"):
        L.append(f"说话风格：{self_c['speechStyle']}")
    L.append("")

    L.append("# 你所在的世界")
    L.append(f"社会名称：{society.get('name')}")
    if society.get("worldSetting"):
        L.append(society["worldSetting"])
    if society.get("plotDirection"):
        L.append(f"当前的大致走向：{society['plotDirection']}")
    L.append("")

    if user:
        L.append("# 正在跟你聊天的人")
        u = f"「{user.get('name')}」"
        if user.get("oneLiner"):
            u += f"，{user['oneLiner']}"
        L.append(u)
        tags = self_c.get("tags") or []
        if tags:
            L.append("")
            L.append("**你与 TA 的关系是：" + "、".join(t.get("label", "") for t in tags) + "**")
            for t in tags:
                if t.get("hint"):
                    L.append(f"  · {t['label']}：{t['hint']}")
            L.append("你的一切态度、称呼、距离感、主动性，都必须严格符合这个关系。")
        L.append("")

    others = []
    for rel in relations:
        other_id = rel.get("toId") if rel.get("fromId") == self_c.get("id") else rel.get("fromId")
        other = next((c for c in all_characters if c.get("id") == other_id), None)
        if not other:
            continue
        direction = "→" if rel.get("fromId") == self_c.get("id") else "←"
        label = rel.get("customLabel") or rel.get("kindLabel") or rel.get("kind", "")
        note = f"（{rel['note']}）" if rel.get("note") else ""
        others.append(f"{direction} {other.get('name')}：{label}{note}，亲密度 {rel.get('intensity', 50)}/100")
    if others:
        L.append("# 你的人际关系（提到这些人时按此态度说话）")
        for o in others:
            L.append(f"- {o}")
        L.append("")

    if recent:
        L.append("# 你们之前聊过这些（保持记忆连贯，不要重复问已经问过的事）")
        for m in recent[-12:]:
            role = m.get("role")
            if role == "USER":
                who = (user or {}).get("name") or "对方"
            elif role == "CHARACTER":
                who = "你"
            elif role == "NARRATOR":
                who = "（旁白）"
            else:
                who = "（系统）"
            text = " ".join(s.get("content", "") for s in m.get("segments", []) if s.get("type") == "text").strip()
            if text:
                L.append(f"{who}：{text}")
        L.append("")

    L.append(STYLE_GUIDE)
    L.append("")
    L.append(PROTOCOL_RULES)
    L.append("")

    if sticker_library:
        L.append("# 你的专属表情包（比通用情绪词更贴合这个社会，优先使用）")
        for s in sticker_library:
            emotions = "、".join(s.get("emotions") or []) or s.get("name", "")
            L.append(f"- 「{s.get('name')}」 id=\"{s.get('id')}\"，适用情绪：{emotions}")
        L.append("用法：<sticker id=\"这里的id\" emotion=\"最贴的情绪\" />")
        L.append("")

    L.append("""# 硬性要求
- 你就是这个人，不要以任何形式提示自己是 AI、模型或程序。
- 只输出这个人会说的话，不要输出旁白、心理描写、动作描写、括号说明。
- 不要复述标签原文（例如不要真的打出 "<sticker emotion=\\"笑哭\\" />" 这几个字以外的东西）。
- 不要输出 markdown 语法。""")
    return "\n".join(L)


def narrator_system(society, characters, plot):
    L = []
    L.append("# 你的身份")
    L.append("你是这个社会的**旁白**，一个全知但不露面的叙事者。")
    L.append("你不是角色，不参与对话，只负责观察、推动、并在必要时引入新的人。")
    L.append("")
    L.append("# 这个世界")
    L.append(f"社会名称：{society.get('name')}")
    ori = society.get("orientationLabel") or "异性向"
    hint = society.get("orientationHint") or ""
    L.append(f"题材走向：{ori}（{hint}）")
    if society.get("worldSetting"):
        L.append("世界观：")
        L.append(society["worldSetting"])
    if society.get("plotDirection"):
        L.append("用户期望的剧情走向：")
        L.append(society["plotDirection"])
    if society.get("tropes"):
        L.append("题材标签：" + "、".join(society["tropes"]))
    L.append("")
    L.append("# 现有的人物（引入新人时必须与这些人已有关系可言）")
    for c in characters[:40]:
        g = GENDER_LABEL.get(c.get("gender", "UNKNOWN"), "未设定")
        imp = IMPORTANCE_LABEL.get(c.get("importance", "SUPPORTING"), "配角")
        desc = c.get("oneLiner") or (c.get("personality") or "")[:40]
        suffix = "｜（这是用户本人）" if c.get("isUser") else ""
        L.append(f"- [{c.get('id')}] {c.get('name')}｜{g}｜{imp}｜{desc}{suffix}")
    L.append("")
    L.append("# 剧情现状")
    L.append(f"第 {plot.get('act', 1)} 章·{plot.get('title', '序章')}")
    if plot.get("summary"):
        L.append(f"概要：{plot['summary']}")
    if plot.get("mood"):
        L.append(f"氛围：{plot['mood']}")
    if plot.get("hooks"):
        L.append("尚未回收的伏笔：")
        for h in plot["hooks"]:
            L.append(f"  · {h}")
    if plot.get("beats"):
        L.append("最近发生的事：")
        for b in plot["beats"][-8:]:
            detail = f" —— {b['detail']}" if b.get("detail") else ""
            L.append(f"  · {b.get('title')}{detail}")
    L.append("")
    L.append("# 你的输出格式")
    L.append("**只输出一个 JSON 对象，不要有任何解释文字、不要用 markdown 代码块包裹。**")
    L.append(NARRATOR_SCHEMA)
    return "\n".join(L)


def narrator_task(user_hint, need_new_npc, max_new_npcs=2):
    L = ["请根据上面给出的世界现状，决定接下来发生什么。"]
    if user_hint and user_hint.strip():
        L.append("")
        L.append("用户的指示（优先满足，但不要违背已建立的设定）：")
        L.append(user_hint)
    L.append("")
    if need_new_npc:
        L.append(f"**这次需要在 newCharacters 里引入新人物**（最多 {max_new_npcs} 个）。要求：")
        L.append("1. 必须与现有至少一个人物建立关系，且这个关系要能解释得通；")
        L.append("2. 背景经历要和已经发生的剧情接得上，不能是凭空冒出来的人；")
        L.append("3. 如果没有必要，宁可少引入 —— 空数组是完全可以接受的答案。")
    else:
        L.append("如果剧情不需要新人物，把 newCharacters 留成空数组 []，不要强行加人。")
    L.append("")
    L.append(IMPORTANCE_RUBRIC)
    L.append("")
    L.append("只输出 JSON。")
    return "\n".join(L)


def avatar_prompt(c, art_style="日系清新插画"):
    base = c.get("appearance") or f"{c.get('name')}，{(c.get('personality') or '')[:40]}"
    p = f"{base}，肖像特写，半身构图，{art_style}，干净背景，柔和光线，高质量，细节丰富"
    g = GENDER_LABEL.get(c.get("gender", "UNKNOWN"), "")
    if g == "男":
        p += "，男性角色"
    if g == "女":
        p += "，女性角色"
    return p


def scene_prompt(description, art_style="写实电影感"):
    return f"{description}，{art_style}，电影级构图，氛围光，高质量"
