# -*- coding: utf-8 -*-
"""重启 Kith.exe（杀净旧树 → 干净环境启动 → 验证窗口与渲染）。"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time
import urllib.request

ROOT = r"D:\PC Projects\Kith"


def main():
    subprocess.run(["taskkill", "/IM", "Kith.exe", "/T", "/F"], capture_output=True)
    # 不能按映像名杀 python.exe —— 会连脚本自己一起杀；只精准清理占用 19287 的孤儿
    txt = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True).stdout.decode("gbk", errors="replace")
    for line in txt.splitlines():
        if ":19287" in line and "LISTENING" in line:
            pid = line.rsplit(None, 1)[-1]
            if pid != str(os.getpid()):
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
                print("killed stale listener", pid)
    time.sleep(2.5)
    txt = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True).stdout.decode("gbk", errors="replace")
    left = [l.split(",")[0] for l in txt.splitlines() if "kith" in l.lower() or "python.exe" in l.lower()]
    print("left:", left or "none")

    env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    subprocess.Popen([ROOT + r"\app\Kith.exe"], cwd=ROOT, env=env,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
    ok = False
    for i in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:19287/api/ping", timeout=1) as f:
                if b"KithDesktop" in f.read():
                    print(f"ping OK @ {i * 0.5:.1f}s")
                    ok = True
                    break
        except Exception:
            pass
        time.sleep(0.5)
    print("server:", ok)
    time.sleep(8)

    u32 = ctypes.windll.user32
    hwnd = u32.FindWindowW(None, "Kith")
    print("window:", bool(hwnd))
    if not hwnd:
        return
    g32 = ctypes.windll.gdi32
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
    img.save(ROOT + r"\tools\final_drag_fix.png")
    px = list(img.resize((80, 45)).getdata())
    print("amber:", sum(1 for c in px if c[0] > 180 and 120 < c[1] < 210 and c[2] < 120))


if __name__ == "__main__":
    main()
