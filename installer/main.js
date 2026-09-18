// Kith Desktop —— Electron 主进程。
// 职责：拉起本地服务 → 开原生独立窗口 → 生命周期绑定。
// 三种形态：
//   开发   node_modules electron + python server/main.py（APP_ROOT 硬编码为本工作区）
//   便携   app/Kith.exe + 旁置 web/assets/server（pythonw 拉起）
//   安装   安装目录 Kith.exe + resources/{kith-server.exe, web, assets, kith.ico}
//          （kith-server.exe 为 PyInstaller 冻结的服务端，数据在 %APPDATA%/Kith/data）
"use strict";
const { app, BrowserWindow, Menu } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

const isPackaged = app.isPackaged;
const APP_ROOT = isPackaged ? path.dirname(app.getPath("exe")) : "D:\\PC Projects\\Kith";
const RES_DIR = isPackaged ? process.resourcesPath : APP_ROOT;
const DATA_DIR = isPackaged ? path.join(app.getPath("appData"), "Kith", "data") : path.join(APP_ROOT, "data");
const SERVER_PORT = 19287;
const URL_BASE = `http://127.0.0.1:${SERVER_PORT}`;

// 这台机器的 Chromium GPU 沙箱初始化失败（GPU process exit_code=1 连崩）：
// 关沙箱 + 纯软件渲染。本应用只加载本机 localhost 内容，此组合是容器/VM 环境的标准解。
// 可用 data/gpu-mode.txt 覆盖：a=no-sandbox+禁GPU / d=默认行为
app.disableHardwareAcceleration();
let gpuMode = "a";
try { gpuMode = fs.readFileSync(path.join(DATA_DIR, "gpu-mode.txt"), "utf8").trim() || "a"; } catch (e) { }
if (gpuMode === "a") {
  app.commandLine.appendSwitch("no-sandbox");
  app.commandLine.appendSwitch("disable-gpu");
  app.commandLine.appendSwitch("disable-gpu-compositing");
}

function log(m) {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    fs.appendFileSync(path.join(DATA_DIR, "electron.log"),
      new Date().toISOString().slice(11, 23) + " " + m + "\n");
  } catch (e) { }
}
log(`boot mode=${isPackaged ? "installed" : "dev"} appRoot=${APP_ROOT} res=${RES_DIR} data=${DATA_DIR} gpu=${gpuMode}`);

const PY_CANDIDATES = [
  "C:\\Users\\Administrator\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe",
  "D:\\python\\python.exe",
];
const PY = PY_CANDIDATES.find(p => { try { return fs.existsSync(p); } catch (e) { return false; } });
const SERVER_EXE = path.join(RES_DIR, "kith-server.exe");

let win = null;
let serverProc = null;
let serverStarts = 0;
let quitting = false;
let loaded = false;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.show();
      win.focus();
    }
  });
}

function ping(cb) {
  const req = http.get(`${URL_BASE}/api/ping`, res => {
    let d = "";
    res.on("data", c => (d += c));
    res.on("end", () => {
      try { cb(JSON.parse(d).app === "KithDesktop"); } catch (e) { cb(false); }
    });
  });
  req.on("error", () => cb(false));
  req.setTimeout(800, () => { req.destroy(); cb(false); });
}

function waitServer(tries, cb) {
  ping(ok => {
    if (ok || tries <= 0) return cb(ok);
    setTimeout(() => waitServer(tries - 1, cb), 250);
  });
}

function childEnv() {
  const env = {};
  for (const k of Object.keys(process.env)) {
    if (k !== "ELECTRON_RUN_AS_NODE") env[k] = process.env[k]; // 剥掉会把 electron 退化成无头 Node 的变量
  }
  env.KITH_DATA_DIR = DATA_DIR;
  env.KITH_RES_DIR = RES_DIR;
  env.KITH_APP_ROOT = APP_ROOT;
  return env;
}

function startServer() {
  serverStarts++;
  const out = fs.openSync(path.join(DATA_DIR, "server.log"), "a");
  let proc;
  if (isPackaged || fs.existsSync(SERVER_EXE)) {
    log(`spawn kith-server.exe (第 ${serverStarts} 次)`);
    proc = spawn(SERVER_EXE, [String(SERVER_PORT)], {
      cwd: path.dirname(SERVER_EXE),
      stdio: ["ignore", out, out],
      windowsHide: true,
      env: childEnv(),
    });
  } else if (PY) {
    log(`spawn python (第 ${serverStarts} 次)`);
    proc = spawn(PY, [path.join(APP_ROOT, "server", "main.py"), String(SERVER_PORT)], {
      cwd: APP_ROOT,
      stdio: ["ignore", out, out],
      windowsHide: true,
      env: childEnv(),
    });
  } else {
    log("FATAL: 未找到 Python 解释器且无 kith-server.exe");
    return false;
  }
  serverProc = proc;
  proc.on("exit", (code) => {
    log(`server exited code=${code} starts=${serverStarts} loaded=${loaded} quitting=${quitting}`);
    serverProc = null;
    if (quitting) return;
    if (serverStarts < 3) {
      log("1s 后重拉服务");
      setTimeout(() => { if (!quitting) { startServer(); waitServer(40, ok => log("重拉后 ping=" + ok)); } }, 1000);
    } else if (loaded) {
      log("服务被主动退出，关闭应用");
      if (win && !win.isDestroyed()) win.close();
      setTimeout(() => app.quit(), 300);
    }
  });
  return true;
}

function killServer() {
  if (serverProc) {
    try { serverProc.kill(); } catch (e) { }
    serverProc = null;
  }
}

function createWindow() {
  Menu.setApplicationMenu(null);
  const iconPath = fs.existsSync(path.join(RES_DIR, "kith.ico"))
    ? path.join(RES_DIR, "kith.ico")
    : path.join(APP_ROOT, "web", "kith.ico");
  win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 980,
    minHeight: 620,
    title: "Kith",
    backgroundColor: "#F7F8FA",
    icon: iconPath,
    autoHideMenuBar: true,
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, spellcheck: false },
  });
  win.setMenuBarVisibility(false);
  win.once("ready-to-show", () => win.show());
  win.on("page-title-updated", e => e.preventDefault());

  const wc = win.webContents;
  wc.on("did-finish-load", () => { loaded = true; log("did-finish-load"); });
  wc.on("did-fail-load", (e, code, desc, url) => {
    log(`did-fail-load ${code} ${desc} ${url}`);
    if (!quitting && code !== -3) {
      setTimeout(() => {
        if (!quitting && win && !win.isDestroyed()) {
          log("重试 loadURL");
          win.loadURL(URL_BASE + "/").catch(() => { });
        }
      }, 800);
    }
  });
  wc.on("render-process-gone", (e, d) => log("render-process-gone " + JSON.stringify(d)));

  win.loadURL(URL_BASE + "/").catch(err => log("loadURL catch: " + err.message));
  win.on("closed", () => { win = null; });
}

app.whenReady().then(() => {
  log("app ready, pid=" + process.pid);
  const started = startServer();
  waitServer(started ? 60 : 1, ok => {
    log("waitServer ok=" + ok);
    createWindow();
  });
});

app.on("window-all-closed", () => {
  quitting = true;
  killServer();
  app.quit();
});
app.on("before-quit", () => { quitting = true; killServer(); });
process.on("exit", killServer);
