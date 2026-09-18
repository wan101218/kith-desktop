# -*- coding: utf-8 -*-
"""用 ctypes 调 IShellLinkW/IPersistFile 验证 .lnk 能否被 Windows 解析（不启动任何进程）。"""
import ctypes
import sys
from ctypes import HRESULT, POINTER, c_void_p, c_wchar_p, c_int, c_uint, byref
from ctypes import Structure, c_ushort, c_ulong

VTBL = {}


class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        h = s.strip("{}").replace("-", "")
        self.Data1 = int(h[0:8], 16)
        self.Data2 = int(h[8:12], 16)
        self.Data3 = int(h[12:16], 16)
        for i in range(8):
            self.Data4[i] = int(h[16 + i * 2:18 + i * 2], 16)


CLSID_ShellLink = GUID("{00021401-0000-0000-C000-000000000046}")
IID_IShellLinkW = GUID("{000214F9-0000-0000-C000-000000000046}")
IID_IPersistFile = GUID("{0000010B-0000-0000-C000-000000000046}")

ole32 = ctypes.oledll.ole32
ole32.CoInitialize(None)

unk = c_void_p()
hr = ole32.CoCreateInstance(byref(CLSID_ShellLink), None, 1, byref(IID_IShellLinkW), byref(unk))
assert hr == 0, f"CoCreateInstance failed 0x{hr:08x}"


def method(iface, index, restype, *argtypes):
    vt = ctypes.cast(ctypes.cast(iface, POINTER(c_void_p))[0], POINTER(c_void_p))
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(vt[index])


def qi(iface, iid):
    QueryInterface = method(iface, 0, HRESULT, POINTER(GUID), POINTER(c_void_p))
    out = c_void_p()
    hr = QueryInterface(iface, byref(iid), byref(out))
    return hr, out


# 1) IPersistFile::Load —— 与资源管理器读取 .lnk 相同的入口
hr_pf, pf = qi(unk, IID_IPersistFile)
assert hr_pf == 0, f"QI IPersistFile failed 0x{hr_pf:08x}"
Load = method(pf, 5, HRESULT, c_wchar_p, c_uint)
path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Desktop\Kith.lnk"
hr = Load(pf, path, 0x10)  # STGM_READ
print("Load:", "OK" if hr == 0 else f"FAILED 0x{hr:08x}")

# 2) 解析字段
GetPath = method(unk, 3, HRESULT, c_wchar_p, c_int, c_void_p, c_uint)
buf = ctypes.create_unicode_buffer(1024)
hr1 = GetPath(unk, buf, 1024, None, 0)
GetArguments = method(unk, 10, HRESULT, c_wchar_p, c_int)
buf2 = ctypes.create_unicode_buffer(1024)
hr2 = GetArguments(unk, buf2, 1024)
GetWorkingDirectory = method(unk, 8, HRESULT, c_wchar_p, c_int)
buf3 = ctypes.create_unicode_buffer(1024)
hr3 = GetWorkingDirectory(unk, buf3, 1024)
GetIconLocation = method(unk, 16, HRESULT, c_wchar_p, c_int, POINTER(c_int))
buf4 = ctypes.create_unicode_buffer(1024)
icon_idx = c_int()
hr4 = GetIconLocation(unk, buf4, 1024, byref(icon_idx))
GetShowCmd = method(unk, 14, HRESULT, POINTER(c_int))
show = c_int()
GetShowCmd(unk, byref(show))

if hr == 0:
    print("target :", buf.value if hr1 == 0 else f"(err 0x{hr1:08x})")
    print("args   :", buf2.value if hr2 == 0 else f"(err 0x{hr2:08x})")
    print("workdir:", buf3.value if hr3 == 0 else f"(err 0x{hr3:08x})")
    print("icon   :", buf4.value, "idx", icon_idx.value if hr4 == 0 else f"(err 0x{hr4:08x})")
    print("showcmd:", show.value)
else:
    sys.exit(1)
