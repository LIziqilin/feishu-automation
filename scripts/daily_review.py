#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每日学习复盘功能"""

import urllib.request
import json
from datetime import datetime, timedelta

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

# 1. 统计今日答题流水
print("📊 今日学习复盘")
print(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
print()

# 读复习流水表
FLOW_TABLE = 'tblbznzCSpPhSz93'
url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{FLOW_TABLE}/records?page_size=200'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=30) as r:
    resp = json.load(r)

flows = resp['data']['items']
today = datetime.now().strftime('%Y-%m-%d')

today_flows = []
for flow in flows:
    fields = flow.get('fields', {})
    event_time = fields.get('event_time', '')
    if today in str(event_time):
        today_flows.append(flow)

print(f"今日答题次数: {len(today_flows)}次")

# 统计正确率
correct = sum(1 for f in today_flows if f.get('fields', {}).get('结果') == ['会'])
total = len(today_flows)
accuracy = (correct / total * 100) if total > 0 else 0
print(f"今日正确率: {accuracy:.1f}% ({correct}/{total})")
print()

# 2. 统计学习卡片总数
CARD_TABLE = 'tblpLvxyYpDJgF92'
url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{CARD_TABLE}/records?page_size=100'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=30) as r:
    resp = json.load(r)

cards = resp['data']['items']
learning = sum(1 for c in cards if c.get('fields', {}).get('卡片状态') == ['LEARNING'])
not_started = sum(1 for c in cards if c.get('fields', {}).get('卡片状态') == ['NOT_STARTED'])
mastered = sum(1 for c in cards if c.get('fields', {}).get('卡片状态') == ['MASTERED'])

print(f"学习卡片总数: {len(cards)}张")
print(f"  📚 学习中: {learning}张")
print(f"  🆕 未开始: {not_started}张")
print(f"  ✅ 已掌握: {mastered}张")
print()

# 3. 生成复盘报告
print("💡 今日学习建议:")
if accuracy >= 80:
    print("  👍 正确率很高，可以学新卡片了！")
elif accuracy >= 60:
    print("  👍 正确率不错，继续保持！")
else:
    print("  📚 今天错的有点多，建议复习一下错题")

if total < 5:
    print("  📝 今天答题有点少，建议多复习几张卡片")

print()
print("✅ 每日学习复盘完成！")
