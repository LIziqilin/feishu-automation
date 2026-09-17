#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P1-2: 掌握度统计与趋势分析"""

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

# 统计掌握度分布（状态枚举 + 数值字段掌握度M 双口径）
def _cell_text(v):
    if v is None: return ''
    if isinstance(v, str): return v
    if isinstance(v, list):
        return ''.join(x.get('text','') if isinstance(x,dict) else str(x) for x in v)
    if isinstance(v, dict): return v.get('text','')
    return str(v)
def _cell_num(v, default=0):
    try:
        if v is None or v=='' : return default
        return float(v)
    except: return default

status_count = {}
m_sum = 0.0
m_cnt = 0
for card in cards:
    fields = card.get('fields', {})
    status = fields.get('卡片状态', '')
    if isinstance(status, list):
        status = status[0].get('text', '') if status else '未知'
    status_count[status] = status_count.get(status, 0) + 1
    m = _cell_num(fields.get('掌握度M'))
    m_sum += m; m_cnt += 1

print('掌握度分布:')
for status, count in sorted(status_count.items()):
    print(f'  {status}: {count}张')
print()

# 计算掌握率（双口径：枚举MASTERED + 数值掌握度M均值）
total = len(cards)
mastered = status_count.get('MASTERED', 0)
learning = status_count.get('LEARNING', 0)
reviewing = status_count.get('REVIEWING', 0)
new = status_count.get('NEW', 0)
# 数值口径：掌握度M>=3.5 视为已掌握（与USER.md口径一致）
m_rate = (m_sum / m_cnt) if m_cnt > 0 else 0
mastered_by_m = sum(1 for c in cards if _cell_num(c.get('fields',{}).get('掌握度M')) >= 3.5)
mastery_rate = (mastered_by_m / total * 100) if total > 0 else 0
print(f'掌握率(数值掌握度M口径, >=3.5算掌握): {mastery_rate:.1f}% ({mastered_by_m}/{total})')
print(f'平均掌握度M: {m_rate:.2f}')
print(f'状态枚举 MASTERED={mastered} 学习中={learning} 复习中={reviewing} 新卡片={new}')
print()

# 生成掌握度报告
report = f"""📊 学习掌握度报告 ({datetime.now().strftime('%Y-%m-%d')})

总卡片数: {total}张
掌握率(数值口径,掌握度M>=3.5): {mastery_rate:.1f}%
平均掌握度M: {m_rate:.2f}

📈 状态枚举分布:
  ✅ 已掌握(MASTERED): {mastered}张
  📚 学习中(LEARNING): {learning}张
  🔄 复习中(REVIEWING): {reviewing}张
  🆕 新卡片(NEW): {new}张
  （未匹配枚举/未知状态已纳入数值口径统计）

💡 建议:
  - 优先复习REVIEWING/掌握度M<3.5的卡片
  - 保持每天学习1张新卡片
  - 定期回顾已掌握卡片，防止遗忘
"""

print(report)

# 保存报告到文件
with open('mastery_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)
print('✅ 报告已保存到 mastery_report.txt')
