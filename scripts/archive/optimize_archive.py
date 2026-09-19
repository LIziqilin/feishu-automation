#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""优化自动归档功能"""

with open('task_insight_extension.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 优化归档指令解析，增加别名
old_parse_archive = '''def parse_archive_command(text):
    """解析「归档 xxx」或「归档：xxx」指令"""
    match = re.match(r'^归档[：:]\\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^归档\\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    return None'''

new_parse_archive = '''def parse_archive_command(text):
    """解析「归档 xxx」或「归档：xxx」指令（V15增强：增加别名）"""
    # 主指令：归档
    match = re.match(r'^归档[：:]\\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^归档\\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    # V15增强：增加别名
    aliases = ['archive', '收起来', '存档']
    for alias in aliases:
        match = re.match(r'^' + alias + r'[：:]\\s*(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.match(r'^' + alias + r'\\s+(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None'''

content = content.replace(old_parse_archive, new_parse_archive)

with open('task_insight_extension.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 自动归档功能已优化：')
print('   - 增加别名：archive/收起来/存档')
