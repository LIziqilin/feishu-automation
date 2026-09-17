#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1-3: 知识缺口分析"""

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
CARD_TABLE = 'tblpLvxyYpDJgF92'

# 获取所有学习卡片
url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{CARD_TABLE}/records?page_size=100'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(req, timeout=30) as r:
    resp = json.load(r)

cards = resp['data']['items']
print(f'总卡片数: {len(cards)}')
print()

# 分析标签分布
tag_count = {}
for card in cards:
    fields = card.get('fields', {})
    tags = fields.get('标签', '')
    if isinstance(tags, list):
        for tag in tags:
            tag_name = tag.get('text', '') if isinstance(tag, dict) else str(tag)
            tag_count[tag_name] = tag_count.get(tag_name, 0) + 1

print('标签分布:')
for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True):
    print(f'  {tag}: {count}张')
print()

# 分析知识缺口
print('🔍 知识缺口分析:')
print()

# 假设核心领域应该有至少5张卡片
core_domains = ['机电工程', '学习方法', '认知思维', '酒店管理', '项目管理']
gaps = []
for domain in core_domains:
    count = tag_count.get(domain, 0)
    if count < 5:
        gaps.append((domain, count, 5 - count))
        print(f'  ⚠️ {domain}: 只有{count}张，还差{5-count}张')
    else:
        print(f'  ✅ {domain}: {count}张，已覆盖')

print()
print('💡 学习建议:')
if gaps:
    print('  优先补充以下领域的卡片:')
    for domain, current, need in gaps:
        print(f'    - {domain} (还需{need}张)')
else:
    print('  核心领域已覆盖，可以开始深化学习')

# 生成知识缺口报告
report = f"""🔍 知识缺口分析报告 ({datetime.now().strftime('%Y-%m-%d')})

总卡片数: {len(cards)}张

📊 标签分布:
"""
for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True):
    report += f'  {tag}: {count}张\n'

report += '\n⚠️ 知识缺口:\n'
for domain, current, need in gaps:
    report += f'  {domain}: {current}张 (还需{need}张)\n'

report += '\n💡 建议:\n'
report += '  1. 优先补充缺口领域的卡片\n'
report += '  2. 每个核心领域至少5张卡片\n'
report += '  3. 建立知识体系，而不是散点学习\n'

print()
print(report)

# 保存报告
with open('knowledge_gap_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)
print('✅ 报告已保存到 knowledge_gap_report.txt')
