#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查多维表格待办任务"""

import urllib.request
import json
from datetime import datetime

# 读取凭证
env_path = r'C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env'
app_id = ''
app_secret = ''
for line in open(env_path, encoding='utf-8-sig'):
    line = line.strip()
    if line.startswith('FEISHU_APP_ID='):
        app_id = line.split('=', 1)[1]
    elif line.startswith('FEISHU_APP_SECRET='):
        app_secret = line.split('=', 1)[1]

# 获取token
req = urllib.request.Request(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode(),
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(req, timeout=30) as r:
    token = json.load(r)['tenant_access_token']

BASE_TOKEN = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
TASK_TABLE = 'tblz3H4lV7PCrBrX'

# 获取所有任务
url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TASK_TABLE}/records?page_size=100'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=30) as r:
    resp = json.load(r)

records = resp['data']['items']
print(f'总任务数: {len(records)}')
print()

# 筛选待办任务
todo_tasks = []
for rec in records:
    fields = rec.get('fields', {})
    title = fields.get('任务名称', '')
    if isinstance(title, list):
        title = title[0].get('text', '') if title else ''
    
    status = fields.get('状态', '')
    if isinstance(status, list):
        status = status[0].get('text', '') if status else ''
    
    if status == '待办':
        todo_tasks.append(title)

print(f'待办任务: {len(todo_tasks)}个')
print()
print('待办任务列表:')
for i, task in enumerate(todo_tasks, 1):
    print(f'  {i}. {task}')
