#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复_looks_like_instruction方法，把新建任务判断移到return False之前"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到有问题的代码
old_code = '''        if re.match(r'^暂停\\s*\\d*\\s*(天|日)?$', text):
            return True
        return False
        # 新建任务指令
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            return True
        # 记录任务指令
        if text.startswith("记录任务：") or text.startswith("记录任务:"):
            return True'''

new_code = '''        if re.match(r'^暂停\\s*\\d*\\s*(天|日)?$', text):
            return True
        # 新建任务指令
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            return True
        # 记录任务指令
        if text.startswith("记录任务：") or text.startswith("记录任务:"):
            return True
        return False'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 已修复_looks_like_instruction方法')
else:
    print('❌ 未找到目标代码')
    # 打印一下附近的代码
    lines = content.split('\\n')
    for i, line in enumerate(lines):
        if 'return False' in line and i > 1000 and i < 1100:
            print(f'第{i+1}行: {line}')
