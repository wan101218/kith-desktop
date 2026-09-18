/* Kith Desktop 前端 —— 与安卓端同源的设计语言与数据协议。 */
"use strict";

/* ── 小工具 ─────────────────────────────────── */
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => (s ?? "").toString().replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nowMs = () => Date.now();

function fnv1a(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = (h * 16777619) >>> 0; } return h & 0x7fffffff; }
function hslHex(h, s, l) { const f = n => { const k = (n + h / 30) % 12; const a = s * Math.min(l, 1 - l); const v = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); return Math.round(255 * v).toString(16).padStart(2, "0"); }; return "#" + f(0) + f(8) + f(4); }
function initials(name) { const t = (name || "").trim(); if (!t) return "?"; if (t.charCodeAt(0) > 0x2e80) return t[0]; const p = t.split(/\s+/).filter(Boolean); return (p.slice(0, 2).map(x => x[0]).join("") || t[0]).toUpperCase(); }
function avatarColor(name) { const h = fnv1a(name || "?") % 360; return [hslHex(h, .52, .46), hslHex((h + 40) % 360, .5, .34)]; }
function relTime(ts) { const d = nowMs() - ts; if (d < 60e3) return "刚刚"; if (d < 3600e3) return Math.floor(d / 60e3) + " 分钟前"; if (d < 86400e3) return Math.floor(d / 3600e3) + " 小时前"; if (d < 7 * 86400e3) return Math.floor(d / 86400e3) + " 天前"; const t = new Date(ts); return `${t.getMonth() + 1}-${t.getDate()} ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`; }
function clockTime(ts) { const t = new Date(ts); return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`; }
function fmtCny(usd) { const r = (window._settings && window._settings.usdToCnyRate) || 7.2; const v = usd * r; if (v <= 0) return "¥0"; if (v < 0.01) return "<¥0.01"; if (v < 10) return "¥" + v.toFixed(3); if (v < 1000) return "¥" + v.toFixed(2); return "¥" + Math.round(v); }
function fmtTok(v) { return v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "k" : String(v); }
function toast(msg, isErr) { const el = document.createElement("div"); el.className = "toast" + (isErr ? " err" : ""); el.textContent = msg; $("#toast-root").appendChild(el); setTimeout(() => el.remove(), 3600); }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function fileToB64(f) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.onerror = rej; r.readAsDataURL(f); }); }
const SPIN = '<span class="spin"></span> ';

const IMPORTANCE = {
  LEAD: { label: "核心", tier: "PREMIUM", chat: true, color: "#F5B544" },
  MAJOR: { label: "重要", tier: "STANDARD", chat: true, color: "#6B5BD2" },
  SUPPORTING: { label: "配角", tier: "ECONOMY", chat: true, color: "#4A86C8" },
  MINOR: { label: "次要", tier: "ECONOMY", chat: false, color: "#8A92A3" },
  EXTRA: { label: "路人", tier: "ECONOMY", chat: false, color: "#AEB4C0" },
};
const RELATION_KINDS = [["FAMILY", "亲属"], ["LOVER", "恋人"], ["SPOUSE", "伴侣"], ["FRIEND", "朋友"], ["BEST_FRIEND", "挚友"], ["RIVAL", "对手"], ["ENEMY", "宿敌"], ["COLLEAGUE", "同事"], ["CLASSMATE", "同学"], ["SUPERIOR", "上司"], ["SUBORDINATE", "下属"], ["MENTOR", "师长"], ["STUDENT", "学生"], ["NEIGHBOR", "邻里"], ["ACQUAINTANCE", "点头之交"], ["CUSTOM", "自定义"]];
// 关系类型 → 连线颜色（与安卓端 RelationGraphLayout.edgeColor 同轮盘）：
// 每种关系一个专属色，不再复用主题语义色，图例里不会出现三条线挤同一个颜色
const KIND_COLOR = { FAMILY: "#D9A036", LOVER: "#F2547D", SPOUSE: "#B15CE8", FRIEND: "#4C9BE8", BEST_FRIEND: "#21B586", RIVAL: "#C9A227", ENEMY: "#E0453A", COLLEAGUE: "#7986CB", CLASSMATE: "#38BFD8", SUPERIOR: "#5C7A99", SUBORDINATE: "#A67F5A", MENTOR: "#4FBDB1", STUDENT: "#A2CE5D", NEIGHBOR: "#DD7AC8", ACQUAINTANCE: "#8A93A0", CUSTOM: "#F5B544" };
const GENDERS = [["MALE", "男"], ["FEMALE", "女"], ["OTHER", "其他"], ["UNKNOWN", "未设定"]];

function avatarHtml(c, size, ring) {
  const [c1, c2] = avatarColor(c.name);
  const bg = c.avatarUrl ? mediaUrl(c.avatarUrl) : `linear-gradient(135deg,${c1},${c2})`;
  return `<div class="avatar" style="width:${size}px;height:${size}px;font-size:${Math.round(size * .42)}px;background:${bg}">${c.avatarUrl ? "" : esc(initials(c.name))}${ring && (c.isUser || c.importance === "LEAD") ? '<span class="ring"></span>' : ""}</div>`;
}
function mediaSrc(sid, ref) { if (!ref) return ""; if (/^(https?:|data:)/.test(ref)) return ref; return "/media/" + sid + "/" + String(ref); }
function mediaUrl(ref) {
  if (!ref) return "";
  if (/^(https?:|data:)/.test(ref)) return ref;
  // 社会内上下文（聊天/人物/贴纸）：把 media/xxx 引用解析为 /media/{sid}/xxx
  const sid = S.bundle && S.bundle.society ? S.bundle.society.id : null;
  return sid ? "/media/" + sid + "/" + String(ref) : "/media/" + ref;
}
function vendorTile(v, size) { return `<span class="ep-tile" style="width:${size || 40}px;height:${size || 40}px;background:${v.color};border-radius:${Math.round((size || 40) * .3)}px">${esc(v.monogram)}</span>`; }

/* ── API ───────────────────────────────────── */
async function api(path, opts) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  let d = {};
  try { d = await r.json(); } catch (e) { }
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}
const apiGet = p => api(p);
const apiPost = (p, body) => api(p, { method: "POST", body: JSON.stringify(body || {}) });
const apiPut = (p, body) => api(p, { method: "PUT", body: JSON.stringify(body || {}) });
const apiDelete = p => api(p, { method: "DELETE" });

async function ssePost(path, body, onEvent) {
  const resp = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!resp.ok) { let d = {}; try { d = await resp.json(); } catch (e) { } throw new Error(d.error || "HTTP " + resp.status); }
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data:")) { try { onEvent(JSON.parse(line.slice(5).trim())); } catch (e) { } }
      }
    }
  }
}

/* ── HC 协议解析（与后端 / 安卓端同规则）────── */
const TAG_RE = /<(chat_image|sticker|transfer)\b[^>]*?\/?>/ig;
const ATTR_RE = /([A-Za-z_][\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
const OPEN_TAIL_RE = /<[a-z_]*$/i;
function parseTag(tag) {
  const nm = /^<\s*(chat_image|sticker|transfer)/i.exec(tag); if (!nm) return null;
  const name = nm[1].toLowerCase(); const attrs = {};
  let m; ATTR_RE.lastIndex = 0;
  while ((m = ATTR_RE.exec(tag))) attrs[m[1].toLowerCase()] = (m[2] !== undefined && m[2] !== "") ? m[2] : (m[3] ?? "");
  if (name === "sticker") { const e = attrs.emotion || "", id = attrs.id || ""; return (e || id) ? { type: "sticker", emotion: e, stickerId: id } : null; }
  if (name === "chat_image") { const u = attrs.url || "", p = attrs.prompt || "", q = attrs.search_query || ""; if (!u && !p && !q) return null; return { type: "picture", url: u, prompt: p, searchQuery: q, style: attrs.style || "", ratio: attrs.ratio || "", caption: attrs.caption || "", state: u ? "READY" : "GENERATING" }; }
  if (name === "transfer") { const a = parseFloat(attrs.amount || ""); const to = attrs.to || ""; if (isNaN(a) || !to || a < 0 || a > 1e6) return null; return { type: "transfer", amount: a, to, note: attrs.note || "", confirmed: false }; }
  return null;
}
function hcParse(raw) {
  if (!raw) return [];
  const out = []; let cursor = 0; TAG_RE.lastIndex = 0; let m;
  while ((m = TAG_RE.exec(raw))) {
    if (m.index > cursor) out.push({ type: "text", content: raw.slice(cursor, m.index) });
    const seg = parseTag(m[0]);
    out.push(seg || { type: "text", content: m[0] });
    cursor = m.index + m[0].length;
  }
  if (cursor < raw.length) out.push({ type: "text", content: raw.slice(cursor) });
  const merged = [];
  for (const s of out) { if (s.type === "text" && merged.length && merged[merged.length - 1].type === "text") merged[merged.length - 1].content += s.content; else merged.push(s); }
  return merged;
}
function hcParseStreaming(buf) { const m = OPEN_TAIL_RE.exec(buf); return hcParse(m ? buf.slice(0, m.index) : buf); }
function hcPlainText(segs) { return (segs || []).filter(s => s.type === "text").map(s => s.content).join(""); }

const SYS_STICKERS = { "大笑": ["😄", "😆"], "偷笑": ["🤭", "😏"], "嘿嘿": ["😁", "😏"], "得意": ["😎", "😏"], "开心": ["😊", "😄"], "耶": ["✌️", "🙌"], "雀跃": ["🤗", "🙌"], "笑哭": ["😂", "🤣"], "笑尿": ["🤣", "😹"], "笑死": ["😂", "💀"], "笑不活了": ["🤣", "🫠"], "笑到打鸣": ["🤣", "🐔"], "抱抱": ["🫂", "🤗"], "摸摸": ["🫳", "🥺"], "拍拍": ["🫂", "🤚"], "安慰": ["🥺", "🫂"], "心疼": ["🥺", "💔"], "点赞": ["👍", "👏"], "棒": ["👍", "⭐"], "牛": ["🐮", "💪"], "666": ["🔥", "👏"], "太强了": ["💪", "🔥"], "服": ["🙇", "👍"], "尴尬": ["😅", "😬"], "汗": ["😓", "💧"], "捂脸": ["🤦", "🫣"], "无语": ["😑", "🙃"], "裂开": ["🫠", "💥"], "委屈": ["🥺", "😞"], "可怜": ["🥺", "😢"], "哭": ["😭", "😢"], "嘤嘤": ["🥺", "😿"], "泪目": ["🥹", "😢"], "狗头": ["🐶", "🐕"], "吃瓜": ["🍉", "👀"], "看热闹": ["👀", "🍿"], "坏笑": ["😏", "😼"], "阴阳怪气": ["🙃", "😏"], "生气": ["😠", "😤"], "怒": ["😡", "💢"], "哼": ["😤", "😾"], "不服": ["😤", "🙄"], "气鼓鼓": ["😤", "😠"], "比心": ["🫰", "💕"], "飞吻": ["😘", "💋"], "萌萌哒": ["🥰", "🐰"], "可爱": ["🥰", "😊"], "啾咪": ["😘", "✨"], "思考": ["🤔", "🧐"], "嗯": ["🤔", "😶"], "让我想想": ["🤔", "💭"], "琢磨": ["🧐", "🤔"], "沉吟": ["😶", "🤔"], "哇": ["😲", "🤩"], "卧槽": ["😱", "🤯"], "震惊": ["😱", "🤯"], "不会吧": ["😳", "😲"], "离谱": ["🤯", "🫠"], "拜拜": ["👋", "🙋"], "溜了": ["🏃", "💨"], "撤": ["🏃", "👋"], "跑路": ["🏃", "💨"] };
const FALLBACK_GLYPHS = ["🙂", "😊", "💬"];
function stickerResolve(library, emotion, stickerId, seed) {
  if (stickerId) { const hit = library.find(s => s.id === stickerId); if (hit) return { kind: "image", sticker: hit }; }
  const key = (emotion || "").trim();
  if (key) { const ex = library.filter(s => (s.emotions || []).includes(key)); if (ex.length) return pickSticker(ex, seed); }
  if (key) { const fz = library.filter(s => (s.emotions || []).some(e => e.includes(key) || key.includes(e))); if (fz.length) return pickSticker(fz, seed); }
  let glyphs = null;
  if (key) { if (SYS_STICKERS[key]) glyphs = SYS_STICKERS[key]; else { const ks = Object.keys(SYS_STICKERS).filter(k => k.includes(key) || key.includes(k)); if (ks.length) { const best = ks.sort((a, b) => b.length - a.length)[0]; glyphs = SYS_STICKERS[best]; } } }
  glyphs = glyphs || FALLBACK_GLYPHS;
  const g = glyphs[seed ? Math.abs(seed) % glyphs.length : 0];
  return { kind: "emoji", glyph: g, emotion: key };
}
function pickSticker(cands, seed) { if (cands.length === 1) return { kind: "image", sticker: cands[0] }; const top = [...cands].sort((a, b) => (b.usageCount || 0) - (a.usageCount || 0)).slice(0, 3); return { kind: "image", sticker: top[seed ? Math.abs(seed) % top.length : 0] }; }

/* ── Modal ─────────────────────────────────── */
function openModal(html, opts) {
  const mask = document.createElement("div"); mask.className = "modal-mask";
  mask.innerHTML = `<div class="modal ${opts && opts.wide ? "wide" : ""}">${html}</div>`;
  mask.addEventListener("mousedown", e => { if (e.target === mask && !(opts && opts.sticky)) mask.remove(); });
  $("#modal-root").appendChild(mask);
  mask.close = () => mask.remove();
  return mask;
}
function modalHead(title) { return `<div class="modal-head"><h3>${esc(title)}</h3><button class="modal-x" onclick="this.closest('.modal-mask').remove()">✕</button></div>`; }

/* ── 全局状态与路由 ─────────────────────────── */
const S = { settings: null, templates: null, vendors: [], bundle: null, graphView: null };

async function boot() {
  try {
    S.settings = await apiGet("/api/settings");
    window._settings = S.settings;
    applyTheme();
    const [tpl, vd] = await Promise.all([apiGet("/api/templates"), apiGet("/api/vendors")]);
    S.templates = tpl; S.vendors = vd.vendors;
    route();
    window.addEventListener("hashchange", route);
  } catch (e) {
    document.getElementById("app").innerHTML = `<div style="padding:60px;text-align:center;color:var(--text-2)">服务连接失败：${esc(e.message)}<br><br><button class="btn btn-ink" onclick="location.reload()">重试</button></div>`;
  }
}
function applyTheme() {
  const mode = S.settings.themeMode;
  const sysDark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = (mode === "DARK" || (mode === "SYSTEM" && sysDark)) ? "dark" : "light";
}
function goto(hash) { if (location.hash === hash) route(); else location.hash = hash; }
// 「跟随系统」主题：系统深浅切换时立即生效（与安卓端 MainActivity 的设置流订阅同语义）
if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (S.settings && S.settings.themeMode === "SYSTEM") applyTheme(); });
// 弹出小菜单的统一外点关闭（CharsTab 的 ＋ 菜单等）
if (!window._popMenuCloser) {
  window._popMenuCloser = true;
  document.addEventListener("mousedown", e => {
    const m = $("#char-add-menu");
    if (m && !m.hidden && !m.contains(e.target) && !e.target.closest("#char-add")) m.hidden = true;
  });
}

async function route() {
  const h = location.hash || "#/";
  const app = $("#app");
  const mM = /^#\/society\/([\w-]+)$/.exec(h);
  const mC = /^#\/chat\/([\w-]+)\/([\w-]+)$/.exec(h);
  if (mC) return ChatView(mC[1], mC[2]);
  if (mM) return SocietyView(mM[1]);
  if (h === "#/settings") return SettingsView();
  return HomeView();
}

/* ── 首页 ──────────────────────────────────── */
async function HomeView() {
  const app = $("#app");
  app.innerHTML = `<div class="page"><div class="home-wrap">
    <div class="home-head">
      <div class="brandline"><div class="brand-logo">K</div>
        <div><h1>Kith</h1><div class="sub">造一个社会，看它自己活起来</div></div></div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost" id="btn-import">⬓ 导入</button>
        <button class="btn btn-amber" id="btn-sync">⇄ 手机同步</button>
        <button class="btn btn-ghost" onclick="goto('#/settings')">⚙ 设置</button>
      </div></div>
    <div class="home-stats" id="home-stats"></div>
    <div class="soc-grid" id="soc-grid"></div>
    <div class="home-empty" id="home-empty" style="display:none">
      <div class="big">🌐</div>还没有社会。<br>新建一个，或从手机导入一份存档 —— 局域网同步见「设置」。</div>
  </div>
  <button class="fab" id="fab-new">＋ 新建社会</button>
  <input type="file" id="import-file" accept=".json,application/json" style="display:none"></div>`;
  $("#fab-new").onclick = () => CreateWizard();
  $("#btn-sync").onclick = () => SyncModal();
  $("#btn-import").onclick = () => $("#import-file").click();
  $("#import-file").onchange = async e => {
    const f = e.target.files[0]; if (!f) return; e.target.value = "";
    try { const text = await f.text(); const d = await apiPost("/api/import", text); toast(`已导入「${d.society.name}」`); loadHome(); }
    catch (err) { toast(err.message, true); }
  };
  loadHome();
}
async function exportSociety(id) {
  try {
    const resp = await fetch(`/api/societies/${id}/export`); const blob = await resp.blob();
    const cd = resp.headers.get("Content-Disposition") || ""; const m = /filename="(.+)"/.exec(cd);
    const url = URL.createObjectURL(blob); const el = document.createElement("a");
    el.href = url; el.download = m ? m[1] : "society.kith.json"; el.click(); URL.revokeObjectURL(url);
    toast("已导出存档");
  } catch (err) { toast(err.message, true); }
}
async function loadHome() {
  const d = await apiGet("/api/societies").catch(() => ({ societies: [], stats: { societies: 0, characters: 0, relations: 0 } }));
  $("#home-stats").innerHTML = `
    <div class="hstat"><b>${d.stats.societies}</b><span>个社会</span></div>
    <div class="hstat"><b>${d.stats.characters}</b><span>位人物</span></div>
    <div class="hstat"><b>${d.stats.relations}</b><span>条关系</span></div>`;
  $("#home-empty").style.display = d.societies.length ? "none" : "block";
  window._socSummaries = d.societies;
  $("#soc-grid").innerHTML = d.societies.map(s => {
    const h = Math.abs(s.coverSeed || fnv1a(s.id)) % 360, h2 = (h + 70) % 360;
    const coverStyle = s.coverUrl
      ? `background-image:url('${esc(mediaSrc(s.id, 'media/' + s.coverImage))}');background-size:cover;background-position:center`
      : `background:linear-gradient(135deg,hsl(${h},52%,62%),hsl(${h2},48%,38%))`;
    return `<div class="soc-card" data-id="${s.id}">
      <div class="soc-cover" style="${coverStyle}">
        <button class="menu-btn" data-menu="${s.id}">⋮</button></div>
      <div class="soc-info"><div class="n">${esc(s.name)}</div>
        <div class="meta"><span class="chip violet">${esc(s.orientationLabel || "")}</span><span>${s.characterCount} 人 · ${s.relationCount} 关</span><span style="margin-left:auto">${relTime(s.updatedAt)}</span></div></div></div>`;
  }).join("");
  $$("#soc-grid .soc-card").forEach(card => {
    card.addEventListener("click", e => {
      const mid = e.target.dataset.menu;
      if (mid) { e.stopPropagation(); socMenu(e, mid); return; }
      goto("#/society/" + card.dataset.id);
    });
  });
}
function socMenu(e, id) {
  $$(".ctx-menu").forEach(x => x.remove());
  const summary = (window._socSummaries || []).find(x => x.id === id) || {};
  const menu = document.createElement("div"); menu.className = "ctx-menu";
  menu.innerHTML = `<button data-a="open">✦ 打开</button><button data-a="cover">🖼 更换封面</button>` +
    (summary.coverImage ? `<button data-a="cover-rm">🗑 移除封面</button>` : "") +
    `<button data-a="export">⬓ 导出存档</button><button data-a="sync">⇄ 手机同步</button><button class="danger" data-a="del">✕ 删除…</button>`;
  document.body.appendChild(menu);
  menu.style.left = Math.min(e.clientX, innerWidth - 180) + "px"; menu.style.top = e.clientY + 6 + "px";
  menu.addEventListener("click", async ev => {
    const a = ev.target.dataset.a; menu.remove(); if (!a) return;
    if (a === "open") goto("#/society/" + id);
    if (a === "cover") return pickCover(id, () => loadHome());
    if (a === "cover-rm") {
      await apiPut(`/api/societies/${id}/society`, { coverImage: "" });
      toast("已移除封面"); return loadHome();
    }
    if (a === "export") { await exportSociety(id); }
    if (a === "sync") return SyncModal();
    if (a === "del") {
      const name = summary.name || "";
      if (confirm(`删除社会「${name}」？\n\n将同时删除：人物、关系、剧情、全部会话与日志。\n此操作不可恢复，建议先导出备份。`)) {
        await apiDelete(`/api/societies/${id}`); toast("已删除"); loadHome();
      }
    }
  });
  setTimeout(() => document.addEventListener("mousedown", function h(ev) { if (!menu.contains(ev.target)) { menu.remove(); document.removeEventListener("mousedown", h); } }), 0);
}

/* ── 封面与手机同步 ─────────────────────────── */
async function pickCover(sid, onDone) {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.onchange = async () => {
    const f = inp.files[0]; if (!f) return;
    try {
      toast("正在上传封面…");
      const dataBase64 = await fileToB64(f);
      const up = await apiPost("/api/upload-image", { societyId: sid, dataBase64, ext: (f.name.split(".").pop() || "png").toLowerCase() });
      await apiPut(`/api/societies/${sid}/society`, { coverImage: (up.url || "").split("/").pop() });
      toast("封面已更新"); if (onDone) onDone();
    } catch (err) { toast(err.message, true); }
  };
  inp.click();
}

async function SyncModal() {
  const info = await apiGet("/api/sync-info").catch(() => ({ lanUrl: "", ip: "" }));
  const list = await apiGet("/sync/list").catch(() => ({ societies: [] }));
  const mask = openModal(`${modalHead("手机 ⇄ 电脑 数据互通")}<div class="modal-body" id="sync-body"></div>`);
  const body = $("#sync-body", mask);
  body.innerHTML = `
    <div class="field"><label>手机浏览器打开这个地址（需与电脑连同一 Wi-Fi）</label>
      <div style="display:flex;gap:8px">
        <input class="inp" id="sync-url" readonly value="${esc(info.lanUrl || "")}" style="font-weight:700;color:var(--amber-deep)">
        <button class="btn btn-ink" id="sync-copy" style="flex:none">复制</button>
        <button class="btn btn-ghost" id="sync-open" style="flex:none">打开页面</button></div></div>
    <div class="field"><label>从手机导出的存档文件导入电脑</label>
      <button class="btn btn-ghost" id="sync-up">⬓ 选择 .kith.json 文件</button>
      <input type="file" id="sync-file" accept=".json,application/json" style="display:none"></div>
    <div class="field"><label>电脑上的社会（下载存档后可在手机 Kith 首页导入）</label>
      <div id="sync-list"></div></div>
    <div class="muted">双端约定：导入总是生成新副本，不覆盖已有社会；封面会随存档（coverData）一起同步。</div>`;
  $("#sync-copy", body).onclick = async () => {
    try { await navigator.clipboard.writeText(info.lanUrl || ""); toast("已复制"); }
    catch (e) { $("#sync-url", body).select(); document.execCommand("copy"); toast("已复制"); }
  };
  $("#sync-open", body).onclick = () => window.open("/sync", "_blank");
  const upBtn = $("#sync-up", body), upFile = $("#sync-file", body);
  upBtn.onclick = () => upFile.click();
  upFile.onchange = async () => {
    const f = upFile.files[0]; if (!f) return; upFile.value = "";
    try {
      const text = await f.text();
      const r = await fetch("/sync/upload", { method: "POST", headers: { "Content-Type": "application/json" }, body: text });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "导入失败");
      toast(`已导入「${d.name}」`); mask.remove(); loadHome();
    } catch (err) { toast(err.message, true); }
  };
  $("#sync-list", body).innerHTML = list.societies.length ? list.societies.map(s => `
    <div class="set-row" style="border-bottom:1px solid var(--outline-2)">
      <div class="info"><b>${esc(s.name)}</b><span>${s.characterCount} 人 · ${s.relationCount} 关</span></div>
      <button class="btn btn-ghost" data-dl="${s.id}">⬓ 下载</button></div>`).join("")
    : '<div class="empty-note">电脑上还没有社会</div>';
  $$("[data-dl]", body).forEach(b => b.onclick = () => downloadArchive(`/sync/download/${b.dataset.dl}`));
}

async function downloadArchive(url) {
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    const cd = resp.headers.get("Content-Disposition") || "";
    const m = /filename="(.+)"/.exec(cd);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : "society.kith.json";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) { toast(err.message, true); }
}

/* ── 新建向导 ──────────────────────────────── */
function CreateWizard() {
  const T = S.templates;
  let tpl = T.plots[0];
  const miniChars = [];
  const mask = openModal(`${modalHead("新建社会")}<div class="modal-body" id="cw-body"></div>
    <div class="modal-foot"><button class="btn btn-ghost" onclick="this.closest('.modal-mask').remove()">取消</button>
    <button class="btn btn-ink" id="cw-create">✦ 创建社会</button></div>`, { wide: true });
  const body = $("#cw-body", mask);
  function render() {
    body.innerHTML = `
      <div class="field"><label>剧情走向模板</label>
        <div class="tpl-grid">${T.plots.map((p, i) => `<div class="tpl-card ${p === tpl ? "on" : ""}" data-i="${i}"><b>${esc(p.title)}</b><span>${esc(p.subtitle)}</span></div>`).join("")}</div></div>
      <div class="field"><label>社会名称 *</label><input class="inp" id="cw-name" placeholder="比如：城南夜班" maxlength="30"></div>
      <div class="field"><label>世界观描述</label><textarea class="inp" id="cw-world" rows="4" placeholder="这个世界按什么规则运转？">${esc(tpl.worldSetting)}</textarea></div>
      <div class="field"><label>剧情走向</label><textarea class="inp" id="cw-plot" rows="3" placeholder="主线往哪个方向走？">${esc(tpl.plotDirection)}</textarea></div>
      <div class="field"><label>题材标签</label><div class="trope-box" id="cw-tropes">${T.tropes.map(t => `<span class="chip click ${tpl.tropes.includes(t) ? "on" : ""}" data-t="${esc(t)}">${esc(t)}</span>`).join("")}</div></div>
      <div class="field"><label>主要人物（可留空，之后让旁白引入）</label><div id="cw-chars"></div>
        <button class="btn btn-ghost" id="cw-addchar" style="margin-top:4px">＋ 添加一位</button></div>
      <div class="divider"></div>
      <div class="field"><label>模型配置（可创建后再配）</label>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn btn-ghost" id="cw-m-narr">旁白：<span id="cw-narr-label">未指定</span></button>
          <button class="btn btn-ghost" id="cw-m-char">人物默认：<span id="cw-char-label">未指定</span></button>
          <button class="btn btn-ghost" id="cw-m-img">文生图：<span id="cw-img-label">未指定</span></button>
        </div></div>`;
    $$(".tpl-card", body).forEach(c => c.onclick = () => { tpl = T.plots[+c.dataset.i]; render(); });
    $$("#cw-tropes .chip", body).forEach(ch => ch.onclick = () => ch.classList.toggle("on"));
    $("#cw-addchar", body).onclick = () => { miniChars.push({ name: "", gender: "FEMALE", tags: [] }); renderChars(); };
    $("#cw-m-narr", body).onclick = () => ModelPicker(ref => { wizardRefs.narrator = ref; $("#cw-narr-label", body).textContent = ref.label || ref.modelId; });
    $("#cw-m-char", body).onclick = () => ModelPicker(ref => { wizardRefs.character = ref; $("#cw-char-label", body).textContent = ref.label || ref.modelId; });
    $("#cw-m-img", body).onclick = () => ImagePresetPicker(ref => { wizardRefs.image = ref; $("#cw-img-label", body).textContent = ref.name || ref.modelId; });
    renderChars();
  }
  const wizardRefs = { narrator: null, character: null, image: null };
  function renderChars() {
    const box = $("#cw-chars", body); if (!box) return;
    box.innerHTML = miniChars.map((c, i) => `<div class="char-mini">
      <div class="head"><input class="inp" style="flex:1" placeholder="姓名" value="${esc(c.name)}" data-k="name" data-i="${i}">
      <select class="inp" style="width:90px" data-k="gender" data-i="${i}">${GENDERS.map(g => `<option value="${g[0]}" ${g[0] === c.gender ? "selected" : ""}>${g[1]}</option>`).join("")}</select>
      <button class="modal-x" data-del="${i}">✕</button></div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px" data-tags="${i}">
        ${S.templates.tags.map(t => `<span class="chip click ${c.tags.includes(t.label) ? "on" : ""}" data-tag="${esc(t.label)}" data-i="${i}">${esc(t.label)}</span>`).join("")}
      </div>
      <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-size:12.5px;color:var(--text-2)"><span class="switch"><input type="checkbox" data-k="isUser" data-i="${i}" ${c.isUser ? "checked" : ""}><i></i></span>这是我本人扮演的角色</label>
    </div>`).join("") || `<div class="muted" style="padding:4px 2px 8px">暂无初始人物</div>`;
    $$("input[data-k],select[data-k],input[data-k='isUser']", box).forEach(el => el.onchange = () => { miniChars[+el.dataset.i][el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; });
    $$("[data-del]", box).forEach(b => b.onclick = () => { miniChars.splice(+b.dataset.del, 1); renderChars(); });
    $$("[data-tag]", box).forEach(ch => ch.onclick = () => { const c = miniChars[+ch.dataset.i]; const t = ch.dataset.tag; const k = c.tags.indexOf(t); k >= 0 ? c.tags.splice(k, 1) : c.tags.push(t); renderChars(); });
  }
  render();
  $("#cw-create", mask).onclick = async () => {
    const name = $("#cw-name", body).value.trim();
    if (!name) { toast("先给社会起个名字", true); return; }
    const tropes = $$("#cw-tropes .chip.on", body).map(c => c.dataset.t);
    const chars = miniChars.filter(c => c.name.trim()).map(c => ({
      name: c.name.trim(), gender: c.gender, isUser: !!c.isUser,
      tags: c.tags.map(lb => { const t = S.templates.tags.find(x => x.label === lb); return { label: lb, hint: t ? t.hint : "", builtin: !!t }; }),
    }));
    try {
      const d = await apiPost("/api/societies", {
        name, orientation: tpl.orientation, worldSetting: $("#cw-world", body).value,
        plotDirection: $("#cw-plot", body).value, tropes, characters: chars,
        narratorModel: wizardRefs.narrator, defaultCharacterModel: wizardRefs.character, imageModel: wizardRefs.image,
        coverSeed: Math.floor(Math.random() * 360),
      });
      mask.remove(); toast(`社会「${d.society.name}」已建立`);
      goto("#/society/" + d.society.id);
    } catch (e) { toast(e.message, true); }
  };
}

/* ── 模型选择器 ─────────────────────────────── */
function ModelPicker(onPick, preEndpoint) {
  let endpointId = preEndpoint || null;
  const saved = (S.settings.savedModels || []);
  const mask = openModal(`${modalHead("选择模型")}<div class="modal-body" id="mp-body"></div>`, { wide: true });
  const body = $("#mp-body", mask);
  const q = { kw: "", free: false, vision: false, text: false, sort: "PRICE_ASC" };
  const eps = () => (S.settings.endpoints || []).filter(e => (e.kind || "LLM") === "LLM");
  function renderChips() {
    const list = eps();
    if (!list.length) {
      return `<div class="ep-chips"><span class="muted">还没有配置接入点 —— 点下面按钮添加一个厂商 API Key 后即可选择模型</span>
        <button class="btn btn-ink" id="mp-add-ep" style="padding:6px 14px">＋ 添加接入点</button></div>`;
    }
    return `<div class="ep-chips">${list.map(e => {
      const v = vendorOfKey(e.vendor);
      return `<button class="ep-chip ${endpointId === e.id ? "on" : ""}" data-ep="${e.id}"><span class="dot" style="background:${v.color}"></span>${esc(e.label || e.vendor)}</button>`;
    }).join("")}</div>`;
  }
  function vendorOfKey(k) { return S.vendors.find(v => v.key === k) || { color: "#7A8291", monogram: "··", name: k }; }
  async function renderList() {
    $("#mp-list", body).innerHTML = `<div class="empty-note">${SPIN}正在加载模型目录…</div>`;
    const p = new URLSearchParams({ q: q.kw, sort: q.sort, limit: "80" });
    if (endpointId) p.set("vendor", vendorOfEndpoint());
    if (q.free) p.set("free", "1"); if (q.vision) p.set("vision", "1"); if (q.text) p.set("text", "1");
    const d = await apiGet("/api/catalog?" + p.toString()).catch(() => ({ models: [] }));
    if (!$("#mp-list", body)) return;
    $("#mp-list", body).innerHTML = d.models.map(m => `
      <div class="model-row" data-mid="${esc(m.id)}" data-mlabel="${esc(m.name)}" data-mvendor="${esc(m.vendorKey)}">
        ${vendorTile(m.vendor, 34)}
        <div style="min-width:0"><div class="n">${esc(m.name)} ${m.isFree ? '<span class="chip teal">免费</span>' : ""} ${m.supportsVision ? '<span class="chip violet">看图</span>' : ""}</div>
        <div class="d">${esc(m.id)} · ${fmtCtx(m.contextLength)}</div></div>
        <div class="price">${priceStr(m)}</div></div>`).join("") || '<div class="empty-note">没有匹配的模型</div>';
    $$("#mp-list .model-row", body).forEach(row => row.onclick = () => {
      if (!endpointId) { toast("请先在上方选择或添加一个接入点（API Key），否则模型无法调用", true); return; }
      mask.remove();
      onPick({ endpointId, modelId: row.dataset.mid, label: row.dataset.mlabel, vendor: row.dataset.mvendor });
    });
  }
  async function renderKnownModels() {
    const box = $("#mp-known", body), listEl = $("#mp-known-list", body);
    if (!box || !endpointId) { if (box) box.style.display = "none"; return; }
    box.style.display = "block";
    listEl.innerHTML = `<span class="muted">${SPIN}正在拉取接入点模型列表…</span>`;
    try {
      const d = await apiGet(`/api/endpoint-models?endpointId=${encodeURIComponent(endpointId)}`);
      if (!$("#mp-known", body)) return;
      const names = d.models || [];
      if (!names.length) { box.style.display = "none"; return; }
      listEl.innerHTML = names.map(n => `<span class="chip click" data-known="${esc(n)}">${esc(n)}</span>`).join("");
      $$("[data-known]", body).forEach(c => c.onclick = () => {
        mask.remove();
        onPick({ endpointId, modelId: c.dataset.known, label: c.dataset.known, vendor: vendorOfEndpoint() });
      });
    } catch (e) { box.style.display = "none"; }
  }
  function vendorOfEndpoint() { const e = eps().find(x => x.id === endpointId); return e ? e.vendor : ""; }
  function fmtCtx(n) { return n ? (n >= 1000 ? Math.round(n / 1000) + "K 上下文" : n + " 上下文") : "上下文未知"; }
  function priceStr(m) {
    const r = (S.settings.usdToCnyRate) || 7.2;
    if (m.promptPerM == null && m.completionPerM == null) return m.isFree ? "免费" : "价格未知";
    const f = x => x == null ? "?" : "¥" + (x * r).toFixed(x * r < 1 ? 3 : 2);
    return `${f(m.promptPerM)} / ${f(m.completionPerM)}<br><span class="muted">每百万 token</span>`;
  }
  function render() {
    if (!endpointId && eps().length) endpointId = eps()[0].id; // 先选中再渲染，芯片高亮才正确
    body.innerHTML = `<div class="field"><label>已保存的常用配置</label><div class="ep-chips" id="mp-saved"></div></div>
      ${renderChips()}
      <div class="model-toolbar">
        <input class="inp" id="mp-kw" placeholder="搜索模型…" style="flex:1;min-width:130px" value="${esc(q.kw)}">
        <select class="inp" id="mp-sort" style="width:130px">
          <option value="PRICE_ASC">价格从低到高</option><option value="PRICE_DESC">价格从高到低</option>
          <option value="NEWEST">最新发布</option><option value="CONTEXT">上下文长度</option><option value="NAME">名称</option></select>
        <span class="chip click ${q.free ? "on" : ""}" data-f="free">免费</span>
        <span class="chip click ${q.vision ? "on" : ""}" data-f="vision">看图</span>
        <span class="chip click ${q.text ? "on" : ""}" data-f="text">纯文本</span>
      </div><div id="mp-list"><div class="empty-note">${SPIN}正在加载模型目录…</div></div>`;
    $("#mp-saved", body).innerHTML = saved.map((m, i) => {
      const e = (S.settings.endpoints || []).find(x => x.id === m.endpointId);
      if (!e) return "";
      return `<button class="ep-chip" data-sv="${i}"><span class="dot" style="background:${vendorOfKey(m.vendor).color}"></span>${esc(m.label || m.modelId)}</button>`;
    }).join("");
    $$("#mp-saved [data-sv]", body).forEach(b => b.onclick = () => { mask.remove(); onPick(saved[+b.dataset.sv]); });
    $$("[data-ep]", body).forEach(c => c.onclick = () => { endpointId = c.dataset.ep; render(); });
    const addEp = $("#mp-add-ep", body);
    if (addEp) addEp.onclick = () => EndpointEditor(null, async () => {
      S.settings = await apiGet("/api/settings"); window._settings = S.settings;
      endpointId = null; render(); toast("接入点已保存，继续选择模型");
    });
    $$("[data-f]", body).forEach(c => c.onclick = () => { q[c.dataset.f] = !q[c.dataset.f]; render(); });
    $("#mp-sort", body).onchange = e => { q.sort = e.target.value; renderList(); };
    $("#mp-kw", body).oninput = debounce(e => { q.kw = e.target.value; renderList(); }, 300);
    renderList();
    renderKnownModels();
  }
  render();
}

function ImagePresetPicker(onPick) {
  const mask = openModal(`${modalHead("选择生图模型")}<div class="modal-body"><div id="ip-list"><div class="empty-note">${SPIN}正在加载生图模型…</div></div></div>`, { wide: true });
  apiGet("/api/image-presets").then(d => {
    const box = $("#ip-list", mask); if (!box) return;
    box.innerHTML = d.presets.map(p => {
      const v = S.vendors.find(v => v.key === p.vendorKey) || { color: "#888", monogram: "··" };
      return `<div class="model-row" data-mid="${esc(p.modelId)}" data-name="${esc(p.name)}" data-vendor="${esc(p.vendorKey)}" data-baseurl="${esc(p.baseUrl || "")}">
        ${vendorTile(v, 34)}<div><div class="n">${esc(p.name)} ${p.free ? '<span class="chip teal">免费</span>' : ""}</div><div class="d">${esc(p.modelId)} · ${esc(p.note || p.priceHint)}</div></div>
        <div class="price">${esc(p.priceHint)}</div></div>`;
    }).join("");
    $$("#ip-list .model-row", mask).forEach(row => row.onclick = () => { mask.remove(); onPick({ modelId: row.dataset.mid, label: row.dataset.name, vendor: row.dataset.vendor, baseUrl: row.dataset.baseurl }); });
  }).catch(e => { const box = $("#ip-list", mask); if (box) box.innerHTML = `<div class="empty-note">加载失败：${esc(e.message)}</div>`; });
}

/* ── 社会主界面 ─────────────────────────────── */
/* ── 社会页头部统计与图例 ───────────────────── */
function renderTopStats(b) {
  const st = b.stats || {};
  const tok = (st.tokensIn || 0) + (st.tokensOut || 0);
  $("#top-stats").innerHTML =
    `<span><b>${b.characters.length}</b> 人</span><span><b>${b.relations.length}</b> 关系</span>` +
    (st.totalCostUsd ? `<span>花费 <b>${fmtCny(st.totalCostUsd)}</b></span>` : "") +
    (tok ? `<span>${fmtTok(tok)} tok</span>` : "") +
    `<span>第 <b>${b.plot.act || 1}</b> 章 · ${esc(b.plot.title || "序章")}</span>` +
    (st.isolatedCount ? `<span><b>${st.isolatedCount}</b> 人未连线</span>` : "");
}
// 图例只列这张图里真实出现过的关系类型，空类型不占位置（与安卓端一致）
function updateLegend() {
  const el = $("#legend"); if (!el || !S.bundle) return;
  const kinds = [...new Set(S.bundle.relations.map(r => r.kind))].filter(k => KIND_COLOR[k]);
  const labelOf = k => (RELATION_KINDS.find(x => x[0] === k) || [k, k])[1];
  el.innerHTML = `<div style="font-weight:700;margin-bottom:2px">▪ 图例</div>` +
    (kinds.length ? kinds.map(k => `<div class="row"><span class="swatch" style="background:${KIND_COLOR[k]}"></span>${esc(labelOf(k))}</div>`).join("")
      : '<div class="row muted">还没有连线</div>');
}

async function SocietyView(sid) {
  const app = $("#app");
  app.innerHTML = `<div style="height:100vh;display:flex;align-items:center;justify-content:center;color:var(--text-3)">' + SPIN + '加载中…</div>`;
  let bundle;
  try { bundle = await apiGet(`/api/societies/${sid}`); } catch (e) { app.innerHTML = `<div style="padding:60px;text-align:center;color:var(--text-2)">${esc(e.message)}</div>`; return; }
  S.bundle = bundle;
  S.graphView = { layout: S.settings.graphLayout || "TREE", positions: bundle.positions || {}, scale: 1, tx: 0, ty: 0, drag: null, hover: null };
  const soc = bundle.society;
  const totalCost = 0; // 会话花费在聊天里累计，这里显示剧情花费可扩展
  app.innerHTML = `
    <div class="topbar">
      <button class="back" onclick="goto('#/')">←</button>
      <h2>${esc(soc.name)} <span class="chip violet">${esc(soc.orientationLabel)}</span></h2>
      <div class="top-stats" id="top-stats"></div>
      <div class="top-actions">
        <button class="icon-btn" id="tb-god" title="上帝视角：NPC 对话">⊕</button>
        <button class="icon-btn" id="tb-cover" title="更换封面">🖼</button>
        <button class="icon-btn" id="tb-model" title="社会模型配置">◈</button>
        <button class="icon-btn" id="tb-export" title="导出存档">⬓</button>
      </div></div>
    <div class="society-layout">
      <div class="graph-pane">
        <canvas id="graph-canvas"></canvas>
        <div class="iso-empty" id="iso-empty" hidden></div>
        <div class="iso-wrap" id="iso-wrap"></div>
        <div class="graph-toolbar">
          <div class="seg"><button id="lay-tree">树状图</button><button id="lay-chain">链式图</button></div>
          <div class="legend" id="legend"></div>
        </div>
        <div class="graph-hint">滚轮缩放 · 拖拽平移 · 拖动头像固定位置 · 点击看详情 · 双击已钉入的头像放回网格</div>
      </div>
      <div class="soc-side">
        <div class="side-tabs">
          <button data-tab="narrator" class="on">旁白</button>
          <button data-tab="chars">人物</button>
          <button data-tab="logs">日志</button>
        </div>
        <div class="side-body" id="side-body"></div>
      </div></div>`;
  renderTopStats(bundle);
  $("#lay-tree").classList.toggle("on", S.graphView.layout === "TREE");
  $("#lay-chain").classList.toggle("on", S.graphView.layout === "CHAIN");
  updateLegend();
  $$(".side-tabs button").forEach(b => b.onclick = () => {
    $$(".side-tabs button").forEach(x => x.classList.remove("on")); b.classList.add("on");
    renderSideTab(b.dataset.tab);
  });
  $("#lay-tree").onclick = () => setLayout("TREE");
  $("#lay-chain").onclick = () => setLayout("CHAIN");
  $("#tb-export").onclick = () => exportSociety(sid);
  $("#tb-cover").onclick = () => pickCover(sid, async () => { toast("封面已更新"); await reloadBundle(); });
  $("#tb-model").onclick = () => SocietyModelsModal();
  $("#tb-god").onclick = () => { if (S.settings.godViewEnabled) GodViewModal(); else toast("上帝视角已在设置中关闭"); };
  GraphInit();
  renderIsoGrid();
  renderSideTab("narrator");

  function setLayout(l) {
    S.graphView.layout = l;
    $("#lay-tree").classList.toggle("on", l === "TREE"); $("#lay-chain").classList.toggle("on", l === "CHAIN");
    GraphDraw();
  }
  function renderSideTab(tab) {
    const el = $("#side-body");
    if (tab === "narrator") return NarratorTab(el);
    if (tab === "chars") return CharsTab(el);
    if (tab === "logs") return LogsTab(el);
    if (tab === "detail") return CharDetailTab(el, S.graphView.detailId);
  }
  window._renderSideTab = renderSideTab;
}
async function reloadBundle() {
  const d = await apiGet(`/api/societies/${S.bundle.society.id}`);
  S.bundle = d; S.graphView.positions = d.positions || {};
  renderTopStats(d); updateLegend();
  GraphDraw(); renderIsoGrid();
}

/* ── 旁白面板 ──────────────────────────────── */
function NarratorTab(el) {
  const b = S.bundle, plot = b.plot;
  el.innerHTML = `
    <div class="plot-card">
      <div class="act">第 ${plot.act || 1} 章</div><h4>${esc(plot.title || "序章")}</h4>
      ${plot.summary ? `<p>${esc(plot.summary)}</p>` : '<p class="muted">剧情还没有展开 —— 点击下方按钮，让旁白推进一步。</p>'}
      ${plot.mood ? `<div class="mood"><span class="chip violet">氛围 · ${esc(plot.mood)}</span></div>` : ""}
      ${plot.hooks && plot.hooks.length ? `<ul class="hook-list">${plot.hooks.map(h => `<li>伏笔：${esc(h)}</li>`).join("")}</ul>` : ""}
      ${plot.beats && plot.beats.length ? `<div class="beat-list">${plot.beats.slice(-6).reverse().map(bt => `<div class="beat"><span class="dot"></span><div><b style="color:var(--text)">${esc(bt.title)}</b>${bt.detail ? `<br>${esc(bt.detail)}` : ""}</div></div>`).join("")}</div>` : ""}
    </div>
    <div id="narr-out"></div>
    <div class="field" style="margin-top:6px"><label>给旁白的指示（可空）</label>
      <textarea class="inp" id="narr-hint" rows="2" placeholder="比如：让周野和林晓在冷柜前再碰一次面"></textarea></div>
    <label style="display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:13px;color:var(--text-2)">
      <span class="switch"><input type="checkbox" id="narr-newnpc"><i></i></span>顺带引入新人物（最多 2 个）</label>
    <button class="btn btn-ink" id="narr-go" style="width:100%;justify-content:center;font-size:14.5px">✦ 让旁白推进一段</button>`;
  $("#narr-go", el).onclick = async () => {
    const btn = $("#narr-go", el); btn.disabled = true; btn.innerHTML = '<span class="spin"></span> 旁白正在书写…';
    const out = $("#narr-out", el); out.innerHTML = "";
    try {
      await ssePost(`/api/societies/${b.society.id}/narrate`, {
        userHint: $("#narr-hint", el).value, needNewNpc: $("#narr-newnpc", el).checked,
      }, ev => {
        if (ev.type === "started") { out.innerHTML = `<div class="narr-bubble"><div class="who">旁白</div><span class="typing-dots"><span></span><span></span><span></span></span></div>`; }
        if (ev.type === "done") {
          const o = ev.outcome;
          if (!o.ok) { out.innerHTML = ""; toast(o.error, true); }
          else {
            out.innerHTML = `<div class="narr-bubble"><div class="who">旁白</div>${esc(o.narrative)}</div>` +
              (o.newCharacters || []).map(c => `<div class="narr-newchar"><b>新人物 · ${esc(c.name)}</b>（${IMPORTANCE[c.importance].label}）<br>${esc(c.oneLiner || c.personality || "")}</div>`).join("");
            if (o.guardNotice) toast(o.guardNotice, true);
          }
        }
      });
      await reloadBundle();
      // 不重渲染旁白 Tab：保留刚生成的旁白文本与新人物提示
    } catch (e) { toast(e.message, true); out.innerHTML = ""; }
    btn.disabled = false; btn.textContent = "✦ 让旁白推进一段";
  };
}

/* ── 人物列表 Tab ──────────────────────────── */
function CharsTab(el) {
  const b = S.bundle;
  el.innerHTML = `
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <input class="inp" id="char-search" placeholder="搜索人物…">
      <div style="position:relative;flex:none">
        <button class="btn btn-ink" id="char-add" style="padding:8px 14px">＋</button>
        <div class="pop-menu" id="char-add-menu" hidden>
          <button data-a="new">✎ 新建人物</button>
          <button data-a="import">⬒ 从文件导入人物…</button>
        </div></div></div>
    <input type="file" id="char-import-file" accept=".json,application/json" hidden>
    <div id="char-list"></div>`;
  const render = () => {
    const kw = ($("#char-search", el).value || "").trim().toLowerCase();
    const list = b.characters.filter(c => !kw || c.name.toLowerCase().includes(kw) || (c.alias || "").toLowerCase().includes(kw));
    $("#char-list", el).innerHTML = list.map(c => `<div class="char-row" data-id="${c.id}">
      ${avatarHtml(c, 38, true)}
      <div style="min-width:0;flex:1"><div class="n">${esc(c.name)}${c.alias ? ` <span class="muted">(${esc(c.alias)})</span>` : ""}${c.isUser ? ' <span class="chip amber">你</span>' : ""}</div>
      <div class="d">${esc(c.oneLiner || c.personality || "暂无简介")}</div></div>
      <span class="chip imp" style="background:${IMPORTANCE[c.importance].color}22;color:${IMPORTANCE[c.importance].color}">${IMPORTANCE[c.importance].label}</span></div>`).join("");
    $$("#char-list .char-row", el).forEach(r => r.onclick = () => { $$(".side-tabs button")[1].click(); S.graphView.detailId = r.dataset.id; window._renderSideTab("detail"); });
  };
  $("#char-search", el).oninput = debounce(render, 200);
  // ＋ 菜单：新建 / 从文件导入（Kith 自家格式或喵咚角色卡，服务端按名字去重）
  const addBtn = $("#char-add", el), addMenu = $("#char-add-menu", el);
  addBtn.onclick = () => { addMenu.hidden = !addMenu.hidden; };
  $$("#char-add-menu button", el).forEach(btn => btn.onclick = () => {
    addMenu.hidden = true;
    if (btn.dataset.a === "new") return CharacterEditor(null);
    $("#char-import-file", el).click();
  });
  $("#char-import-file", el).onchange = async e => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    addBtn.disabled = true; addBtn.innerHTML = '<span class="spin"></span>';
    try {
      const d = await apiPost(`/api/societies/${b.society.id}/import-characters`, { raw: await f.text() });
      toast(d.message || `已导入 ${d.added} 位人物`);
      await reloadBundle(); GraphCenter(); window._renderSideTab("chars");
    } catch (err) { toast(err.message, true); }
    addBtn.disabled = false; addBtn.textContent = "＋";
  };
  render();
}

function CharDetailTab(el, cid) {
  const b = S.bundle;
  const c = b.characters.find(x => x.id === cid);
  if (!c) { el.innerHTML = '<div class="empty-note">人物不存在</div>'; return; }
  const rels = b.relations.filter(r => r.fromId === c.id || r.toId === c.id);
  const canChat = IMPORTANCE[c.importance].chat;
  el.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;text-align:center;padding:8px 0 16px">
      ${avatarHtml(c, 76, true)}
      <div style="font-size:18px;font-weight:700;margin-top:10px">${esc(c.name)}${c.alias ? ` <span class="muted">${esc(c.alias)}</span>` : ""}</div>
      <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;justify-content:center">
        <span class="chip" style="background:${IMPORTANCE[c.importance].color}22;color:${IMPORTANCE[c.importance].color}">${IMPORTANCE[c.importance].label}</span>
        ${c.isUser ? '<span class="chip amber">你本人</span>' : ""}${c.tags.map(t => `<span class="chip violet">${esc(t.label)}</span>`).join("")}
      </div>
      ${c.oneLiner ? `<div style="margin-top:10px;font-size:13.5px;color:var(--text-2)">${esc(c.oneLiner)}</div>` : ""}
      <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;justify-content:center">
        ${canChat ? `<button class="btn btn-ink" id="cd-chat">✉ 发消息</button>` : `<span class="muted" style="align-self:center">背景人物 · 不参与对话</span>`}
        <button class="btn btn-ghost" id="cd-edit">编辑</button>
        <button class="btn btn-danger" id="cd-del">删除</button>
      </div></div>
    <div class="divider"></div>
    ${c.personality ? sec("性格", c.personality) : ""}${c.background ? sec("背景经历", c.background) : ""}
    ${c.appearance ? sec("外貌", c.appearance) : ""}${c.speechStyle ? sec("说话风格", c.speechStyle) : ""}
    ${c.model ? sec("使用模型", esc(c.model.label || c.model.modelId)) : ""}
    <div class="field"><label>人际关系（${rels.length}）</label>
      ${rels.map(r => { const oid = r.fromId === c.id ? r.toId : r.fromId; const o = b.characters.find(x => x.id === oid); if (!o) return ""; return `<div class="char-row" data-oid="${oid}" style="padding:7px 6px">${avatarHtml(o, 30)}<div style="flex:1;min-width:0"><div class="n" style="font-size:13px">${esc(o.name)}</div></div><span class="chip">${esc(r.customLabel || r.kindLabel || "")} · ${r.intensity}</span></div>`; }).join("") || '<div class="muted">还没有任何连线</div>'}</div>`;
  function sec(t, v) { return `<div class="field"><label>${t}</label><div style="font-size:13px;white-space:pre-wrap;color:var(--text-2)">${esc(v)}</div></div>`; }
  const chatBtn = $("#cd-chat", el); if (chatBtn) chatBtn.onclick = () => goto(`#/chat/${b.society.id}/${c.id}`);
  $("#cd-edit", el).onclick = () => CharacterEditor(c);
  $("#cd-del", el).onclick = async () => {
    if (!confirm(`删除人物「${c.name}」？\n\nTA 的会话记录与所有关系连线将一并删除。`)) return;
    await apiDelete(`/api/societies/${b.society.id}/characters/${c.id}`);
    toast("已删除"); await reloadBundle(); window._renderSideTab("chars");
  };
  $$(".char-row[data-oid]", el).forEach(r => r.onclick = () => { S.graphView.detailId = r.dataset.oid; GraphCenterOn(r.dataset.oid); window._renderSideTab("detail"); });
}

/* ── 日志 Tab ──────────────────────────────── */
async function LogsTab(el) {
  el.innerHTML = '<div class="empty-note">加载日志…</div>';
  const d = await apiGet(`/api/societies/${S.bundle.society.id}/logs?limit=300`);
  const colors = { NARRATOR: "#6B5BD2", CHARACTER: "#1F8A80", USER: "#C9820F", VISION: "#4A86C8", IMAGE: "#D25570", MODEL: "#7A8291", SYSTEM: "#8A92A3" };
  const names = { NARRATOR: "旁白", CHARACTER: "角色", USER: "用户", VISION: "视觉", IMAGE: "生图", MODEL: "模型", SYSTEM: "系统" };
  el.innerHTML = d.logs.length ? d.logs.map(g => `<div class="log-item">
    <div class="head"><span class="chip" style="background:${colors[g.kind]}22;color:${colors[g.kind]}">${names[g.kind] || g.kind}</span>
    <span>${esc(g.actor)}</span>·<span>${esc(g.title)}</span><span class="time">${relTime(g.ts)}</span></div>
    ${g.detail ? `<div class="detail" data-full="${esc(g.detail)}">${esc(g.detail.length > 160 ? g.detail.slice(0, 160) + "…" : g.detail)}</div>${g.detail.length > 160 ? '<span class="more">展开全部</span>' : ""}` : ""}
    ${g.modelLabel || g.tokensOut ? `<div class="muted" style="margin-top:4px">${esc(g.modelLabel || "")} ${g.tokensOut ? `· ${fmtTok(g.tokensIn || 0)}→${fmtTok(g.tokensOut)} tok` : ""} ${g.costUsd ? `· ${fmtCny(g.costUsd)}` : ""}</div>` : ""}
  </div>`).join("") : '<div class="empty-note">还没有日志。旁白推进与角色对话都会留痕在这里。</div>';
  $$(".log-item .more", el).forEach(m => m.onclick = () => { const dt = m.previousElementSibling; dt.classList.add("expanded"); dt.textContent = dt.dataset.full; m.remove(); });
}

/* ── 关系图（Canvas）────────────────────────── */
function GraphInit() {
  const canvas = $("#graph-canvas");
  const gv = S.graphView;
  const dpr = window.devicePixelRatio || 1;
  function resize() {
    const r = canvas.parentElement.getBoundingClientRect();
    canvas.width = r.width * dpr; canvas.height = r.height * dpr;
    GraphDraw();
  }
  window.addEventListener("resize", resize);
  resize();
  GraphCenter();

  const rectOf = () => canvas.getBoundingClientRect();
  const toWorld = (cx, cy) => { const r = rectOf(); return { x: (cx - r.left - gv.tx) / gv.scale, y: (cy - r.top - gv.ty) / gv.scale }; };

  canvas.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    const pt = toWorld(e.clientX, e.clientY);
    const node = hitNode(pt);
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { }
    if (node) {
      // 拖动位移必须落进 gv.positions —— graphCompute 每帧都以它为准，
      // 只改节点对象会被下一次重绘覆盖（这正是当初拖不动的根因）
      gv.drag = { id: node.id, ox: pt.x - node.x, oy: pt.y - node.y, moved: false };
      canvas.style.cursor = "grabbing";
    } else {
      gv.drag = { pan: true, sx: e.clientX, sy: e.clientY, tx: gv.tx, ty: gv.ty };
      canvas.classList.add("dragging");
    }
  });

  canvas.addEventListener("pointermove", e => {
    if (!gv.drag) {
      const pt = toWorld(e.clientX, e.clientY);
      canvas.style.cursor = hitNode(pt) ? "grab" : "default";
      return;
    }
    if (gv.drag.pan) {
      gv.tx = gv.drag.tx + (e.clientX - gv.drag.sx);
      gv.ty = gv.drag.ty + (e.clientY - gv.drag.sy);
      GraphDraw();
      return;
    }
    const pt = toWorld(e.clientX, e.clientY);
    const nx = pt.x - gv.drag.ox, ny = pt.y - gv.drag.oy;
    gv.positions[gv.drag.id] = [nx, ny];
    const n = (gv._nodes || []).find(x => x.id === gv.drag.id);
    if (n) { n.x = nx; n.y = ny; }
    gv.drag.moved = true;
    GraphDraw();
  });

  function finish(e, cancelled) {
    if (!gv.drag) return;
    const d = gv.drag; gv.drag = null;
    canvas.classList.remove("dragging");
    canvas.style.cursor = "default";
    try { if (e.pointerId !== undefined) canvas.releasePointerCapture(e.pointerId); } catch (err) { }
    if (d.pan || !d.id) return;
    if (d.moved && !cancelled) {
      apiPut(`/api/societies/${S.bundle.society.id}/layout`, { positions: gv.positions }).catch(() => { });
    } else if (!d.moved && !cancelled) {
      openNode(d.id);
    }
  }
  canvas.addEventListener("pointerup", e => finish(e, false));
  canvas.addEventListener("pointercancel", e => finish(e, true));

  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const r = rectOf();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const old = gv.scale;
    const k = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    gv.scale = Math.min(2.6, Math.max(0.35, gv.scale * k));
    gv.tx = mx - (mx - gv.tx) * (gv.scale / old);
    gv.ty = my - (my - gv.ty) * (gv.scale / old);
    GraphDraw();
  }, { passive: false });
  canvas.addEventListener("dblclick", e => {
    // 双击「已钉进画布的未连线人物」放回下方网格；双击空白处仍是重置视图
    const pt = toWorld(e.clientX, e.clientY);
    const n = hitNode(pt);
    if (n && (gv._isolated || []).some(c => c.id === n.id) && !((adjOf(n.id) || []).length)) {
      delete gv.positions[n.id];
      apiPut(`/api/societies/${S.bundle.society.id}/layout`, { positions: gv.positions }).catch(() => { });
      renderIsoGrid(); GraphDraw();
      toast("已放回未连线网格");
      return;
    }
    gv.scale = 1; GraphCenter(); GraphDraw();
  });
}
function adjOf(id) {
  const out = [];
  if (!S.bundle) return out;
  for (const r of S.bundle.relations) {
    if (r.fromId === id) out.push(r.toId);
    else if (r.toId === id) out.push(r.fromId);
  }
  return out;
}
/* ── 未连线人物网格 ────────────────────────── */
// 这些人和社会里谁都没有关系，画进图里只会是一盘散沙（与安卓端 RelationGraph
// 同约定）：以紧凑头像网格列在图下方，点按同样能看资料、发消息；按住头像拖到
// 上方画布里松手，即可把 TA 钉进画布（双击画布里的这类头像可放回网格）。
function renderIsoGrid() {
  const wrap = $("#iso-wrap"), empty = $("#iso-empty");
  if (!wrap || !S.bundle) return;
  const gv = S.graphView;
  const iso = S.bundle.characters.filter(c => !(adjOf(c.id) || []).length && !gv.positions[c.id]);
  const linkedCount = S.bundle.characters.length - S.bundle.characters.filter(c => !(adjOf(c.id) || []).length).length;
  const placedCount = Object.keys(gv.positions).filter(id => (S.bundle.characters.some(c => c.id === id)) && !(adjOf(id) || []).length).length;
  wrap.innerHTML = iso.length
    ? `<div class="iso-title">未连线人物 · ${iso.length}<span class="muted">（按住头像拖到图上可固定位置）</span></div>
       <div class="iso-grid">${iso.map(c => `<div class="iso-chip" data-id="${c.id}">${avatarHtml(c, 34, true)}<span>${esc(c.name)}</span></div>`).join("")}</div>`
    : "";
  if (empty) {
    empty.hidden = !(!linkedCount && !placedCount && S.bundle.characters.length);
    empty.textContent = S.bundle.characters.length
      ? "还没有连线的人物 —— 下方网格里的人物可以拖进画布"
      : "";
  }
  $$(".iso-chip", wrap).forEach(chip => {
    const cid = chip.dataset.id;
    chip.addEventListener("pointerdown", e => {
      if (e.button !== 0) return;
      e.preventDefault();
      try { chip.setPointerCapture(e.pointerId); } catch (err) { }
      const start = { x: e.clientX, y: e.clientY };
      let ghost = null, moved = false;
      const onMove = ev => {
        if (!moved && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return;
        moved = true;
        if (!ghost) {
          const c = S.bundle.characters.find(x => x.id === cid);
          ghost = document.createElement("div");
          ghost.className = "iso-ghost";
          ghost.innerHTML = avatarHtml(c, 44, true);
          document.body.appendChild(ghost);
          chip.classList.add("dragging");
        }
        ghost.style.left = ev.clientX + "px";
        ghost.style.top = ev.clientY + "px";
      };
      const onUp = ev => {
        chip.removeEventListener("pointermove", onMove);
        chip.removeEventListener("pointerup", onUp);
        chip.removeEventListener("pointercancel", onUp);
        if (ghost) ghost.remove();
        chip.classList.remove("dragging");
        const canvas = $("#graph-canvas");
        if (moved && canvas) {
          const r = canvas.getBoundingClientRect();
          if (ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom) {
            const g = S.graphView;
            // 落点（屏幕 px）→ 画布内容坐标（世界系，扣掉平移与缩放）
            g.positions[cid] = [(ev.clientX - r.left - g.tx) / g.scale, (ev.clientY - r.top - g.ty) / g.scale];
            apiPut(`/api/societies/${S.bundle.society.id}/layout`, { positions: g.positions }).catch(() => { });
            renderIsoGrid(); GraphDraw();
          }
          return;
        }
        if (!moved) openNode(cid); // 纯点击看详情
      };
      chip.addEventListener("pointermove", onMove);
      chip.addEventListener("pointerup", onUp);
      chip.addEventListener("pointercancel", onUp);
    });
  });
}
function graphCompute() {
  const b = S.bundle, gv = S.graphView;
  const adj = {}; b.relations.forEach(r => { (adj[r.fromId] = adj[r.fromId] || []).push(r.toId); (adj[r.toId] = adj[r.toId] || []).push(r.fromId); });
  // 与安卓端 RelationGraphLayout 同构：没连线的人物不进画布（在图下方网格列出，
  // 拖进画布后作为自由节点渲染）。导入大量无关系人物时树状/链式不再被撑爆。
  const linked = b.characters.filter(c => (adj[c.id] || []).length);
  const isolated = b.characters.filter(c => !(adj[c.id] || []).length);
  const nodes = linked.map(c => ({ id: c.id, c, x: 0, y: 0 }));
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const root = linked.find(c => c.isUser) ||
    linked.reduce((best, c) => (!best || (adj[c.id] || []).length > (adj[best.id] || []).length ? c : best), null);
  const order = []; const layer = {};
  if (root) {
    const seen = new Set([root.id]); const q = [root.id]; layer[root.id] = 0;
    while (q.length) { const id = q.shift(); order.push(id); for (const nb of (adj[id] || [])) if (!seen.has(nb)) { seen.add(nb); layer[nb] = layer[id] + 1; q.push(nb); } }
    // 连通但 BFS 没到的（别的连通分量，比如「A ↔ B」这种不经过用户的关系对）
    // 当作最外层，保留在画布里不丢弃
    const maxDepth = Math.max(0, ...Object.values(layer));
    nodes.forEach(n => { if (!(n.id in layer)) { order.push(n.id); layer[n.id] = maxDepth + 1; } });
  } else { nodes.forEach(n => order.push(n.id)); }
  const W = 900;
  if (gv.layout === "TREE") {
    const groups = {};
    order.forEach(id => { (groups[layer[id]] = groups[layer[id]] || []).push(id); });
    const keys = Object.keys(groups).map(Number).sort((a, b) => a - b);
    keys.forEach((k, ki) => {
      const arr = groups[k];
      arr.forEach((id, i) => {
        const n = byId[id];
        n.x = (i - (arr.length - 1) / 2) * 150 + W / 2 + ((fnv1a(id) % 40) - 20);
        n.y = ki * 165 + 110;
      });
    });
  } else {
    const midY = 420;
    order.forEach((id, i) => { const n = byId[id]; n.x = 160 + i * 128; n.y = midY + Math.sin(i * 0.85) * 150; });
  }
  // 用户拖过的位置优先
  Object.entries(gv.positions).forEach(([id, xy]) => { if (byId[id]) { byId[id].x = xy[0]; byId[id].y = xy[1]; } });
  // 已钉进画布的未连线人物：布局计算不给坐标，位置完全由 positions 决定，
  // 拖拽/选中行为与普通节点一致
  isolated.forEach(c => {
    const p = gv.positions[c.id];
    if (p) { const n = { id: c.id, c, x: p[0], y: p[1] }; nodes.push(n); byId[c.id] = n; }
  });
  gv._isolated = isolated;
  return { nodes, byId };
}
function nodeRadius(c) { return { LEAD: 34, MAJOR: 30, SUPPORTING: 26, MINOR: 23, EXTRA: 20 }[c.importance] || 26; }
function GraphDraw() {
  const canvas = $("#graph-canvas"); if (!canvas || !S.bundle) return;
  const ctx = canvas.getContext("2d");
  const gv = S.graphView, dpr = window.devicePixelRatio || 1;
  const W = canvas.width / dpr, H = canvas.height / dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const { nodes, byId } = graphCompute();
  ctx.save();
  ctx.translate(gv.tx, gv.ty); ctx.scale(gv.scale, gv.scale);
  const dark = document.documentElement.dataset.theme === "dark";
  // 边
  for (const r of S.bundle.relations) {
    const a = byId[r.fromId], bb = byId[r.toId]; if (!a || !bb) continue;
    const cp = edgeCtrl(a, bb, r.kind); if (!cp) continue;
    const w = 1.2 + (r.intensity / 100) * 3;
    const col = KIND_COLOR[r.kind] || (dark ? "#454D5C" : "#A9B1C0");
    const ra = nodeRadius(a.c), rb = nodeRadius(bb.c);
    const t1 = edgePoint(a, cp, ra), t2 = edgePoint(bb, cp, rb);
    ctx.beginPath(); ctx.moveTo(t1.x, t1.y); ctx.quadraticCurveTo(cp.cx, cp.cy, t2.x, t2.y);
    ctx.strokeStyle = col; ctx.globalAlpha = dark ? 0.8 : 0.65; ctx.lineWidth = w; ctx.stroke(); ctx.globalAlpha = 1;
  }
  // 选中节点的连线标注：平时满屏都是字会淹掉图，只在选中某人（详情打开）时，
  // 才把 TA 的每条连线在曲线中点标上关系名（与安卓端 RelationGraph 一致）
  if (gv.detailId && byId[gv.detailId]) {
    ctx.font = `700 10px "PingFang SC","Microsoft YaHei",sans-serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    for (const r of S.bundle.relations) {
      if (r.fromId !== gv.detailId && r.toId !== gv.detailId) continue;
      const a = byId[r.fromId], bb = byId[r.toId]; if (!a || !bb) continue;
      const cp = edgeCtrl(a, bb, r.kind); if (!cp) continue;
      // 二次贝塞尔在 t=0.5 处的点 = (P0 + 2P1 + P2) / 4
      const mx = (a.x + 2 * cp.cx + bb.x) / 4, my = (a.y + 2 * cp.cy + bb.y) / 4;
      const label = r.customLabel || r.kindLabel || "";
      if (!label) continue;
      const tw = ctx.measureText(label).width;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(mx - tw / 2 - 7, my - 9, tw + 14, 18, 9);
      else ctx.rect(mx - tw / 2 - 7, my - 9, tw + 14, 18);
      ctx.fillStyle = dark ? "rgba(16,18,24,.88)" : "rgba(16,18,24,.88)";
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.fillText(label, mx, my + 0.5);
    }
  }
  // 节点
  for (const n of nodes) {
    const rad = nodeRadius(n.c);
    const [c1, c2] = avatarColor(n.c.name);
    const imp = IMPORTANCE[n.c.importance];
    if (n.c.isUser || n.c.importance === "LEAD") {
      ctx.beginPath(); ctx.arc(n.x, n.y, rad + 3.5, 0, 7); ctx.strokeStyle = "#F5B544"; ctx.lineWidth = 2.5; ctx.stroke();
    }
    const grad = ctx.createLinearGradient(n.x - rad, n.y - rad, n.x + rad, n.y + rad);
    grad.addColorStop(0, c1); grad.addColorStop(1, c2);
    ctx.beginPath(); ctx.arc(n.x, n.y, rad, 0, 7); ctx.fillStyle = grad; ctx.fill();
    ctx.font = `700 ${Math.round(rad * 0.82)}px "PingFang SC","Microsoft YaHei",sans-serif`;
    ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(initials(n.c.name), n.x, n.y + 1);
    ctx.font = `500 11.5px "PingFang SC","Microsoft YaHei",sans-serif`;
    ctx.fillStyle = dark ? "#9BA3B4" : "#5A6070";
    ctx.fillText(n.c.name, n.x, n.y + rad + 14);
  }
  ctx.restore();
  gv._nodes = nodes;
}
function edgePoint(from, to, r) {
  const dx = to.x - from.x, dy = to.y - from.y; const d = Math.hypot(dx, dy) || 1;
  return { x: from.x + dx / d * r, y: from.y + dy / d * r };
}
function edgeCtrl(a, bb, kind) {
  const dist = Math.hypot(bb.x - a.x, bb.y - a.y);
  if (dist < 1) return null;
  const curv = (kind === "SUPERIOR" || kind === "SUBORDINATE" || kind === "MENTOR" || kind === "STUDENT") ? 0.12 : 0.2;
  const mx = (a.x + bb.x) / 2, my = (a.y + bb.y) / 2;
  const nx = -(bb.y - a.y) / dist, ny = (bb.x - a.x) / dist;
  return { cx: mx + nx * dist * curv, cy: my + ny * dist * curv };
}
function screenToWorld(sx, sy) { const gv = S.graphView; return { x: (sx - gv.tx) / gv.scale, y: (sy - gv.ty) / gv.scale }; }
function hitNode(pt) { const gv = S.graphView; const ns = gv._nodes || []; for (let i = ns.length - 1; i >= 0; i--) { const n = ns[i]; if (Math.hypot(pt.x - n.x, pt.y - n.y) <= nodeRadius(n.c) + 4 / gv.scale) return n; } return null; }
function GraphCenterOn(id) { const n = (S.graphView._nodes || []).find(x => x.id === id); if (!n) return; const gv = S.graphView; const canvas = $("#graph-canvas"); gv.tx = canvas.clientWidth / 2 - n.x * gv.scale; gv.ty = canvas.clientHeight / 2 - n.y * gv.scale; GraphDraw(); }
function GraphCenter() { const gv = S.graphView; const canvas = $("#graph-canvas"); if (!canvas) return; const ns = gv._nodes || []; if (!ns.length) { gv.tx = canvas.clientWidth / 2; gv.ty = 60; return; } const xs = ns.map(n => n.x), ys = ns.map(n => n.y); const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2; gv.tx = canvas.clientWidth / 2 - cx * gv.scale; gv.ty = canvas.clientHeight / 2 - cy * gv.scale; }
function openNode(id) {
  const c = S.bundle.characters.find(x => x.id === id); if (!c) return;
  $$(".side-tabs button")[1].click();
  S.graphView.detailId = id;
  window._renderSideTab("detail");
}

/* ── 人物编辑器 ─────────────────────────────── */
function CharacterEditor(existing) {
  const b = S.bundle;
  const c = existing ? JSON.parse(JSON.stringify(existing)) : {
    id: "", name: "", alias: "", gender: "UNKNOWN", age: "", oneLiner: "", personality: "",
    background: "", appearance: "", speechStyle: "", openingLine: "", avatarUrl: "",
    importance: "SUPPORTING", model: null, tags: [], isUser: false,
  };
  const mask = openModal(`${modalHead(existing ? "编辑人物" : "添加人物")}<div class="modal-body" id="ce-body"></div>
    <div class="modal-foot">${existing ? '<button class="btn btn-danger" id="ce-del" style="margin-right:auto">删除</button>' : ""}
    <button class="btn btn-ghost" onclick="this.closest('.modal-mask').remove()">取消</button>
    <button class="btn btn-ink" id="ce-save">保存</button></div>`, { wide: true });
  const body = $("#ce-body", mask);
  function render() {
    body.innerHTML = `
      <div style="display:flex;gap:16px;margin-bottom:14px">
        <div style="text-align:center;flex:none">${avatarHtml(c, 66, true)}
          <div style="display:flex;flex-direction:column;gap:5px;margin-top:8px">
            <button class="btn btn-ghost" style="padding:4px 10px;font-size:12px" id="ce-av-up">上传</button>
            <button class="btn btn-ghost" style="padding:4px 10px;font-size:12px" id="ce-av-gen">AI 生成</button></div></div>
        <div style="flex:1">
          <div class="field"><label>姓名 *</label><input class="inp" id="ce-name" value="${esc(c.name)}"></div>
          <div style="display:flex;gap:10px">
            <div class="field" style="flex:1"><label>别称</label><input class="inp" id="ce-alias" value="${esc(c.alias)}"></div>
            <div class="field" style="width:110px"><label>性别</label><select class="inp" id="ce-gender">${GENDERS.map(g => `<option value="${g[0]}" ${g[0] === c.gender ? "selected" : ""}>${g[1]}</option>`).join("")}</select></div>
            <div class="field" style="width:90px"><label>年龄</label><input class="inp" id="ce-age" value="${esc(c.age)}"></div></div>
          <div class="field"><label>一句话简介</label><input class="inp" id="ce-oneliner" value="${esc(c.oneLiner)}"></div>
        </div></div>
      <div class="field"><label>性格特点</label><textarea class="inp" id="ce-personality" rows="2">${esc(c.personality)}</textarea></div>
      <div class="field"><label>背景经历</label><textarea class="inp" id="ce-background" rows="3">${esc(c.background)}</textarea></div>
      <div style="display:flex;gap:10px">
        <div class="field" style="flex:1"><label>外貌</label><textarea class="inp" id="ce-appearance" rows="2">${esc(c.appearance)}</textarea></div>
        <div class="field" style="flex:1"><label>说话风格</label><textarea class="inp" id="ce-speech" rows="2">${esc(c.speechStyle)}</textarea></div></div>
      <div class="field"><label>开场白（空会话的第一句话）</label><input class="inp" id="ce-opening" value="${esc(c.openingLine)}"></div>
      <div class="field"><label>与你的关系标签（决定 TA 怎么对待你）</label>
        <div class="trope-box" id="ce-tags">${S.templates.tags.map(t => `<span class="chip click ${c.tags.some(x => x.label === t.label) ? "on" : ""}" data-tag="${esc(t.label)}">${esc(t.label)}</span>`).join("")}</div></div>
      <div style="display:flex;gap:12px;align-items:flex-end">
        <div class="field" style="width:150px"><label>重要性</label><select class="inp" id="ce-importance">${Object.keys(IMPORTANCE).map(k => `<option value="${k}" ${k === c.importance ? "selected" : ""}>${IMPORTANCE[k].label} · ${IMPORTANCE[k].tier === "PREMIUM" ? "旗舰" : IMPORTANCE[k].tier === "STANDARD" ? "标准" : "经济"}</option>`).join("")}</select></div>
        <div class="field" style="flex:1"><label>使用模型</label>
          <button class="btn btn-ghost" id="ce-model" style="width:100%;justify-content:flex-start">${c.model ? esc(c.model.label || c.model.modelId) : "跟随社会默认"}</button></div>
        <label style="display:flex;align-items:center;gap:8px;padding-bottom:14px;font-size:12.5px;color:var(--text-2)"><span class="switch"><input type="checkbox" id="ce-isuser" ${c.isUser ? "checked" : ""}><i></i></span>我本人</label></div>
      <input type="file" id="ce-file" accept="image/*" style="display:none">`;
    const bind = (id, k) => { const el = $(id, body); el.oninput = el.onchange = () => { c[k] = el.value; }; };
    bind("#ce-name", "name"); bind("#ce-alias", "alias"); bind("#ce-gender", "gender"); bind("#ce-age", "age");
    bind("#ce-oneliner", "oneLiner"); bind("#ce-personality", "personality"); bind("#ce-background", "background");
    bind("#ce-appearance", "appearance"); bind("#ce-speech", "speechStyle"); bind("#ce-opening", "openingLine");
    $("#ce-importance", body).onchange = e => { c.importance = e.target.value; };
    $("#ce-isuser", body).onchange = e => { c.isUser = e.target.checked; };
    $("#ce-model", body).onclick = () => ModelPicker(ref => { c.model = ref; $("#ce-model", body).textContent = ref.label || ref.modelId; }, c.model && c.model.endpointId);
    $$("#ce-tags .chip", body).forEach(ch => ch.onclick = () => {
      const lb = ch.dataset.tag; const i = c.tags.findIndex(x => x.label === lb);
      if (i >= 0) c.tags.splice(i, 1); else { const t = S.templates.tags.find(x => x.label === lb); c.tags.push({ label: lb, hint: t ? t.hint : "", builtin: true }); }
      ch.classList.toggle("on");
    });
    $("#ce-file", body).onchange = async e => {
      const f = e.target.files[0]; if (!f) return; e.target.value = "";
      await uploadAsAvatar(f);
    };
    $("#ce-av-up", body).onclick = () => $("#ce-file", body).click();
    $("#ce-av-gen", body).onclick = async () => {
      const prompt = (c.appearance || `${c.name}，${(c.personality || "").slice(0, 40)}`) + "，肖像特写，半身构图，日系清新插画，干净背景，柔和光线，高质量，细节丰富" + (c.gender === "MALE" ? "，男性角色" : c.gender === "FEMALE" ? "，女性角色" : "");
      const btn = $("#ce-av-gen", body); btn.innerHTML = '<span class="spin"></span>'; btn.disabled = true;
      try {
        const d = await apiPost(`/api/societies/${b.society.id}/generate-image`, { kind: "avatar", prompt, ratio: "1:1" });
        c.avatarUrl = d.url; render();
        toast("头像已生成");
      } catch (e) { toast(e.message, true); }
      btn.disabled = false; btn.textContent = "AI 生成";
    };
    async function uploadAsAvatar(f) {
      const dataBase64 = await fileToB64(f);
      const d = await apiPost("/api/upload-image", { societyId: b.society.id, dataBase64, ext: f.name.split(".").pop() });
      c.avatarUrl = d.url; render();
    }
  }
  function fileToB64(f) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.onerror = rej; r.readAsDataURL(f); }); }
  render();
  $("#ce-save", mask).onclick = async () => {
    c.name = $("#ce-name", body).value.trim();
    if (!c.name) { toast("名字不能为空", true); return; }
    try {
      await apiPost(`/api/societies/${b.society.id}/characters`, c);
      mask.remove(); toast("已保存"); await reloadBundle(); window._renderSideTab(S.graphView.detailId === c.id ? "detail" : "chars");
    } catch (e) { toast(e.message, true); }
  };
  const delBtn = $("#ce-del", mask);
  if (delBtn) delBtn.onclick = async () => {
    if (!confirm(`删除人物「${c.name}」？TA 的会话与关系将一并删除。`)) return;
    await apiDelete(`/api/societies/${b.society.id}/characters/${c.id}`);
    mask.remove(); toast("已删除"); await reloadBundle(); window._renderSideTab("chars");
  };
}

/* ── 社会模型配置 ──────────────────────────── */
function SocietyModelsModal() {
  const soc = S.bundle.society;
  const mask = openModal(`${modalHead("社会模型配置")}<div class="modal-body">
    <div class="field"><label>旁白使用的模型</label>
      <button class="btn btn-ghost" id="sm-narr" style="width:100%;justify-content:flex-start">${soc.narratorModel ? esc(soc.narratorModel.label || soc.narratorModel.modelId) : "未指定 —— 旁白推进剧情前必须先配置"}</button></div>
    <div class="field"><label>人物默认模型（新人物未单独指定时使用）</label>
      <button class="btn btn-ghost" id="sm-char" style="width:100%;justify-content:flex-start">${soc.defaultCharacterModel ? esc(soc.defaultCharacterModel.label || soc.defaultCharacterModel.modelId) : "未指定"}</button></div>
    <div class="field"><label>文生图模型（头像与聊天配图）</label>
      <button class="btn btn-ghost" id="sm-img" style="width:100%;justify-content:flex-start">${soc.imageModel ? esc(soc.imageModel.label || soc.imageModel.modelId) : "未指定"}</button></div>
    <div class="muted">新 NPC 由旁白按重要性自动分配档位模型（可在设置里关闭）。</div></div>
    <div class="modal-foot"><button class="btn btn-ink" id="sm-ok">完成</button></div>`);
  $("#sm-narr", mask).onclick = () => ModelPicker(ref => { soc.narratorModel = ref; $("#sm-narr", mask).textContent = ref.label || ref.modelId; save(); });
  $("#sm-char", mask).onclick = () => ModelPicker(ref => { soc.defaultCharacterModel = ref; $("#sm-char", mask).textContent = ref.label || ref.modelId; save(); });
  $("#sm-img", mask).onclick = () => ImagePresetPicker(ref => {
    // 生图模型需要挂在生图接入点上
    const eps = (S.settings.endpoints || []).filter(e => e.kind === "IMAGE");
    const ep = eps.find(e => e.vendor === ref.vendor) || eps[0];
    if (!ep) { toast("请先到设置里添加一个「文生图模型」类型的接入点", true); return; }
    soc.imageModel = { endpointId: ep.id, modelId: ref.modelId, label: ref.label, vendor: ref.vendor };
    $("#sm-img", mask).textContent = ref.label || ref.modelId; save();
  });
  async function save() { await apiPut(`/api/societies/${soc.id}/society`, { narratorModel: soc.narratorModel, defaultCharacterModel: soc.defaultCharacterModel, imageModel: soc.imageModel }); }
  $("#sm-ok", mask).onclick = () => mask.remove();
}

/* ── 上帝视角 ──────────────────────────────── */
function GodViewModal() {
  const b = S.bundle;
  const mask = openModal(`${modalHead("上帝视角 · 让 NPC 互相说话")}<div class="modal-body">
    <div style="display:flex;gap:10px">
      <select class="inp" id="gv-a">${b.characters.filter(c => !c.isUser).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>
      <span style="align-self:center;color:var(--text-3)">→</span>
      <select class="inp" id="gv-b">${b.characters.filter(c => !c.isUser).map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></div>
    <div class="field" style="margin-top:12px"><label>话题</label><input class="inp" id="gv-topic" placeholder="比如：昨天冷柜前发生的事" value="聊聊最近的近况"></div>
    <button class="btn btn-ink" id="gv-go" style="width:100%;justify-content:center">开始对话</button>
    <div class="god-result" id="gv-out" style="margin-top:12px;display:none"></div></div>`, { wide: true });
  $("#gv-go", mask).onclick = async () => {
    const a = $("#gv-a", mask).value, bb = $("#gv-b", mask).value;
    if (a === bb) { toast("选两个不同的人", true); return; }
    const out = $("#gv-out", mask); out.style.display = "block"; out.textContent = "";
    $("#gv-go", mask).disabled = true;
    const nameA = (b.characters.find(c => c.id === a) || {}).name || "";
    try {
      await ssePost(`/api/societies/${b.society.id}/godview`, { aId: a, bId: bb, topic: $("#gv-topic", mask).value }, ev => {
        if (ev.type === "delta") {
          const raw = ev.buffer || "";
          const segs = hcParseStreaming(raw);
          out.textContent = `${nameA}：` + segs.map(s => s.type === "text" ? s.content : s.type === "sticker" ? "[表情]" : s.type === "transfer" ? "[转账]" : "[图片]").join("");
          out.scrollTop = out.scrollHeight;
        }
        if (ev.type === "failed") { out.textContent += "\n\n[失败] " + ev.error; }
        if (ev.type === "done") { out.textContent += "\n\n—— 对话结束（仅记入日志，不进入任何人的会话）"; }
      });
    } catch (e) { out.textContent += "\n[失败] " + e.message; }
    $("#gv-go", mask).disabled = false;
  };
}

/* ── 聊天页 ────────────────────────────────── */
async function ChatView(sid, cid) {
  const app = $("#app");
  app.innerHTML = `<div style="height:100vh;display:flex;align-items:center;justify-content:center;color:var(--text-3)">' + SPIN + '加载中…</div>`;
  let bundle, thread;
  try {
    [bundle, thread] = await Promise.all([apiGet(`/api/societies/${sid}`), apiGet(`/api/societies/${sid}/chats/${cid}`)]);
  } catch (e) { app.innerHTML = `<div style="padding:60px;text-align:center;color:var(--text-2)">${esc(e.message)}</div>`; return; }
  if (!S.bundle || S.bundle.society.id !== sid) S.bundle = bundle;
  const c = bundle.characters.find(x => x.id === cid);
  if (!c) { toast("人物不存在", true); goto("#/society/" + sid); return; }
  const imp = IMPORTANCE[c.importance];
  let streaming = false; let pendingAttach = "";
  const stickers = bundle.stickers || [];

  app.innerHTML = `<div class="chat-page">
    <div class="chat-head">
      <button class="back" style="width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center" onclick="goto('#/society/${sid}')">←</button>
      ${avatarHtml(c, 42, true)}
      <div style="flex:1;min-width:0"><div style="font-weight:700;font-size:16px">${esc(c.name)} <span class="chip" style="background:${imp.color}22;color:${imp.color}">${imp.label}</span>${c.tags.map(t => `<span class="chip violet">${esc(t.label)}</span>`).join("")}</div>
      <div class="muted" id="chat-sub"></div></div></div>
    <div class="chat-msgs" id="chat-msgs"><div class="chat-inner" id="chat-inner"></div></div>
    <div class="chat-inputbar"><div class="chat-input-inner-wrap" style="max-width:760px;margin:0 auto">
      <div class="att-preview" id="att-preview" style="display:none"></div>
      <div id="sticker-panel" style="display:none;margin-bottom:10px;background:var(--surface);border:1px solid var(--outline-2);border-radius:14px;padding:10px;max-height:190px;overflow-y:auto"></div>
      <div class="chat-input-inner">
        <button class="icon-btn" id="btn-attach" title="发图片" style="width:40px;height:40px">🖼</button>
        <button class="icon-btn" id="btn-sticker" title="表情包" style="width:40px;height:40px">☺</button>
        <textarea id="chat-input" rows="1" placeholder="说点什么…"></textarea>
        <button class="icon-btn" id="btn-transfer" title="转账" style="width:40px;height:40px">¥</button>
        <button class="send-btn" id="btn-send">➤</button></div></div>
    <input type="file" id="attach-file" accept="image/*" style="display:none"></div>`;

  const inner = $("#chat-inner");
  function updateSub() {
    const cost = thread.messages.reduce((a, m) => a + (m.costUsd || 0), 0);
    const tok = thread.messages.reduce((a, m) => a + (m.tokensOut || 0), 0);
    $("#chat-sub").textContent = `${fmtCny(cost)} · ${fmtTok(tok)} tok` + (c.model ? ` · ${esc(c.model.label || c.model.modelId)}` : "");
  }
  function renderSticker(seg, seed) {
    const r = stickerResolve(stickers, seg.emotion, seg.stickerId, seed);
    if (r.kind === "emoji") return `<div class="sticker-emoji">${r.glyph}</div>`;
    return `<img class="sticker-img" src="${esc(mediaUrl(r.sticker.imageUrl))}" loading="lazy">`;
  }
  function renderSeg(seg, seed, msg) {
    if (seg.type === "text") return seg.content ? `<div class="bubble">${esc(seg.content)}</div>` : "";
    if (seg.type === "sticker") return renderSticker(seg, seed);
    if (seg.type === "picture") {
      if (seg.state === "READY" && seg.url) return `<div class="pic-card"><img src="${esc(mediaUrl(seg.url))}">${seg.caption ? `<div class="cap">${esc(seg.caption)}</div>` : ""}</div>`;
      if (seg.state === "FAILED") return `<div class="pic-card"><div class="ph">⚠ 图片生成失败<br><span class="muted">${esc(seg.error || "未配置生图模型或生成出错")}</span></div></div>`;
      return `<div class="pic-card"><div class="ph"><span class="spin"></span>正在画：${esc(seg.prompt || "")}</div>${seg.caption ? `<div class="cap">${esc(seg.caption)}</div>` : ""}</div>`;
    }
    if (seg.type === "transfer") {
      return `<div class="transfer-card"><div class="yuan">¥</div>
        <div><div class="amt">¥${Number(seg.amount).toFixed(2)}</div><div class="to">给 ${esc(seg.to)}</div>${seg.note ? `<div class="note">${esc(seg.note)}</div>` : ""}</div>
        ${seg.confirmed ? '<span class="ok-badge">已收下</span>' : (msg && msg.id ? `<button class="btn btn-amber" data-confirm="${esc(msg.id)}">收下</button>` : "")}</div>`;
    }
    return "";
  }
  function renderMsg(msg, liveBuffer) {
    const isMe = msg.role === "USER";
    const isNarr = msg.role === "NARRATOR";
    const seed = fnv1a(msg.id || String(msg.ts));
    if (isNarr) return `<div class="msg-row narr"><div class="narr-line">${esc(hcPlainText(liveBuffer ? hcParseStreaming(liveBuffer) : msg.segments))}</div></div>`;
    const speaker = isMe ? (bundle.characters.find(x => x.isUser) || null) : c;
    let segs;
    if (liveBuffer != null) segs = hcParseStreaming(liveBuffer);
    else segs = msg.segments && msg.segments.length ? msg.segments : hcParse(msg.raw || "");
    if (!segs.length) return "";
    const body = segs.map(s => renderSeg(s, seed, msg)).join("");
    const meta = msg.modelLabel || msg.tokensOut ? `<div class="msg-meta">${esc(msg.modelLabel || "")}${msg.tokensOut ? ` · ${fmtTok(msg.tokensOut || 0)} tok` : ""}${msg.costUsd ? ` · ${fmtCny(msg.costUsd)}` : ""}${msg.status === "FAILED" ? " · 失败" : ""}</div>` : "";
    return `<div class="msg-row ${isMe ? "me" : "them"}">
      ${speaker ? avatarHtml(speaker, 32) : '<div class="avatar" style="width:32px;height:32px">?</div>'}
      <div class="msg-stack">${body}${meta}</div></div>`;
  }
  function renderAll() {
    inner.innerHTML = thread.messages.map(m => renderMsg(m)).join("") +
      (streaming ? `<div class="msg-row them">${avatarHtml(c, 32)}<div class="msg-stack" id="live-slot"></div></div>` : "");
    bindConfirms();
    updateSub();
    scrollBottom();
  }
  function bindConfirms() {
    $$("[data-confirm]", inner).forEach(btn => btn.onclick = async () => {
      const m = thread.messages.find(x => x.id === btn.dataset.confirm);
      if (!m) return;
      await apiPost(`/api/societies/${sid}/confirm-transfer`, { charId: cid, msgId: m.id });
      m.segments.forEach(s => { if (s.type === "transfer") s.confirmed = true; });
      renderAll();
      toast("已收下（模拟支付，没有真实资金流动）");
    });
  }
  function scrollBottom() { const box = $("#chat-msgs"); box.scrollTop = box.scrollHeight; }

  renderAll();
  if (!thread.messages.length && c.openingLine) {
    // 开场白：显示但不入库（与安卓一致，独立于人设）
    inner.innerHTML += `<div class="msg-row them">${avatarHtml(c, 32)}<div class="msg-stack"><div class="bubble">${esc(c.openingLine)}</div></div></div>`;
  }
  bindConfirms();
  // 自动补图：找出 GENERATING 的图片段
  autoGenImages();

  async function autoGenImages() {
    for (const m of thread.messages) {
      if (m.role !== "CHARACTER") continue;
      const pics = (m.segments || []).filter(s => s.type === "picture" && s.state === "GENERATING");
      for (const p of pics) {
        try {
          const d = await apiPost(`/api/societies/${sid}/generate-image`, { kind: "chat", prompt: p.prompt, ratio: p.ratio || "3:4", style: p.style || "" });
          p.url = d.url; p.state = "READY";
        } catch (e) { p.state = "FAILED"; p.error = e.message; }
        await apiPost(`/api/societies/${sid}/update-message`, { charId: cid, message: m });
        renderAll();
      }
    }
  }

  const input = $("#chat-input");
  input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(130, input.scrollHeight) + "px"; });
  $("#btn-send").onclick = send;
  $("#btn-attach").onclick = () => $("#attach-file").click();
  $("#attach-file").onchange = async e => {
    const f = e.target.files[0]; if (!f) return; e.target.value = "";
    try {
      const b64 = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.onerror = rej; r.readAsDataURL(f); });
      const d = await apiPost("/api/upload-image", { societyId: sid, dataBase64: b64, ext: f.name.split(".").pop() });
      pendingAttach = d.url;
      $("#att-preview").style.display = "flex";
      $("#att-preview").innerHTML = `<img src="${mediaUrl(d.url)}"><span>将随下一条消息发送</span><button class="btn btn-ghost" style="padding:3px 10px;font-size:11px" id="att-x">移除</button>`;
      $("#att-x").onclick = () => { pendingAttach = ""; $("#att-preview").style.display = "none"; };
    } catch (err) { toast(err.message, true); }
  };
  $("#btn-sticker").onclick = () => {
    const p = $("#sticker-panel");
    if (p.style.display === "none") {
      const emotions = ["笑哭", "抱抱", "点赞", "狗头", "吃瓜", "开心", "泪目", "无语", "生气", "比心", "震惊", "拜拜"];
      p.innerHTML = (stickers.length ? `<div style="font-size:11.5px;color:var(--text-3);margin-bottom:6px">本社会专属</div><div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">${stickers.map(s => `<img class="sticker-img" style="width:52px;height:52px" data-stk="${s.id}" data-emo="${esc((s.emotions || [])[0] || s.name)}" src="${esc(mediaUrl(s.imageUrl))}" title="${esc(s.name)}">`).join("")}</div>` : "") +
        `<div style="font-size:11.5px;color:var(--text-3);margin-bottom:6px">通用情绪</div><div style="display:flex;flex-wrap:wrap;gap:6px">${emotions.map(e => `<span class="chip click" data-emo="${e}">${e}</span>`).join("")}</div>`;
      p.style.display = "block";
      $$("[data-emo]", p).forEach(el => el.onclick = () => { p.style.display = "none"; input.value = `<sticker emotion="${el.dataset.emo}" />`; send(); });
      $$("[data-stk]", p).forEach(el => el.onclick = () => { p.style.display = "none"; input.value = `<sticker id="${el.dataset.stk}" emotion="${el.dataset.emo}" />`; send(); });
    } else p.style.display = "none";
  };
  $("#btn-transfer").onclick = () => {
    const mask = openModal(`${modalHead("给 " + c.name + " 转账")}<div class="modal-body">
      <div class="field"><label>金额（元）</label><input class="inp" id="tf-amt" type="number" step="0.01" min="0.01" placeholder="5.20"></div>
      <div class="field"><label>备注</label><input class="inp" id="tf-note" placeholder="请你喝奶茶"></div>
      <div class="muted">转账只是剧情演出，不会发生真实支付。</div></div>
      <div class="modal-foot"><button class="btn btn-ghost" onclick="this.closest('.modal-mask').remove()">取消</button><button class="btn btn-amber" id="tf-ok">塞钱进聊天</button></div>`);
    $("#tf-ok", mask).onclick = () => {
      const amt = parseFloat($("#tf-amt", mask).value);
      if (!(amt > 0)) { toast("金额不合法", true); return; }
      mask.remove();
      input.value = `<transfer amount="${amt.toFixed(2)}" to="${c.name}" note="${($("#tf-note", mask) || {}).value || ""}" />`;
      send();
    };
  };

  async function send() {
    if (streaming) return;
    const text = input.value.trim();
    if (!text && !pendingAttach) return;
    streaming = true; input.value = ""; input.style.height = "auto";
    const att = pendingAttach; pendingAttach = ""; $("#att-preview").style.display = "none";
    // 乐观插入用户消息，立即可见
    thread.messages.push({ id: "pending", role: "USER", charId: cid, segments: hcParse(text), raw: text, ts: nowMs(), status: "DONE", attachment: att });
    renderAll();
    const slot = () => $("#live-slot");
    try {
      await ssePost(`/api/societies/${sid}/chat/${cid}/send`, { text, attachment: att }, ev => {
        if (ev.type === "delta" && slot()) { slot().innerHTML = renderMsg({ role: "CHARACTER", id: "live", ts: nowMs(), segments: [] }, ev.buffer); scrollBottom(); }
        if (ev.type === "vision_used") { toast("图片经视觉桥接转述给对方"); }
        if (ev.type === "failed") { toast(ev.error, true); }
        if (ev.type === "done") { thread.messages.push(ev.message); }
      });
    } catch (e) { toast(e.message, true); }
    // 重新拉取线程以同步持久化结果
    try { thread = await apiGet(`/api/societies/${sid}/chats/${cid}`); } catch (e) { }
    streaming = false; renderAll(); autoGenImages();
  }
}

/* ── 设置页 ────────────────────────────────── */
async function SettingsView() {
  const app = $("#app");
  S.settings = await apiGet("/api/settings"); window._settings = S.settings; applyTheme();
  const st = S.settings;
  const syncInfo = await apiGet("/api/sync-info").catch(() => ({ lanUrl: "" }));
  const snap = await apiGet("/api/catalog?limit=1").catch(() => ({}));
  const vendors = S.vendors;
  const vendorOf = k => vendors.find(v => v.key === k) || { color: "#7A8291", monogram: "··" };
  app.innerHTML = `<div class="page"><div class="settings-wrap">
    <div style="display:flex;align-items:center;gap:12px"><button class="btn btn-ghost" onclick="goto('#/')">←</button><h1>设置</h1></div>

    <div class="set-section"><h3>模型接入点</h3><div class="set-card" id="ep-list"></div>
      <div style="margin-top:10px"><button class="btn btn-ink" id="ep-add">＋ 添加接入点</button></div></div>

    <div class="set-section"><h3>已保存的模型配置</h3><div class="set-card" id="sm-list"></div></div>

    <div class="set-section"><h3>视觉桥接 <span class="muted">—— 给纯文本模型补上「看图」能力</span></h3><div class="set-card">
      <div class="set-row"><div class="info"><b>启用视觉桥接</b><span>角色模型不支持读图时，先用视觉模型转述图片内容</span></div>
        <label class="switch"><input type="checkbox" id="set-vision" ${st.visionEnabled ? "checked" : ""}><i></i></label></div>
      <div class="set-row"><div class="info"><b>视觉模型</b><span id="vision-desc">${esc(st.visionBaseUrl)} · ${esc(st.visionModel)}</span></div>
        <button class="btn btn-ghost" id="vision-edit">配置</button></div></div></div>

    <div class="set-section"><h3>旁白与玩法</h3><div class="set-card">
      <div class="set-row"><div class="info"><b>旁白自动分配模型</b><span>按新 NPC 的重要性自动挑选档位合适的模型</span></div>
        <label class="switch"><input type="checkbox" id="set-autoassign" ${st.narratorAutoAssignModel ? "checked" : ""}><i></i></label></div>
      <div class="set-row"><div class="info"><b>旁白自动建立关系连线</b><span>新 NPC 的关系直接写入关系图</span></div>
        <label class="switch"><input type="checkbox" id="set-autolink" ${st.narratorAutoLinkRelations ? "checked" : ""}><i></i></label></div>
      <div class="set-row"><div class="info"><b>上帝视角</b><span>允许让两个 NPC 互相说话（不进入用户会话）</span></div>
        <label class="switch"><input type="checkbox" id="set-godview" ${st.godViewEnabled ? "checked" : ""}><i></i></label></div>
      <div class="set-row"><div class="info"><b>旁白输出体检</b><span>本地规则检查旁白输出（空输出 / 过短 / 重复 / 协议标签未闭合），结果写入日志并提示；内容总是保留</span></div>
        <label class="switch"><input type="checkbox" id="set-guard" ${st.guardEnabled ? "checked" : ""}><i></i></label></div>
      <div class="set-row"><div class="info"><b>进入社会自动推进剧情</b><span>每次打开社会时让旁白检查一次推进</span></div>
        <label class="switch"><input type="checkbox" id="set-autonarr" ${st.autoNarratorOnEnter ? "checked" : ""}><i></i></label></div></div></div>

    <div class="set-section"><h3>模型目录 <span class="muted">—— ${snap.totalModels || 0} 个模型 · ${snap.origin || ""} · 免费 ${snap.freeCount || 0} · 支持读图 ${snap.visionCount || 0}</span></h3>
      <div class="set-card">
      <div class="set-row"><div class="info"><b>浏览与检索</b><span>按价格 / 厂商 / 能力筛选全部模型</span></div><button class="btn btn-ghost" id="cat-browse">打开目录</button></div>
      <div class="set-row"><div class="info"><b>在线刷新</b><span>从 modelwatch 导出地址拉取最新价格${st.catalogRefreshedAt ? ` · 上次 ${relTime(st.catalogRefreshedAt)}` : ""}</span></div><button class="btn btn-ghost" id="cat-refresh">刷新</button></div>
      <div class="set-row"><div class="info"><b>手动导入 / 恢复内置</b><span>粘贴导出 JSON，或回到随应用发布的快照</span></div>
        <button class="btn btn-ghost" id="cat-import">导入</button><button class="btn btn-ghost" id="cat-reset">恢复内置</button></div></div></div>

    <div class="set-section"><h3>界面</h3><div class="set-card">
      <div class="set-row"><div class="info"><b>主题</b><span>琥珀强调色保持不变</span></div>
        <select class="inp" id="set-theme" style="width:130px"><option value="LIGHT" ${st.themeMode === "LIGHT" ? "selected" : ""}>浅色</option><option value="DARK" ${st.themeMode === "DARK" ? "selected" : ""}>深色</option><option value="SYSTEM" ${st.themeMode === "SYSTEM" ? "selected" : ""}>跟随系统</option></select></div>
      <div class="set-row"><div class="info"><b>关系图默认布局</b></div>
        <select class="inp" id="set-layout" style="width:130px"><option value="TREE" ${st.graphLayout !== "CHAIN" ? "selected" : ""}>树状图</option><option value="CHAIN" ${st.graphLayout === "CHAIN" ? "selected" : ""}>链式图</option></select></div>
      <div class="set-row"><div class="info"><b>美元 → 人民币汇率</b><span>花费按美元记账、按此汇率展示；当前 ${st.usdToCnyRate}</span></div>
        <input class="inp" id="set-rate" type="number" step="0.01" style="width:110px" value="${st.usdToCnyRate}"></div></div></div>

    <div class="set-section"><h3>手机数据互通</h3><div class="set-card">
      <div class="set-row"><div class="info"><b>局域网同步页</b><span>手机浏览器打开：<b>${esc(syncInfo.lanUrl)}</b>（需同一 Wi-Fi）</span>
        <span class="muted" style="margin-top:4px;display:block">手机端「导出社会」→ 同步页上传；点下载拿回手机「导入」。导入总是生成新副本，不会覆盖两端数据。</span></div>
        <button class="btn btn-ink" id="sync-open">打开</button></div></div></div>

    <div class="set-section"><h3>服务</h3><div class="set-card">
      <div class="set-row"><div class="info"><b>Kith Desktop 0.2.0</b><span>本地服务运行中 · 数据在应用目录 data/ 下，可直接备份</span></div>
        <button class="btn btn-danger" id="app-quit">退出服务</button></div></div></div>
  </div></div>`;

  // 接入点列表
  function renderEps() {
    $("#ep-list").innerHTML = (st.endpoints || []).length ? st.endpoints.map(e => {
      const v = vendorOf(e.vendor);
      return `<div class="set-row">${vendorTile(v)}<div class="info"><b>${esc(e.label || e.vendor)} <span class="chip">${e.kind === "IMAGE" ? "生图" : "对话"}</span></b><span>${esc(v.name)} · ${esc(e.baseUrl)}</span></div>
        <button class="btn btn-ghost" data-edit="${e.id}">编辑</button><button class="btn btn-danger" data-delep="${e.id}">删除</button></div>`;
    }).join("") : '<div class="empty-note">还没有接入点。添加一个厂商的 API Key 才能开始对话。</div>';
    $$("[data-edit]").forEach(b => b.onclick = () => EndpointEditor(st.endpoints.find(x => x.id === b.dataset.edit)));
    $$("[data-delep]").forEach(b => b.onclick = async () => {
      const e = st.endpoints.find(x => x.id === b.dataset.delep);
      if (!confirm(`删除接入点「${e.label || e.vendor}」？挂在它下面的已保存模型配置也会一并清除。`)) return;
      await apiPost("/api/endpoints/delete", { id: e.id });
      S.settings = await apiGet("/api/settings"); st.endpoints = S.settings.endpoints; st.savedModels = S.settings.savedModels;
      renderEps(); renderSaved();
    });
  }
  function renderSaved() {
    $("#sm-list").innerHTML = (st.savedModels || []).length ? st.savedModels.map((m, i) => {
      const e = (st.endpoints || []).find(x => x.id === m.endpointId);
      const v = vendorOf(m.vendor || (e ? e.vendor : ""));
      return `<div class="set-row">${vendorTile(v, 34)}<div class="info"><b>${esc(m.label || m.modelId)}</b><span>${e ? esc(e.label || e.vendor) : "接入点已删除"}</span></div>
        <button class="btn btn-danger" data-delsm="${i}">移除</button></div>`;
    }).join("") : '<div class="empty-note">在模型选择器里挑好的模型会存到这里，跨社会复用。</div>';
    $$("[data-delsm]").forEach(b => b.onclick = async () => {
      await apiPost("/api/saved-models/delete", { ref: st.savedModels[+b.dataset.delsm] });
      S.settings = await apiGet("/api/settings"); st.savedModels = S.settings.savedModels; renderSaved();
    });
  }
  renderEps(); renderSaved();
  $("#ep-add").onclick = () => EndpointEditor(null);

  // 视觉桥接
  $("#set-vision").onchange = async e => { await apiPut("/api/settings", { visionEnabled: e.target.checked }); };
  $("#vision-edit").onclick = () => {
    const s2 = S.settings;
    const mask = openModal(`${modalHead("视觉桥接配置")}<div class="modal-body">
      <div class="field"><label>接入地址</label><input class="inp" id="vb-base" value="${esc(s2.visionBaseUrl)}"></div>
      <div class="field"><label>API Key</label><input class="inp" id="vb-key" value="${esc(s2.visionApiKey)}"></div>
      <div class="field"><label>模型</label><input class="inp" id="vb-model" value="${esc(s2.visionModel)}"></div>
      <div class="muted">填你自己的 Key（GLM-4V-Flash 有免费额度）。仓库不含任何密钥，别把 Key 提交进代码。</div></div>
      <div class="modal-foot"><button class="btn btn-ghost" id="vb-reset">恢复默认</button><button class="btn btn-ink" id="vb-ok">保存</button></div>`);
    $("#vb-ok", mask).onclick = async () => {
      await apiPut("/api/settings", { visionBaseUrl: $("#vb-base", mask).value.trim().replace(/\/+$/, ""), visionApiKey: $("#vb-key", mask).value.trim(), visionModel: $("#vb-model", mask).value.trim(), visionNoticeAccepted: true });
      mask.remove(); SettingsView._reload();
    };
    $("#vb-reset", mask).onclick = async () => {
      // 恢复默认只还原地址和模型，Key 清空由用户自己填
      await apiPut("/api/settings", { visionBaseUrl: "https://open.bigmodel.cn/api/paas/v4", visionModel: "glm-4v-flash", visionApiKey: "" });
      mask.remove(); SettingsView._reload();
    };
  };

  // 行为开关
  const bindSwitch = (id, key) => { $(id).onchange = async e => { await apiPut("/api/settings", { [key]: e.target.checked }); }; };
  bindSwitch("#set-autoassign", "narratorAutoAssignModel");
  bindSwitch("#set-autolink", "narratorAutoLinkRelations");
  bindSwitch("#set-godview", "godViewEnabled");
  bindSwitch("#set-guard", "guardEnabled");
  bindSwitch("#set-autonarr", "autoNarratorOnEnter");
  $("#set-theme").onchange = async e => { await apiPut("/api/settings", { themeMode: e.target.value }); S.settings.themeMode = e.target.value; applyTheme(); };
  $("#set-layout").onchange = async e => { await apiPut("/api/settings", { graphLayout: e.target.value }); };
  $("#set-rate").onchange = async e => { const v = parseFloat(e.target.value); if (v > 0) await apiPut("/api/settings", { usdToCnyRate: v }); };

  // 目录
  $("#cat-browse").onclick = () => CatalogBrowser();
  $("#cat-refresh").onclick = async () => {
    const url = prompt("目录刷新地址（modelwatch 导出的 models.json URL）：", S.settings.catalogUrl || "");
    if (!url) return;
    toast("正在刷新目录…");
    try { const d = await apiPost("/api/catalog/refresh", { url }); toast(`已刷新：${d.count} 个模型`); SettingsView._reload(); }
    catch (e) { toast(e.message, true); }
  };
  $("#cat-import").onclick = async () => {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = ".json";
    inp.onchange = async () => { const f = inp.files[0]; if (!f) return; try { const d = await apiPost("/api/catalog/import", await f.text()); toast(`已导入：${d.count} 个模型`); SettingsView._reload(); } catch (e) { toast(e.message, true); } };
    inp.click();
  };
  $("#cat-reset").onclick = async () => { if (!confirm("恢复为内置快照？在线刷新的缓存将被丢弃。")) return; await apiPost("/api/catalog/reset"); toast("已恢复内置快照"); SettingsView._reload(); };
  $("#sync-open").onclick = () => window.open("/sync", "_blank");
  $("#app-quit").onclick = async () => { if (!confirm("退出 Kith 本地服务？桌面窗口与手机同步都将停止。")) return; await apiPost("/api/quit"); setTimeout(() => { document.body.innerHTML = '<div style="display:flex;height:100vh;align-items:center;justify-content:center;color:var(--text-2)">服务已退出，可重新用桌面快捷方式启动。</div>'; }, 300); };
}
SettingsView._reload = () => SettingsView();

/* ── 接入点编辑器 ──────────────────────────── */
function EndpointEditor(existing, onSaved) {
  const isImage = existing ? existing.kind === "IMAGE" : false;
  let vendor = existing ? existing.vendor : null;
  const mask = openModal(`${modalHead(existing ? "编辑接入点" : "添加接入点")}<div class="modal-body">
    <div class="field"><label>类型</label>
      <select class="inp" id="ee-kind"><option value="LLM" ${!isImage ? "selected" : ""}>对话模型</option><option value="IMAGE" ${isImage ? "selected" : ""}>文生图模型</option></select></div>
    <div class="field"><label>厂商</label><div class="ep-chips" id="ee-vendors" style="max-height:170px;overflow-y:auto"></div></div>
    <div class="field"><label>显示名称</label><input class="inp" id="ee-label" value="${esc(existing ? existing.label : "")}" placeholder="默认用厂商名"></div>
    <div class="field"><label>接入地址 baseUrl</label><input class="inp" id="ee-base" value="${esc(existing ? existing.baseUrl : "")}" placeholder="选择厂商后自动填充，或粘贴中转地址"></div>
    <div class="field"><label>API Key</label><input class="inp" id="ee-key" type="password" value="${esc(existing ? existing.apiKey : "")}" placeholder="只存在本机，不上传任何服务器"></div></div>
    <div class="modal-foot"><button class="btn btn-ghost" onclick="this.closest('.modal-mask').remove()">取消</button><button class="btn btn-ink" id="ee-ok">保存</button></div>`);
  const body = $(".modal-body", mask);
  function renderVendors() {
    const kind = $("#ee-kind", mask).value;
    const list = S.vendors.filter(v => kind === "IMAGE" ? ["Seedream", "Wanx", "Kolors", "CogView", "SiliconFlow", "OpenAI", "Google", "NewAPI", "Stability", "BlackForest", "Ideogram", "Recraft", "Midjourney"].includes(v.key) : true);
    $("#ee-vendors", mask).innerHTML = list.map(v => `<button class="ep-chip ${vendor === v.key ? "on" : ""}" data-v="${v.key}"><span class="dot" style="background:${v.color}"></span>${esc(v.name)}</button>`).join("") +
      `<button class="ep-chip ${vendor === "custom" ? "on" : ""}" data-v="custom"><span class="dot" style="background:#7A8291"></span>自定义…</button>`;
    $$("#ee-vendors [data-v]", mask).forEach(b => b.onclick = () => {
      vendor = b.dataset.v;
      const v = S.vendors.find(x => x.key === vendor);
      if (v && v.baseUrl) $("#ee-base", mask).value = v.baseUrl;
      renderVendors();
    });
  }
  $("#ee-kind", mask).onchange = () => { vendor = null; renderVendors(); };
  renderVendors();
  $("#ee-ok", mask).onclick = async () => {
    const kind = $("#ee-kind", mask).value;
    const baseUrl = $("#ee-base", mask).value.trim().replace(/\/+$/, "");
    if (!vendor) { toast("选择一个厂商", true); return; }
    if (!baseUrl) { toast("接入地址不能为空", true); return; }
    try {
      await apiPost("/api/endpoints", {
        id: existing ? existing.id : "", kind,
        vendor: vendor === "custom" ? ($("#ee-label", mask).value.trim() || "custom") : vendor,
        label: $("#ee-label", mask).value.trim(), baseUrl, apiKey: $("#ee-key", mask).value.trim(),
      });
      mask.remove(); toast("接入点已保存");
      if (onSaved) await onSaved(); else SettingsView._reload();
    } catch (e) { toast(e.message, true); }
  };
}

/* ── 模型目录浏览器 ────────────────────────── */
function CatalogBrowser() {
  const mask = openModal(`${modalHead("模型目录")}<div class="modal-body" id="cb-body"></div>`, { wide: true });
  const body = $("#cb-body", mask);
  const q = { kw: "", free: false, vision: false, text: false, sort: "PRICE_ASC", vendor: "", offset: 0 };
  let vendorList = [];
  apiGet("/api/catalog/vendors").then(d => { vendorList = d.vendors; render(); });
  async function renderList() {
    const p = new URLSearchParams({ q: q.kw, sort: q.sort, limit: "60", offset: String(q.offset) });
    if (q.vendor) p.set("vendor", q.vendor);
    if (q.free) p.set("free", "1"); if (q.vision) p.set("vision", "1"); if (q.text) p.set("text", "1");
    const d = await apiGet("/api/catalog?" + p.toString()).catch(() => ({ models: [], total: 0 }));
    $("#cb-list", body).innerHTML = d.models.map(m => `
      <div class="model-row">${vendorTile(m.vendor, 34)}
        <div style="min-width:0"><div class="n">${esc(m.name)} ${m.isFree ? '<span class="chip teal">免费</span>' : ""}${m.supportsVision ? '<span class="chip violet">看图</span>' : ""}${m.expiringSoon ? '<span class="chip rose">即将下线</span>' : ""}</div>
        <div class="d">${esc(m.id)} · ${m.contextLength ? Math.round(m.contextLength / 1000) + "K" : "?"} 上下文 · ${esc(m.vendor.name)}</div></div>
        <div class="price">${priceStr(m)}</div></div>`).join("") +
      (d.total > q.offset + 60 ? `<div style="text-align:center;padding:10px"><button class="btn btn-ghost" id="cb-more">加载更多（共 ${d.total}）</button></div>` : "");
    const more = $("#cb-more", body); if (more) more.onclick = () => { q.offset += 60; renderList(); };
  }
  function priceStr(m) {
    const r = (S.settings.usdToCnyRate) || 7.2;
    if (m.promptPerM == null && m.completionPerM == null) return m.isFree ? "免费" : "价格未知";
    const f = x => x == null ? "?" : "¥" + (x * r).toFixed(x * r < 1 ? 3 : 2);
    return `${f(m.promptPerM)} / ${f(m.completionPerM)}<br><span class="muted">每百万 token</span>`;
  }
  function render() {
    body.innerHTML = `<div class="model-toolbar">
      <input class="inp" id="cb-kw" placeholder="搜索名称 / id / 厂商…" style="flex:1;min-width:140px" value="${esc(q.kw)}">
      <select class="inp" id="cb-vendor" style="width:150px"><option value="">全部厂商</option>${vendorList.map(v => `<option value="${esc(v.vendor.key)}" ${q.vendor === v.vendor.key ? "selected" : ""}>${esc(v.vendor.name)} (${v.count})</option>`).join("")}</select>
      <select class="inp" id="cb-sort" style="width:130px"><option value="PRICE_ASC">价格从低到高</option><option value="PRICE_DESC">价格从高到低</option><option value="NEWEST">最新发布</option><option value="CONTEXT">上下文长度</option><option value="NAME">名称</option></select>
      <span class="chip click ${q.free ? "on" : ""}" data-f="free">免费</span>
      <span class="chip click ${q.vision ? "on" : ""}" data-f="vision">看图</span>
      <span class="chip click ${q.text ? "on" : ""}" data-f="text">纯文本</span></div>
      <div id="cb-list"><div class="empty-note"><span class="spin"></span> 正在加载目录…</div></div>`;
    $("#cb-kw", body).oninput = debounce(e => { q.kw = e.target.value; q.offset = 0; renderList(); }, 300);
    $("#cb-vendor", body).onchange = e => { q.vendor = e.target.value; q.offset = 0; renderList(); };
    $("#cb-sort", body).onchange = e => { q.sort = e.target.value; q.offset = 0; renderList(); };
    $$("[data-f]", body).forEach(c => c.onclick = () => { q[c.dataset.f] = !q[c.dataset.f]; q.offset = 0; render(); });
    renderList();
  }
}

boot();
