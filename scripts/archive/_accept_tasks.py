# -*- coding: utf-8 -*-
"""验收2：任务/提醒/洞察解析器 + 复测3条"""
import sys, os
sys.path.insert(0, r"D:\AI-Tools\feishu\V13方案增强\scripts")
os.chdir(r"D:\AI-Tools\feishu\V13方案增强\scripts")

import task_insight_extension as tie

print("="*60)
print("任务/提醒/洞察 识别验收")
print("="*60)
cases = [
    ("提醒我1分钟后 测试", tie.is_remind_command, True),
    ("提醒我明天下午3点开会", tie.is_remind_command, True),
    ("提醒 1小时后复习", tie.is_remind_command, True),
    ("提醒", tie.is_remind_command, False),  # 无内容应不触发
    ("洞察：以后办事要按流向排查", tie.is_insight_command, True),
    ("写洞察：xxx", tie.is_insight_command, True),
    ("记录洞察：xxx", tie.is_insight_command, True),
]
fail = 0
for txt, fn, expect in cases:
    try:
        got = bool(fn(txt))
        ok = (got == expect)
        if not ok: fail += 1
        print(f"[{'OK' if ok else 'FAIL'}] 期望={expect} 实际={got} | {txt[:30]}")
    except Exception as e:
        fail += 1
        print(f"[ERR] {txt[:30]} -> {e}")

# 复测3条
import v15_command_router as rtr
def fake_run(script, timeout=180): return True, "[mock]"
rtr._run_sub = fake_run
print("-"*60)
print("复测3条（无冒号）:")
for c in ["生成学习周报","更新用户画像","系统健康诊断"]:
    h,r = rtr.handle_v15_command(c)
    print(f"[{'OK' if h else 'FAIL'}] {c} -> {str(r)[:30]}")
    if not h: fail += 1
print("-"*60)
print(f"失败数: {fail}")
