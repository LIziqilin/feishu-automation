#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在parse方法里增加新建任务处理逻辑"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到parse方法里的暂停指令处理，在它之后增加新建任务处理
old_code = '''        # 暂停
        pause_match = re.match(r'^暂停\\s*(\\d+)?\\s*(天|日)?$', text)
        if pause_match:
            days = int(pause_match.group(1)) if pause_match.group(1) else 2
            return "pause", {"days": days}'''

new_code = '''        # 暂停
        pause_match = re.match(r'^暂停\\s*(\\d+)?\\s*(天|日)?$', text)
        if pause_match:
            days = int(pause_match.group(1)) if pause_match.group(1) else 2
            return "pause", {"days": days}

        # 新建任务指令
        if text.startswith("新建任务：") or text.startswith("新建任务:"):
            task_name = text.split("：", 1)[-1].split(":", 1)[-1].strip()
            if task_name:
                return "create_task", {"task_name": task_name}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 已在parse方法里增加新建任务处理逻辑')
else:
    print('❌ 未找到目标代码')
    # 打印一下附近的代码看看
    lines = content.split('\\n')
    for i, line in enumerate(lines):
        if 'pause_match' in line:
            print(f'第{i+1}行: {line}')
