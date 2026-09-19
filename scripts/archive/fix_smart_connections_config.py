#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复smart-connections配置文件中文乱码"""

import json

config = {
    "api_key": "ollama-local",
    "base_url": "http://localhost:11434/v1",
    "embedding_model": "nomic-embed-text",
    "file_exclusions": "缓存,回收站,.smart-connections,node_modules,系统运维,飞书自动化知识库",
    "header_exclusions": "",
    "path_only": "",
    "show_full_path": True
}

# 用UTF-8编码写入
with open(r'D:\AI\finished Brain\.obsidian\plugins\smart-connections\data.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("✅ 配置文件已修复（UTF-8编码）")

# 读取验证
with open(r'D:\AI\finished Brain\.obsidian\plugins\smart-connections\data.json', 'r', encoding='utf-8') as f:
    content = f.read()
print()
print("配置内容:")
print(content)
