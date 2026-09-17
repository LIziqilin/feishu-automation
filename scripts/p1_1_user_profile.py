#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1-1: 用户画像表初始化（修正字段名）"""

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
TABLE_ID = 'tbldjGffbuPKCe21'

# 写入初始数据（按实际字段名）
now_ms = int(datetime.now().timestamp() * 1000)
records = [
    {'fields': {'画像维度': '学习高峰时段', '画像值': '待分析', '更新时间': now_ms, '数据来源': '自动分析', '置信度': 0.5}},
    {'fields': {'画像维度': '薄弱科目', '画像值': '待分析', '更新时间': now_ms, '数据来源': '自动分析', '置信度': 0.5}},
    {'fields': {'画像维度': '工作效率时段', '画像值': '待分析', '更新时间': now_ms, '数据来源': '自动分析', '置信度': 0.5}},
    {'fields': {'画像维度': '兴趣领域', '画像值': '待分析', '更新时间': now_ms, '数据来源': '自动分析', '置信度': 0.5}},
    {'fields': {'画像维度': '交互偏好', '画像值': '直接给结论，不要废话', '更新时间': now_ms, '数据来源': '用户输入', '置信度': 0.9}},
]

url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records/batch_create'
body = {'records': records}
req = urllib.request.Request(
    url,
    data=json.dumps(body).encode(),
    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req, timeout=30) as r:
    resp = json.load(r)

if resp.get('code') == 0:
    print(f'✅ 初始数据写入成功: {len(records)}条')
else:
    print(f'❌ 写入失败: {resp}')
