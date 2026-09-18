"""打包前的资源装配：把前端、目录快照、冻结服务端复制进 installer/。

installer/ 仓库里只提交源码（main.js / package.json），体积大的二进制和
web/ 副本都由本脚本生成，避免仓库里堆构建产物。

用法：
    python tools/prepare_installer.py
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(ROOT, "installer")

# 来源 -> 安装器内目标路径
JOBS = [
    (os.path.join(ROOT, "build_install", "kith-server.exe"), os.path.join(INSTALLER, "kith-server.exe")),
    (os.path.join(ROOT, "web", "kith.ico"), os.path.join(INSTALLER, "kith.ico")),
    (os.path.join(ROOT, "web"), os.path.join(INSTALLER, "web")),
    (os.path.join(ROOT, "assets"), os.path.join(INSTALLER, "assets")),
    (os.path.join(ROOT, "server", "sync_page.html"), os.path.join(INSTALLER, "server", "sync_page.html")),
]


def main():
    missing = []
    for src, dst in JOBS:
        if not os.path.exists(src):
            missing.append(src)
            continue
        if os.path.isdir(src):
            # 逐文件覆盖而不是整目录删除：部分环境下 rmtree 会被回收站策略拦截
            for dirpath, _dirs, files in os.walk(src):
                rel = os.path.relpath(dirpath, src)
                target = dst if rel == "." else os.path.join(dst, rel)
                os.makedirs(target, exist_ok=True)
                for f in files:
                    shutil.copy2(os.path.join(dirpath, f), os.path.join(target, f))
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        print("ok  " + os.path.relpath(dst, ROOT))

    if missing:
        print("\n缺少以下输入（先执行 PyInstaller 冻结服务端）：", file=sys.stderr)
        for m in missing:
            print("  - " + m, file=sys.stderr)
        print("\n冻结命令：", file=sys.stderr)
        print("  pyinstaller --noconfirm --onefile --name kith-server \\", file=sys.stderr)
        print('    --paths server --distpath build_install --workpath build_tmp \\', file=sys.stderr)
        print('    --specpath build_tmp server/main.py \\', file=sys.stderr)
        print('    --add-data "<项目根>\\server\\sync_page.html;."', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
