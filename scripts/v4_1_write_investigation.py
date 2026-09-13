#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V4-1 DLQ重试写入真实性调查脚本"""
import sys, os, json, time, subprocess
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from v19_integration import DLQManager, BASE_TOKEN, FLOW_TABLE, LARK_CLI, SCRIPT_DIR

print('=' * 60)
print('V4-1 DLQ重试写入真实性调查')
print('=' * 60)

# 步骤1: 直接测试_write_flow_record方法
print('\n【步骤1】直接测试_write_flow_record方法')
test_msg_id = f'TEST_WRITE_{int(time.time())}'
flow_data = {
    "卡片ID": "recvtLY8poFzSQ",
    "卡片标题": "测试卡片",
    "结果": "会",
    "event_id": f"test|会|{int(time.time()*1000)}",
    "来源": ["DLQ重试测试"],
    "event_type": ["COMMIT"],
    "revision": 1,
    "superseded": False,
}

# 手动执行_write_flow_record的逻辑，查看详细输出
json_file = os.path.join(SCRIPT_DIR, f"dlq_retry_{test_msg_id}.json")
print(f'  临时文件路径: {json_file}')
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(flow_data, f, ensure_ascii=False)
print(f'  临时文件已创建，大小: {os.path.getsize(json_file)} bytes')

cmd = [LARK_CLI, "base", "+record-upsert",
       "--base-token", BASE_TOKEN,
       "--table-id", FLOW_TABLE,
       "--as", "user",
       "--json", f"@dlq_retry_{test_msg_id}.json"]
print(f'  执行命令: {" ".join(cmd)}')

r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
print(f'  退出码: {r.returncode}')
print(f'  stdout: {r.stdout[:500]}')
print(f'  stderr: {r.stderr[:500]}')

# 清理临时文件
if os.path.exists(json_file):
    os.remove(json_file)
    print(f'  临时文件已清理')

# 步骤2: 查询流水表中来源包含"DLQ"的记录
print('\n【步骤2】查询流水表中来源包含"DLQ"的记录')
cmd = [LARK_CLI, 'base', '+record-list',
       '--base-token', BASE_TOKEN, '--table-id', FLOW_TABLE,
       '--as', 'user', '--limit', '200', '--format', 'json']
r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=True)
data = json.loads(r.stdout)
fields = data.get('data', {}).get('fields', [])
records = data.get('data', {}).get('data', [])
record_ids = data.get('data', {}).get('record_id_list', [])

source_idx = None
for i, f in enumerate(fields):
    if f == '来源':
        source_idx = i
        break

print(f'  总记录数(当前页): {len(records)}')
print(f'  来源字段索引: {source_idx}')

dlq_records = []
for i, rec in enumerate(records):
    if source_idx is not None and source_idx < len(rec):
        source_val = str(rec[source_idx])
        if 'DLQ' in source_val or 'dlq' in source_val.lower():
            rid = record_ids[i] if i < len(record_ids) else 'unknown'
            dlq_records.append({'record_id': rid, 'source': source_val, 'index': i})

print(f'  来源包含DLQ的记录数: {len(dlq_records)}')
for r in dlq_records[:10]:
    print(f'    - {r["record_id"]} | source={r["source"]} | index={r["index"]}')

# 步骤3: 查询流水表最近10条记录的完整信息
print('\n【步骤3】查询流水表最近10条记录的完整信息')
cmd = [LARK_CLI, 'base', '+record-list',
       '--base-token', BASE_TOKEN, '--table-id', FLOW_TABLE,
       '--as', 'user', '--limit', '10', '--format', 'json']
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
data = json.loads(r.stdout)
fields = data.get('data', {}).get('fields', [])
records = data.get('data', {}).get('data', [])
record_ids = data.get('data', {}).get('record_id_list', [])

# 找关键字段索引
key_fields = {}
for i, f in enumerate(fields):
    if f in ['卡片ID', '结果', '来源', '客户端时间戳', '创建时间']:
        key_fields[f] = i

print(f'  关键字段索引: {key_fields}')
for i, rec in enumerate(records[:10]):
    rid = record_ids[i] if i < len(record_ids) else 'unknown'
    info = []
    for fname, idx in key_fields.items():
        if idx < len(rec):
            info.append(f'{fname}={str(rec[idx])[:30]}')
    print(f'  [{i+1}] {rid} | {" | ".join(info)}')

print('\n' + '=' * 60)
print('调查完成')
print('=' * 60)
