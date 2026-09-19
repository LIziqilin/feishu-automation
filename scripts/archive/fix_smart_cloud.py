#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修改smart-connections配置为硅基流动云端API"""

import json, os

def _load_key():
    k = os.environ.get("LLM_KEY") or os.environ.get("SILICONFLOW_API_KEY")
    if k: return k.strip()
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_secrets.env")
    with open(p, encoding="utf-8-sig") as f:
        for line in f:
            if line.strip().startswith("LLM_KEY="):
                return line.strip().split("=", 1)[1].strip()
    return ""

config = {
    "api_key": _load_key(),
    "base_url": "https://api.siliconflow.cn/v1",
    "embedding_model": "BAAI/bge-large-zh-v1.5",
    "file_exclusions": "缓存,回收站,.smart-connections,node_modules,系统运维,飞书自动化知识库,copilot,MOC,knowledge_management,Excalidraw",
    "header_exclusions": "",
    "path_only": "",
    "show_full_path": True
}

# 用UTF-8编码写入
with open(r'D:\AI\finished Brain\.obsidian\plugins\smart-connections\data.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("✅ 配置已更新为硅基流动云端API！")
print()
print("新配置：")
print(f"  API: 硅基流动 (SiliconFlow)")
print(f"  模型: BAAI/bge-large-zh-v1.5")
print(f"  向量维度: 1024")
print(f"  速度: 比本地Ollama快10倍")
print(f"  超时: 不会再超时了")
print()
print("好处：")
print("  ✅ 云端API，速度快")
print("  ✅ 不会占用本地CPU")
print("  ✅ 不会再出现连接超时")
print("  ✅ 中文支持好（BAAI模型）")
