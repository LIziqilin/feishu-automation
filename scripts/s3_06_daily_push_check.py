#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3-06 每日推送验证"""
import sys
import json
import subprocess
import os
import re

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S3-06 每日推送验证 ═══')
print()

# 检查DailyPusher代码实现
print('【1 DailyPusher代码实现检查】')
script_path = r'D:\AI-Tools\feishu\V13方案增强\scripts\v19_integration.py'
if os.path.exists(script_path):
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查DailyPusher类
    if 'class DailyPusher' in content:
        match = re.search(r'class DailyPusher', content)
        if match:
            line_num = content[:match.start()].count('\n') + 1
            print(f'  DailyPusher类: 存在（第{line_num}行）')
        
        # 检查关键方法
        methods = ['send_morning_report', 'send_noon_report', 'send_evening_report', 'push_report']
        for method in methods:
            if method in content:
                match = re.search(rf'def {method}\(', content)
                if match:
                    line_num = content[:match.start()].count('\n') + 1
                    print(f'  {method}: 存在（第{line_num}行）')
            else:
                print(f'  {method}: 不存在 ❌')
        
        # 检查推送时间配置
        time_patterns = [r'07:30', r'7:30', r'12:00', r'21:00', r'9:00']
        for pattern in time_patterns:
            if re.search(pattern, content):
                print(f'  时间配置 {pattern}: 存在')
    else:
        print(f'  DailyPusher类: 不存在 ❌')
else:
    print(f'  v19_integration.py: 文件不存在')
print()

# 检查Windows任务计划
print('【2 Windows任务计划检查】')
tasks_to_check = [
    ('V16_MorningReport', '早报'),
    ('V13_NoonDigest', '午报'),
    ('Hermes_Local_EveningReview', '晚报'),
    ('V13_MorningBrief', '早报(备用)'),
    ('V13_WeeklyReport', '周报'),
]

for task_name, desc in tasks_to_check:
    cmd = ['schtasks', '/query', '/tn', task_name, '/fo', 'LIST', '/v']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if proc.returncode == 0:
        # 解析状态
        status_match = re.search(r'Status:\s*(\S+)', proc.stdout)
        status = status_match.group(1) if status_match else 'UNKNOWN'
        
        # 解析下次运行时间
        next_run_match = re.search(r'Next Run Time:\s*(.+)', proc.stdout)
        next_run = next_run_match.group(1).strip() if next_run_match else 'UNKNOWN'
        
        # 解析任务运行命令
        task_to_run_match = re.search(r'Task To Run:\s*(.+)', proc.stdout)
        task_to_run = task_to_run_match.group(1).strip() if task_to_run_match else 'UNKNOWN'
        
        print(f'  {task_name} ({desc}):')
        print(f'    状态: {status}')
        print(f'    下次运行: {next_run}')
        print(f'    运行命令: {task_to_run[:100]}...' if len(task_to_run) > 100 else f'    运行命令: {task_to_run}')
    else:
        print(f'  {task_name} ({desc}): 任务不存在或查询失败')
print()

# 检查最近推送记录（从群消息中查找）
print('【3 最近推送记录检查】')
# 检查系统事件日志表中的推送记录
cmd = ['lark-cli', 'base', '+record-list',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblPreh1ipB9LQpf',
       '--limit', '20',
       '--as', 'user', '--format', 'json']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
if proc.returncode == 0:
    resp = json.loads(proc.stdout)
    data = resp.get("data", {})
    records = data.get("data", [])
    fields = data.get("fields", [])
    
    # 查找推送相关记录
    push_records = []
    for rec in records:
        record = {}
        for i, field in enumerate(fields):
            record[field] = rec[i] if i < len(rec) else None
        
        # 检查是否包含推送关键词
        log_type = record.get('log_type', '')
        if isinstance(log_type, list):
            log_type = log_type[0] if log_type else ''
        content_str = str(record.get('content', '')) + str(record.get('message', ''))
        
        if any(kw in str(log_type) + content_str for kw in ['推送', '早报', '午报', '晚报', 'push', 'report', 'daily']):
            push_records.append(record)
    
    print(f'  系统事件日志中推送相关记录数: {len(push_records)}')
    for rec in push_records[:5]:
        log_type = rec.get('log_type', '')
        if isinstance(log_type, list):
            log_type = log_type[0] if log_type else ''
        content = str(rec.get('content', rec.get('message', '')))[:100]
        timestamp = rec.get('timestamp', rec.get('创建时间', ''))
        print(f'    类型: {log_type}, 时间: {timestamp}, 内容: {content}')
else:
    print(f'  查询系统事件日志失败: {proc.stderr}')
print()

# 尝试触发一次推送（发送测试消息验证推送功能）
print('【4 推送功能验证（发送测试消息）】')
test_msg = '【V32验证】每日推送功能测试 - 这是一条测试消息，用于验证推送通道是否正常。'
cmd = ['lark-cli', 'im', '+messages-send',
       '--chat-id', 'oc_1fe154e172ab04622b7ffa810ac172bc',
       '--text', test_msg,
       '--as', 'user']
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
if proc.returncode == 0:
    print(f'  测试消息发送成功')
    # 解析返回的message_id
    try:
        resp = json.loads(proc.stdout)
        msg_id = resp.get('data', {}).get('message_id', 'UNKNOWN')
        print(f'  message_id: {msg_id}')
    except:
        print(f'  返回: {proc.stdout[:200]}')
else:
    print(f'  测试消息发送失败: {proc.stderr}')
print()

print('═══ 验证完成 ═══')
