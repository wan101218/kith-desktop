# -*- coding: utf-8 -*-
"""Kith Desktop 启动器（pythonw 运行，无控制台窗口）。

职责：
  1. 起本地服务（默认端口 19287，被占用时自动向后找）；服务已在跑则直接复用；
  2. 用 Edge/Chrome 的 --app 模式打开一个无地址栏的独立桌面窗口；
  3. 常驻后台，让手机同步页随时可用（关掉窗口不影响服务；
     在「设置 → 服务」里点退出才是真正停止）。
"""
import os
import socket
import sys
import threading
import time
import urllib.request
import winreg

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(APP_ROOT, "server"))

DEFAULT_PORT = 19287


def ping(port, timeout=0.6):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=timeout) as r:
            import json
            d = json.loads(r.read().decode("utf-8"))
            return d.get("app") == "KithDesktop"
    except Exception:
        return False


def pick_port():
    env = os.environ.get("KITH_PORT")
    start = int(env) if env and env.isdigit() else DEFAULT_PORT
    for p in range(start, start + 20):
        if ping(p):
            return p, True  # 已有实例
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", p))
                return p, False
            except OSError:
                continue
    return start, False


def find_browser():
    """Edge / Chrome 的 --app 模式窗口。"""
    cands = []
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe")
        cands.append(winreg.QueryValueEx(k, None)[0])
    except OSError:
        pass
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        cands.append(winreg.QueryValueEx(k, None)[0])
    except OSError:
        pass
    cands += [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def open_window(port):
    url = f"http://127.0.0.1:{port}/"
    exe = find_browser()
    try:
        if exe:
            import subprocess
            subprocess.Popen([exe, f"--app={url}", "--window-size=1440,920"], close_fds=True)
            return True
        os.startfile(url)  # 退回默认浏览器
        return True
    except Exception:
        return False


def main():
    port, already = pick_port()
    if not already:
        import server.main as app  # noqa: E402
        t = threading.Thread(target=app.serve, args=(port,), daemon=True)
        t.start()
        for _ in range(60):
            if ping(port, 0.4):
                break
            time.sleep(0.1)
    open_window(port)
    # 常驻：服务线程是 daemon，这里用主线程睡觉维持进程
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
