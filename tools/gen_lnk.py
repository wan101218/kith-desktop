# -*- coding: utf-8 -*-
"""纯 Python 生成 .lnk 快捷方式（MS-SHLLINK 最小实现，无需 COM）。

目标：pythonw.exe + 参数 launcher.pyw，带图标、工作目录。
"""
import struct

CLSID = bytes.fromhex("0114020000000000c000000000000046")  # Shell Link


def u16(s):
    b = s.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<H", len(b) // 2) + b


def string_data(strings):
    out = b""
    for s in strings:
        out += u16(s)
    return out


def link_info(local_base_path):
    label = b"KITHDATA\x00"
    # VolumeID（对照微软官方 .lnk）：Size(4) + DriveType(4) + Serial(4) + LabelOffset(4) + label
    # Size = 16 + len(label)；LabelOffset = 0x10（紧跟 16 字节头）
    volume = struct.pack("<IIII", 16 + len(label), 3, 0x1234ABCD, 0x10) + label
    # LinkInfo header: size, HeaderSize=0x1C, Flags=1(VolumeIDAndLocalBasePath),
    # VolumeIDOffset=0x1C, LocalBasePathOffset, CommonNetOffset=0, CommonSuffixOffset
    base = local_base_path.encode("mbcs") + b"\x00"
    suffix = b"\x00"
    hdr_size = 0x1C
    vol_off = hdr_size
    lbp_off = vol_off + len(volume)
    net_off = 0
    suf_off = lbp_off + len(base)
    size = suf_off + len(suffix)
    info = struct.pack("<IIIIIII", size, hdr_size, 0x1, vol_off, lbp_off, net_off, suf_off)
    return info + volume + base + suffix


def make_idlist(target):
    """用 SHParseDisplayName 生成合法的绝对 ITEMIDLIST 字节串。"""
    import ctypes
    from ctypes import byref, c_void_p
    pidl = c_void_p()
    hr = ctypes.oledll.shell32.SHParseDisplayName(target, None, byref(pidl), 0, None)
    if hr != 0:
        return b""
    out = b""
    p = pidl.value
    while True:
        cb = ctypes.c_ushort.from_address(p).value
        if cb == 0:
            out += b"\x00\x00"  # 终止项本身占 2 字节
            break
        out += ctypes.string_at(p, cb)
        p += cb
    ctypes.oledll.ole32.CoTaskMemFree(pidl)
    return out


def make_lnk(target, args="", workdir="", icon=""):
    idlist = make_idlist(target)
    flags = 0x2 | 0x8 | 0x10 | 0x20 | 0x40 | 0x80  # LinkInfo + RelPath + WorkDir + Args + Icon + Unicode
    if idlist:
        flags |= 0x1  # HasLinkTargetIDList
    header = struct.pack("<I", 0x4C) + CLSID + struct.pack(
        "<II", flags, 0x80) + b"\x00" * 24 + struct.pack(
        "<IIIHHII", 0, 0, 1, 0, 0, 0, 0)
    body = b""
    if idlist:
        body += struct.pack("<H", len(idlist)) + idlist
    body += link_info(target)
    body += string_data(["pythonw.exe", workdir, args, icon])
    return header + body + b"\x00" * 4


if __name__ == "__main__":
    import os
    data = make_lnk(
        target=r"D:\PC Projects\Kith\app\Kith.exe",
        args="",
        workdir=r"D:\PC Projects\Kith",
        icon=r"D:\PC Projects\Kith\web\kith.ico",
    )
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    out = os.path.join(desktop, "Kith.lnk")
    with open(out, "wb") as f:
        f.write(data)
    print("written:", out, len(data), "bytes, exists:", os.path.exists(out))
