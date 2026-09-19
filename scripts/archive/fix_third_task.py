# -*- coding: utf-8 -*-
"""补建第三个测试 + 清理带前缀脏数据"""
import urllib.request, json
from datetime import datetime

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
TASK='tblz3H4lV7PCrBrX'
today_ms=int(datetime.now().timestamp()*1000)
H={'Authorization':'Bearer '+token,'Content-Type':'application/json'}

# 1. 补建"第三个测试"
print("=== 1. 补建任务：第三个测试 ===")
body={'fields':{'任务名称':'第三个测试','状态':'待办','优先级':'中','类别':'工作','截止日期':today_ms}}
req=urllib.request.Request(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{TASK}/records',
    data=json.dumps(body).encode(), headers=H, method='POST')
try:
    with urllib.request.urlopen(req,timeout=30) as r:
        resp=json.load(r)
    if resp.get('code')==0:
        rid=resp.get('data',{}).get('record',{}).get('record_id','')
        print(f"  ✅ 补建成功: 第三个测试 record_id={rid}")
    else:
        print(f"  ❌ 补建失败: {resp}")
except Exception as e:
    print(f"  ❌ 异常: {e}")

# 2. 删除4条带前缀脏数据
print()
print("=== 2. 清理带前缀的重复脏数据 ===")
dirty = {
    'recvvfJUG1nMg5': '创建任务：测试任务 123',
    'recvvg1DsywYcf': '创建任务：测试任务 456789',
    'recvvg1EroLb5p': '新建任务：落实消防验收结果12345',
    'recvvgmRGRRF2P': '创建任务：另一个测试',
}
for rid, name in dirty.items():
    req=urllib.request.Request(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{TASK}/records/{rid}',
        headers=H, method='DELETE')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            resp=json.load(r)
        if resp.get('code')==0:
            print(f"  ✅ 已删除脏数据: {name}")
        else:
            print(f"  ❌ 删除失败 {name}: {resp.get('msg')}")
    except Exception as e:
        print(f"  ❌ 异常 {name}: {e}")

print()
print("=== 完成 ===")
