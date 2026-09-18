# -*- coding: utf-8 -*-
"""GPU 模式矩阵测试：逐个配置启动 Kith.exe，截图判定页面是否真正渲染出来。"""
import os
import subprocess
import time
import urllib.request

import ctypes
import ctypes.wintypes as wt

ROOT = r"D:\PC Projects\Kith"
APP = ROOT + r"\app\Kith.exe"


def kill_all():
    subprocess.run(["taskkill", "/IM", "Kith.exe", "/F"], capture_output=True)
    for _ in range(20):
        txt = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True).stdout.decode("gbk", errors="replace")
        if "kith.exe" not in txt.lower():
            return
        time.sleep(0.5)


def wait_ping(timeout=12):
    dl = time.time() + timeout
    while time.time() < dl:
        try:
            with urllib.request.urlopen("http://127.0.0.1:19287/api/ping", timeout=1) as f:
                if b"KithDesktop" in f.read():
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def shot_classify():
    u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = u32.FindWindowW(None, "Kith")
    if not hwnd:
        return None, "no-window"
    u32.SetForegroundWindow(hwnd)
    time.sleep(1.2)
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    sdc = u32.GetDC(None)
    mem = g32.CreateCompatibleDC(sdc)
    bmp = g32.CreateCompatibleBitmap(sdc, w, h)
    g32.SelectObject(mem, bmp)
    g32.BitBlt(mem, 0, 0, w, h, sdc, r.left, r.top, 0x00CC0020)

    class BMIH(ctypes.Structure):
        _fields_ = [("sz", wt.DWORD), ("w", ctypes.c_long), ("h", ctypes.c_long),
                    ("planes", wt.WORD), ("bits", wt.WORD), ("comp", wt.DWORD),
                    ("szimg", wt.DWORD), ("xppm", ctypes.c_long), ("yppm", ctypes.c_long),
                    ("used", wt.DWORD), ("imp", wt.DWORD)]
    bi = BMIH(ctypes.sizeof(BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    from PIL import Image
    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    p = ROOT + rf"\tools\matrix_{MODE}.png"
    img.save(p)
    small = img.resize((80, 45))
    px = list(small.getdata())
    n = len(px)
    mean = tuple(sum(c[i] for c in px) / n for i in range(3))
    var = sum(sum((c[i] - mean[i]) ** 2 for i in range(3)) for c in px) / n
    amber = sum(1 for c in px if c[0] > 180 and 120 < c[1] < 210 and c[2] < 120)
    dark = sum(1 for c in px if sum(c) < 200)
    return p, f"var={var:.0f} amber={amber} dark={dark} (var高+amber>0 = 渲染成功)"


def tail(p, n=6):
    try:
        return open(p, encoding="utf-8", errors="replace").read().strip().splitlines()[-n:]
    except OSError:
        return ["(no log)"]


for MODE in ["d", "c", "b", "a"]:
    print(f"\n===== MODE {MODE} =====")
    kill_all()
    with open(ROOT + r"\data\gpu-mode.txt", "w") as f:
        f.write(MODE)
    try:
        os.remove(ROOT + r"\data\electron.log")
    except OSError:
        pass
    subprocess.Popen([APP], cwd=ROOT,
                     env={k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"},
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    ping = wait_ping()
    time.sleep(7)  # 渲染余量
    alive = "kith.exe" in subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True).stdout.decode("gbk", errors="replace").lower()
    p, info = shot_classify()
    print("ping:", ping, "| alive:", alive)
    print("shot:", info)
    for l in tail(ROOT + r"\data\electron.log"):
        print("  |", l)
kill_all()
print("\ndone")
