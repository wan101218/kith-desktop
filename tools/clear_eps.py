# -*- coding: utf-8 -*-
"""清理测试接入点 + 完整验证『选择器内添加接入点 → 选模型』前端流程后的服务端状态。"""
import json
import urllib.request

BASE = "http://127.0.0.1:19287"


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())


if __name__ == "__main__":
    st = get("/api/settings")
    for e in st.get("endpoints", []):
        print("delete", e["vendor"], e["id"])
        print(post("/api/endpoints/delete", {"id": e["id"]}))
    st = get("/api/settings")
    print("endpoints now:", st["endpoints"])
