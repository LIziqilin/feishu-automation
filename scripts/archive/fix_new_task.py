#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修改learning_system.py，增加新建任务指令识别"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到_looks_like_instruction方法中的return False行，在它之前插入新代码
found = False
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    # 找到 "return False" 那一行，在它之前插入
    if 'return False' in line and i > 0 and '暂停' in lines[i-2]:
        # 插入新建任务识别
        indent = '        '
        new_lines.append(indent + '# 新建任务指令\n')
        new_lines.append(indent + 'if text.startswith("新建任务：") or text.startswith("新建任务:"):\n')
        new_lines.append(indent + '    return True\n')
        new_lines.append(indent + '# 记录任务指令\n')
        new_lines.append(indent + 'if text.startswith("记录任务：") or text.startswith("记录任务:"):\n')
        new_lines.append(indent + '    return True\n')
        found = True
        print(f'在第{i+1}行附近插入新建任务识别代码')

if found:
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('✅ 修改成功！已增加新建任务指令识别')
else:
    print('❌ 未找到插入位置')
