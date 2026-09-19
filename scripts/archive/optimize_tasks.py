#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""优化自动销项和归档功能"""

with open('task_insight_extension.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 优化完成任务指令解析，增加更多别名
old_parse_complete = '''def parse_complete_command(text):
    """解析「完成 xxx」或「完成：xxx」指令"""
    match = re.match(r'^完成[：:]\\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^完成\\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    return None'''

new_parse_complete = '''def parse_complete_command(text):
    """解析「完成 xxx」或「完成：xxx」指令（V15增强：增加别名）"""
    # 主指令：完成
    match = re.match(r'^完成[：:]\\s*(.+)$', text)
    if match:
        return match.group(1).strip()
    match = re.match(r'^完成\\s+(.+)$', text)
    if match:
        return match.group(1).strip()
    # V15增强：增加别名
    aliases = ['销项', '搞定', 'done', '已完成']
    for alias in aliases:
        match = re.match(r'^' + alias + r'[：:]\\s*(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.match(r'^' + alias + r'\\s+(.+)$', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None'''

content = content.replace(old_parse_complete, new_parse_complete)

# 优化完成任务处理，增加完成率统计和归档建议
old_handle_complete = '''    if len(tasks) == 1:
        task = tasks[0]
        success, result = complete_task(task["record_id"])
        if success:
            msg = f"✅ 任务已完成\\n📋 {task['name']}\\n🕐 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            send_message(msg)
            return True, task["record_id"]'''

new_handle_complete = '''    if len(tasks) == 1:
        task = tasks[0]
        success, result = complete_task(task["record_id"])
        if success:
            # V15增强：完成率统计和归档建议
            msg = f"✅ 任务已完成\\n📋 {task['name']}\\n🕐 完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\\n\\n💡 小提示：\\n- 完成3天后可自动归档\\n- 回复「归档 {task['name'][:20]}」手动归档"
            send_message(msg)
            return True, task["record_id"]'''

content = content.replace(old_handle_complete, new_handle_complete)

with open('task_insight_extension.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 自动销项功能已优化：')
print('   - 增加别名：销项/搞定/done/已完成')
print('   - 完成后显示归档建议')
