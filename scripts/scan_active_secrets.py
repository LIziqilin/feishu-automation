# -*- coding: utf-8 -*-
"""scan_active_secrets.py — 扫描任务计划引用的活跃生产脚本是否仍硬编码密钥"""
import re, os

PATHS = [
    r'D:\AI\AI大系统\01-脚本\prompt_tune.py', r'D:\AI\AI大系统\01-脚本\skill_incubate.py',
    r'D:\AI\AI大系统\01-脚本\review_reminder.py', r'D:\AI\AI大系统\01-脚本\cost_audit.py',
    r'D:\AI\AI大系统\01-脚本\daily_briefing.py', r'D:\AI\AI大系统\01-脚本\weekly_report.py',
    r'D:\AI\AI大系统\01-脚本\backup_all.py', r'D:\AI\AI大系统\01-脚本\daily_report.py',
    r'D:\AI\AI大系统\01-脚本\daily_reminder.py', r'D:\AI\AI大系统\01-脚本\monthly_report.py',
    r'D:\AI\AI大系统\01-脚本\health_check.py', r'D:\AI\AI大系统\01-脚本\chat_sort.py',
    r'D:\AI\AI大系统\01-脚本\cognitive_analysis.py',
    r'D:\AI-Tools\feishu\飞书的高阶用法\优化实施\scripts\cost_sync_to_feishu.py',
    r'D:\AI-Tools\feishu\飞书的高阶用法\优化实施\scripts\preference_sync_to_feishu.py',
    r'D:\AI\Hermes修复\daily_selfcheck.py',
]
RX = re.compile(r'APP_SECRET\s*[:=]\s*["\']|app_secret\s*[:=]\s*["\']')

for p in PATHS:
    if not os.path.exists(p):
        print('[不存在] %s' % p)
        continue
    txt = open(p, encoding='utf-8', errors='ignore').read()
    if RX.search(txt):
        print('[硬编码!] %s' % p)
    else:
        print('[OK] %s' % p)
