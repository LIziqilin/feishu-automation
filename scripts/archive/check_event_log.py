#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查系统事件日志表，找第三个测试/create_task"""
import urllib.request, json

env_path = r'C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env'
app_id=app_secret=''
for line in open(env_path, encoding='utf-8-sig'):
    line=line.strip()
    if line.startswith('FEISHU_APP_ID='): app_id=line.split('=',1)[1]
    elif line.startswith('FEISHU_APP_SECRET='): app_secret=line.split('=',1)[1]

req=urllib.request.Request('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=json.dumps({'app_id':app_id,'app_secret':app_secret}).encode(),
    headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=30) as r:
    token=json.load(r)['tenant_access_token']

BASE='X8N1bvN3na99dFsyu0gcU8zTnHf'
LOG_TABLE='tblPreh1ipB9LQpf'

all_items=[]
page_token=None
for _ in range(20):
    url=f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{LOG_TABLE}/records?page_size=100'
    if page_token: url+=f'&page_token={page_token}'
    req=urllib.request.Request(url, headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=30) as r:
        d=json.load(r)
    data=d.get('data',{})
    all_items.extend(data.get('items',[]))
    if data.get('has_more'):
        page_token=data.get('page_token')
    else:
        break

print(f"系统事件日志共{len(all_items)}条")
print()
print("=== 含'第三'或'create'或'新建任务'的日志 ===")
def txt(v):
    if isinstance(v,list):
        return ' '.join([x.get('text','') if isinstance(x,dict) else str(x) for x in v])
    return str(v)

for it in all_items:
    f=it.get('fields',{})
    blob=' '.join(txt(v) for v in f.values())
    if '第三' in blob or 'create_task' in blob.lower() or '新建任务' in blob:
        # 打印时间和各字段
        t=f.get('时间') or f.get('event_time') or ''
        etype=txt(f.get('事件类型',f.get('event_type','')))
        msg=txt(f.get('消息',f.get('message',f.get('详情',''))))
        print(f"[{t}] {etype}: {msg[:100]}")
