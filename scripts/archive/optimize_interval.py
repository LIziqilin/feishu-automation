#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""优化个性化间隔重复算法"""

with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_get_interval = '''def get_interval(result):
    """根据答题结果获取间隔天数（简化版）"""
    if result == "会":
        return 2
    elif result == "模糊":
        return 1
    else:
        return 1'''

new_get_interval = '''def get_interval(result, consecutive_correct=0):
    """根据答题结果和连续正确次数获取间隔天数（V15增强：个性化间隔）
    
    间隔策略：
    - 不会：1天
    - 模糊：1天
    - 会（根据连续正确次数递增）：
      * 0次：2天
      * 1次：3天
      * 2次：5天
      * 3次：7天
      * 4次：15天
      * 5次+：30天
    """
    if result == "不会":
        return 1
    elif result == "模糊":
        return 1
    else:  # "会"
        # V15增强：根据连续正确次数调整间隔
        if consecutive_correct == 0:
            return 2
        elif consecutive_correct == 1:
            return 3
        elif consecutive_correct == 2:
            return 5
        elif consecutive_correct == 3:
            return 7
        elif consecutive_correct == 4:
            return 15
        else:
            return 30'''

content = content.replace(old_get_interval, new_get_interval)

with open('learning_system.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ 个性化间隔重复已优化：')
print('   - 会：根据连续正确次数递增（2→3→5→7→15→30天）')
print('   - 模糊：1天')
print('   - 不会：1天')
