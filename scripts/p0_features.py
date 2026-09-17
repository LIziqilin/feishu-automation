#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P0功能集成：每日三件事 + 艾森豪威尔矩阵 + 费曼学习法"""

import urllib.request
import json
from datetime import datetime

# 读取飞书凭证
env_path = r'C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env'
app_id = ''
app_secret = ''
for line in open(env_path, encoding='utf-8-sig'):
    line = line.strip()
    if line.startswith('FEISHU_APP_ID='):
        app_id = line.split('=', 1)[1]
    elif line.startswith('FEISHU_APP_SECRET='):
        app_secret = line.split('=', 1)[1]

# 配置
BASE_TOKEN = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
TASK_TABLE = 'tblz3H4lV7PCrBrX'
CHAT_ID = 'oc_1fe154e172ab04622b7ffa810ac172bc'

def get_token():
    """获取飞书访问令牌"""
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        data=json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['tenant_access_token']

def get_todo_tasks():
    """获取待办任务"""
    token = get_token()
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TASK_TABLE}/records?page_size=100'
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.load(r)
    
    tasks = []
    for rec in resp['data']['items']:
        fields = rec.get('fields', {})
        title = fields.get('任务名称', '')
        if isinstance(title, list):
            title = title[0].get('text', '') if title else ''
        
        status = fields.get('状态', '')
        if isinstance(status, list):
            status = status[0].get('text', '') if status else ''
        
        priority = fields.get('优先级', '')
        if isinstance(priority, list):
            priority = priority[0].get('text', '') if priority else ''
        
        if status == '待办':
            tasks.append({
                'title': title,
                'priority': priority,
                'record_id': rec.get('record_id')
            })
    
    return tasks

def get_top3_tasks(tasks):
    """选出今日三件事（按优先级）"""
    priority_order = {'高': 3, '中': 2, '低': 1}
    sorted_tasks = sorted(tasks, key=lambda x: priority_order.get(x['priority'], 0), reverse=True)
    return sorted_tasks[:3]

def get_eisenhower_matrix(tasks):
    """艾森豪威尔矩阵分类"""
    urgent_important = []  # 重要紧急
    not_urgent_important = []  # 重要不紧急
    urgent_not_important = []  # 紧急不重要
    not_urgent_not_important = []  # 不重要不紧急
    
    for task in tasks:
        priority = task['priority']
        # 简化：高优先级=重要，中/低=不重要
        # 紧急程度：高优先级默认紧急
        if priority == '高':
            urgent_important.append(task)
        elif priority == '中':
            not_urgent_important.append(task)
        else:
            not_urgent_not_important.append(task)
    
    return {
        'urgent_important': urgent_important,
        'not_urgent_important': not_urgent_important,
        'urgent_not_important': urgent_not_important,
        'not_urgent_not_important': not_urgent_not_important
    }

def generate_enhanced_morning_report():
    """生成增强版早报（集成三个P0功能）"""
    today = datetime.now().strftime('%Y-%m-%d %A')
    report = f"📅 早报 | {today}\n\n"
    
    # 1. 每日三件事
    tasks = get_todo_tasks()
    top3 = get_top3_tasks(tasks)
    report += "🎯 今日三件事:\n"
    if top3:
        for i, task in enumerate(top3, 1):
            report += f"  {i}. [{task['priority']}] {task['title']}\n"
    else:
        report += "  暂无待办任务\n"
    report += "\n"
    
    # 2. 艾森豪威尔矩阵
    matrix = get_eisenhower_matrix(tasks)
    report += "📊 任务优先级矩阵:\n"
    report += f"  🔴 重要紧急: {len(matrix['urgent_important'])}个\n"
    report += f"  🟡 重要不紧急: {len(matrix['not_urgent_important'])}个\n"
    report += f"  🟢 紧急不重要: {len(matrix['urgent_not_important'])}个\n"
    report += f"  ⚪ 不重要不紧急: {len(matrix['not_urgent_not_important'])}个\n"
    report += "\n"
    
    # 3. 费曼学习法提示
    report += "🧠 费曼学习法提示:\n"
    report += "  学习完一个知识点后，试着用自己的话讲出来\n"
    report += "  讲不清楚的地方，就是你没真正理解的地方\n"
    report += "  记住：能教会别人，才是真的学会了\n"
    report += "\n"
    
    # 4. 其他
    report += f"📝 待办任务总数: {len(tasks)}个\n"
    report += "💪 新的一天，加油！"
    
    return report

if __name__ == '__main__':
    report = generate_enhanced_morning_report()
    print(report)
