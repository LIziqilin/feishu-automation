#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试硅基流动embedding API"""

import urllib.request
import json

# P0-4: 禁止硬编码，改从 scripts/llm_secrets.env 读取
import os
def _load_key():
    k = os.environ.get("LLM_KEY") or os.environ.get("SILICONFLOW_API_KEY")
    if k: return k.strip()
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_secrets.env")
    with open(p, encoding="utf-8-sig") as f:
        for line in f:
            if line.strip().startswith("LLM_KEY="):
                return line.strip().split("=", 1)[1].strip()
    return ""
API_KEY = _load_key()
BASE_URL = "https://api.siliconflow.cn/v1"

# 测试embedding
url = f"{BASE_URL}/embeddings"
body = {
    "model": "BAAI/bge-small-zh-v1.5",
    "input": "测试中文embedding"
}

req = urllib.request.Request(
    url,
    data=json.dumps(body).encode(),
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.load(r)
        print("✅ 硅基流动API正常！")
        print(f"   模型: BAAI/bge-small-zh-v1.5")
        print(f"   向量维度: {len(resp['data'][0]['embedding'])}")
        print(f"   用量: {resp.get('usage', {})}")
except Exception as e:
    print(f"❌ API测试失败: {e}")
    # 试试其他模型
    print()
    print("试试另一个模型: BAAI/bge-large-zh-v1.5")
    body["model"] = "BAAI/bge-large-zh-v1.5"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.load(r)
            print("✅ 这个模型也可以！")
            print(f"   向量维度: {len(resp['data'][0]['embedding'])}")
    except Exception as e2:
        print(f"❌ 也失败: {e2}")
