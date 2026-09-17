#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新备份脚本的表列表"""

with open('backup_with_rotation.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''TABLES_TO_BACKUP = [
    ("学习卡片表", "tblpLvxyYpDJgF92"),
    ("复习流水表", "tblbznzCSpPhSz93"),
    ("系统事件日志表", "tblPreh1ipB9LQpf"),
]'''

new = '''TABLES_TO_BACKUP = [
    ("学习卡片表", "tblpLvxyYpDJgF92"),
    ("复习流水表", "tblbznzCSpPhSz93"),
    ("系统事件日志表", "tblPreh1ipB9LQpf"),
    ("任务总表", "tblz3H4lV7PCrBrX"),
    ("洞察笔记表", "tblaqKBl87V9C0q1"),
    ("用户画像表", "tbldjGffbuPKCe21"),
    ("心跳表", "tblJmm0ZIgqlYmyt"),
    ("系统健康表", "tblxJMndPNtZ7XyG"),
]'''

content = content.replace(old, new)
with open('backup_with_rotation.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 备份表列表已更新，从3张表扩展到8张表')
