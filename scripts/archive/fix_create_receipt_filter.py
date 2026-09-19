# -*- coding: utf-8 -*-
"""加固：把创建任务相关系统回执加入过滤列表"""
with open('learning_system.py','r',encoding='utf-8') as f:
    content=f.read()

old='''            # V15根因修复：批量回执也是系统消息，不要当成用户指令
            "✓ 会", "❓ 会",
        ]'''
new='''            # V15根因修复：批量回执也是系统消息，不要当成用户指令
            "✓ 会", "❓ 会",
            # V15根因修复：创建/完成/归档任务的系统回执，防止被当成新指令重复处理
            "✅ 已创建任务", "❌ 创建失败", "✅ 待办已创建", "❌ 待办创建失败",
        ]'''

if old in content:
    content=content.replace(old,new)
    with open('learning_system.py','w',encoding='utf-8') as f:
        f.write(content)
    print("✅ 已把创建任务相关回执加入系统过滤列表")
else:
    print("⚠️ 未找到目标代码，可能已修改过")
    # 检查是否已经加过
    if '✅ 已创建任务' in content:
        print("   确认：已存在'✅ 已创建任务'过滤，无需重复修改")
