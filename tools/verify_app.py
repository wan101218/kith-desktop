# -*- coding: utf-8 -*-
"""Kith.exe 启动自校验：清理残留 → 分离启动 → 等待就绪 → 收集窗口与日志证据。"""
import ctypes
import os
import subprocess
import sys
import time
import urllib.request

APP = r"D:\PC Projects\Kith\app\Kith.exe"
ROOT = r"D:\PC Projects\Kith"


def kill_stale():
    """结束旧的 Kith.exe 与占 19287 的 python 进程（仅限本应用相关）。"""
    import ctypes.wintypes as wt

    # 枚举窗口找 Kith
    hwnds = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(h, buf, 256)
        if buf.value == "Kith":
            hwnds.append(h)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    for h in hwnds:
        ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(1.5)
    # 通过 taskkill 精确按映像名结束（仅 Kith.exe）
    subprocess.run(["taskkill", "/IM", "Kith.exe", "/F"], capture_output=True)
    time.sleep(1.0)
    # 占 19287 的 python：用 netstat 找 pid
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if ":19287" in line and "LISTENING" in line:
                pid = line.rsplit(None, 1)[-1]
                name = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
                if "python" in name.lower():
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                    print("killed stale python pid", pid)
    except Exception as e:
        print("stale check:", e)


def wait_ping(timeout=25):
    dl = time.time() + timeout
    while time.time() < dl:
        try:
            with urllib.request.urlopen("http://127.0.0.1:19287/api/ping", timeout=1) as r:
                if b"KithDesktop" in r.read():
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def window_shot():
    import ctypes.wintypes as wt
    u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = u32.FindWindowW(None, "Kith")
    if not hwnd:
        return None, "no window"
    u32.ShowWindow(hwnd, 9)
    u32.SetForegroundWindow(hwnd)
    time.sleep(1.5)
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
    p = os.path.join(ROOT, "tools", "shot_kithexe_final.png")
    img.save(p)
    px = list(img.resize((64, 36)).getdata())
    nonblack = sum(1 for q in px if sum(q) > 90)
    return p, f"window {w}x{h}, nonblack={nonblack/len(px):.2f}"


if __name__ == "__main__":
    kill_stale()
    for f in ("electron.log", "server.log"):
        try:
            os.remove(os.path.join(ROOT, "data", f))
        except OSError:
            pass
    subprocess.Popen([APP], cwd=ROOT, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    print("launched, waiting...")
    ok = wait_ping()
    print("ping:", ok)
    time.sleep(4)  # 给页面渲染留时间
    p, info = window_shot()
    print("shot:", info)
    for f in ("electron.log", "server.log"):
        fp = os.path.join(ROOT, "data", f)
        if os.path.exists(fp):
            print(f"--- {f} ---")
            print(open(fp, encoding="utf-8", errors="replace").read()[:1500])
