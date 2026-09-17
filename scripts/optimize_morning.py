#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""优化早报：增加每日三件事"""

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''                if task_msg_parts:
                    sender._send_message("\\n".join(task_msg_parts))
                    print("  [V39增强] 早报待办事项已推送")'''

new_code = '''                # V15增强：每日三件事（从今日待办中选出最重要的3件）
                try:
                    if tasks["today_pending"]:
                        top3 = tasks["today_pending"][:3]
                        three_things = "🎯 今日三件事（最重要）:\\n"
                        for i, t in enumerate(top3):
                            three_things += f"  {i+1}. {t['name']}\\n"
                        sender._send_message(three_things)
                        print("  [V15增强] 每日三件事已推送")
                except Exception as three_e:
                    print(f"  [WARN] 每日三件事异常: {three_e}")
                    
                if task_msg_parts:
                    sender._send_message("\\n".join(task_msg_parts))
                    print("  [V39增强] 早报待办事项已推送")'''

content = content.replace(old_code, new_code)
with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 早报已优化：增加每日三件事')
