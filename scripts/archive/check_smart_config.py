#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查smart-connections配置"""

import json

with open(r'D:\AI\finished Brain\.obsidian\plugins\smart-connections\data.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

print("当前配置：")
print(json.dumps(config, ensure_ascii=False, indent=2))
print()
print("检查：")
print(f"  base_url: {config.get('base_url', '')}")
print(f"  embedding_model: {config.get('embedding_model', '')}")
print(f"  api_key: {config.get('api_key', '')[:20]}...")
print()

# 判断是本地还是云端
if 'localhost' in config.get('base_url', ''):
    print("⚠️ 当前是本地Ollama配置！")
elif 'siliconflow' in config.get('base_url', ''):
    print("✅ 当前是硅基流动云端配置！")
else:
    print("❓ 未知配置")
