#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手动补录群里的两个待办任务"""

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
today_ms = int(datetime.now().timestamp() * 1000)

# 要创建的两个任务
tasks_to_create = [
    '创建任务：测试任务 456789',
    '新建任务：落实消防验收结果12345',
]

for task_name in tasks_to_create:
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TASK_TABLE}/records'
    body = {
        'fields': {
            '任务名称': task_name,
            '状态': '待办',
            '优先级': '中',
            '类别': '工作',
            '截止日期': today_ms
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.load(r)
    
    if resp.get('code') == 0:
        print(f'✅ 已创建: {task_name}')
    else:
        print(f'❌ 创建失败: {task_name} - {resp}')

print()
print('✅ 补录完成！')
