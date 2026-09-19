#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""彻底修复：把创建任务：也加到指令识别里"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修改 _looks_like_instruction 方法
old_looks = '''        # 新建任务指令
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            return True
        # 记录任务指令
        if text.startswith("记录任务：") or text.startswith("记录任务:"):
            return True
        return False'''

new_looks = '''        # 新建任务指令（支持多种说法）
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            return True
        if text.startswith("创建任务：") or text.startswith("创建任务:"):
            return True
        if text.startswith("记录任务：") or text.startswith("记录任务:"):
            return True
        if text.startswith("新增任务：") or text.startswith("新增任务:"):
            return True
        return False'''

if old_looks in content:
    content = content.replace(old_looks, new_looks)
    print("✅ _looks_like_instruction 已更新")
else:
    print("⚠️ 未找到_looks_like_instruction目标代码")

# 2. 修改 parse 方法
old_parse = '''        # 新建任务指令
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            task_name = text.split("：", 1)[-1].split(":", 1)[-1].strip()
            if task_name:
                return "create_task", {"task_name": task_name}'''

new_parse = '''        # 新建任务指令（支持多种说法）
        for prefix in ["新建任务：", "新建任务:", "创建任务：", "创建任务:", "记录任务：", "记录任务:", "新增任务：", "新增任务:"]:
            if text.startswith(prefix):
                task_name = text[len(prefix):].strip()
                if task_name:
                    return "create_task", {"task_name": task_name}'''

if old_parse in content:
    content = content.replace(old_parse, new_parse)
    print("✅ parse 方法已更新")
else:
    print("⚠️ 未找到parse目标代码")

# 写回文件
with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)

print()
print("✅ 修复完成！现在支持以下指令：")
print("  - 新建任务：xxx")
print("  - 创建任务：xxx")
print("  - 记录任务：xxx")
print("  - 新增任务：xxx")
