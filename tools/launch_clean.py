# -*- coding: utf-8 -*-
"""清场后全新启动 Kith.exe 并收集证据。"""
import subprocess
import time
import urllib.request

ROOT = r"D:\PC Projects\Kith"


def run(cmd):
    return subprocess.run(cmd, capture_output=True)


def main():
    run(["taskkill", "/IM", "Kith.exe", "/F"])
    run(["taskkill", "/IM", "pythonw.exe", "/F"])
    run(["taskkill", "/IM", "python.exe", "/F"])  # 仅测试期清场；正常运行不会有裸 python 常驻
    time.sleep(1.5)

    txt = run(["tasklist", "/FO", "CSV"]).stdout.decode("gbk", errors="replace")
    left = [l for l in txt.splitlines() if "kith" in l.lower() or "python" in l.lower()]
    print("remaining procs:", left or "none")

    subprocess.Popen([ROOT + r"\app\Kith.exe"], cwd=ROOT,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
    print("launched fresh")
    ok = False
    for i in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:19287/api/ping", timeout=1) as f:
                if b"KithDesktop" in f.read():
                    print(f"ping OK after {i * 0.5:.1f}s")
                    ok = True
                    break
        except Exception:
            pass
        time.sleep(0.5)
    if not ok:
        print("PING FAILED")
    time.sleep(6)

    txt = run(["tasklist", "/FO", "CSV"]).stdout.decode("gbk", errors="replace")
    n = sum(1 for l in txt.splitlines() if "kith.exe" in l.lower())
    print("kith.exe process count:", n)

    for f in ("electron.log", "server.log"):
        try:
            with open(ROOT + "\\data\\" + f, encoding="utf-8", errors="replace") as fh:
                print(f"--- {f} ---")
                print(fh.read()[:1200])
        except OSError as e:
            print(f"--- {f}: {e}")


if __name__ == "__main__":
    main()
