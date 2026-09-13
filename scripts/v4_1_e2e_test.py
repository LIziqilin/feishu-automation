#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V4-1 DLQ重试端到端验证脚本"""
import sys, os, json, time
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

import subprocess
from v19_integration import DLQManager, BASE_TOKEN, FLOW_TABLE, LARK_CLI

def get_recent_flows(limit=5):
    """获取最近的流水记录"""
    cmd = [LARK_CLI, 'base', '+record-list',
           '--base-token', BASE_TOKEN, '--table-id', FLOW_TABLE,
           '--as', 'user', '--limit', str(limit), '--format', 'json']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(r.stdout)
    record_ids = data.get('data', {}).get('record_id_list', [])
    fields = data.get('data', {}).get('fields', [])
    records = data.get('data', {}).get('data', [])
    result = []
    for i, rid in enumerate(record_ids):
        rec = records[i] if i < len(records) else []
        item = {'record_id': rid}
        for j, f in enumerate(fields):
            if j < len(rec):
                item[f] = rec[j]
        result.append(item)
    return result

print('=' * 60)
print('V4-1 DLQ重试端到端验证')
print('=' * 60)

# 步骤1: 记录重试前流水表最近记录
print('\n【步骤1】记录重试前流水表最近5条记录')
before_flows = get_recent_flows(5)
before_ids = [f['record_id'] for f in before_flows]
for i, f in enumerate(before_flows):
    card_id = str(f.get('卡片ID', ''))[:20]
    result = str(f.get('结果', ''))[:20]
    source = str(f.get('来源', ''))[:20]
    print(f'  [{i+1}] {f["record_id"]} | card={card_id} | result={result} | source={source}')

# 步骤2: 添加一条测试消息到DLQ
print('\n【步骤2】添加测试消息到DLQ')
test_msg_id = f'TEST_V41_{int(time.time())}'
test_msg_text = '会'
DLQManager.add_failed_message(
    message_id=test_msg_id,
    message_text=test_msg_text,
    error_type='test_circuit_open',
    error_detail='V4-1端到端验证测试消息'
)
print(f'  测试消息已添加: message_id={test_msg_id}')

# 验证DLQ中有这条pending消息
dlq = json.load(open('.dlq_queue.json', 'r', encoding='utf-8'))
test_msg = next((m for m in dlq['messages'] if m['message_id'] == test_msg_id), None)
if test_msg:
    print(f'  验证: DLQ中存在该消息, status={test_msg["status"]}, retry_count={test_msg["retry_count"]}')
else:
    print('  验证失败: DLQ中未找到该消息')
    sys.exit(1)

# 步骤3: 触发重试
print('\n【步骤3】触发DLQ重试')
result = DLQManager.retry_pending(max_retries=3, max_messages=10)
print(f'  重试结果: retried={result["retried"]}, success={result["success"]}, failed={result["failed"]}, dead={result["dead"]}')
for r in result.get('results', []):
    if r['message_id'] == test_msg_id:
        print(f'  测试消息: success={r["success"]}, action={r["action"]}, error={r.get("error")}')

# 步骤4: 检查流水表是否新增记录
print('\n【步骤4】检查流水表是否新增记录')
time.sleep(2)  # 等待写入完成
after_flows = get_recent_flows(5)
after_ids = [f['record_id'] for f in after_flows]
new_ids = [rid for rid in after_ids if rid not in before_ids]
print(f'  重试前最近记录ID: {before_ids[:3]}...')
print(f'  重试后最近记录ID: {after_ids[:3]}...')
print(f'  新增记录数: {len(new_ids)}')

if new_ids:
    for rid in new_ids:
        f = next((x for x in after_flows if x['record_id'] == rid), None)
        if f:
            card_id = str(f.get('卡片ID', ''))[:20]
            result_val = str(f.get('结果', ''))[:20]
            source = str(f.get('来源', ''))[:20]
            print(f'  新增记录: {rid} | card={card_id} | result={result_val} | source={source}')
            # 验证来源是DLQ重试
            if 'DLQ重试' in source:
                print('  ✅ 验证: 新增记录来源为"DLQ重试"，确认是真实写入而非只改状态')
            else:
                print(f'  ⚠️  注意: 新增记录来源为"{source}"，不是"DLQ重试"')
else:
    print('  ❌ 验证失败: 流水表未新增记录')

# 步骤5: 检查DLQ状态是否更新为success
print('\n【步骤5】检查DLQ状态是否更新为success')
dlq = json.load(open('.dlq_queue.json', 'r', encoding='utf-8'))
test_msg = next((m for m in dlq['messages'] if m['message_id'] == test_msg_id), None)
if test_msg:
    print(f'  测试消息状态: status={test_msg["status"]}, retry_count={test_msg["retry_count"]}')
    if test_msg['status'] == 'success':
        print('  ✅ 验证: DLQ状态已更新为success')
    else:
        print(f'  ❌ 验证失败: DLQ状态为{test_msg["status"]}，不是success')
else:
    print('  ❌ 验证失败: DLQ中未找到测试消息')

# 步骤6: 反证 - 重复触发重试，不得产生重复记录（幂等）
print('\n【步骤6】反证: 重复触发重试，验证幂等性')
before_retry_ids = [f['record_id'] for f in get_recent_flows(10)]
result2 = DLQManager.retry_pending(max_retries=3, max_messages=10)
print(f'  第二次重试结果: retried={result2["retried"]}, success={result2["success"]}')
time.sleep(2)
after_retry_ids = [f['record_id'] for f in get_recent_flows(10)]
duplicate_new = [rid for rid in after_retry_ids if rid not in before_retry_ids]
print(f'  第二次重试后新增记录数: {len(duplicate_new)}')
if len(duplicate_new) == 0:
    print('  ✅ 反证通过: 重复触发未产生重复记录（已成功消息不会被重试）')
else:
    print(f'  ❌ 反证失败: 重复触发产生了{len(duplicate_new)}条重复记录')

# 步骤7: 清理测试数据
print('\n【步骤7】清理测试数据')
# 从DLQ中删除测试消息
dlq = json.load(open('.dlq_queue.json', 'r', encoding='utf-8'))
dlq['messages'] = [m for m in dlq['messages'] if m['message_id'] != test_msg_id]
with open('.dlq_queue.json', 'w', encoding='utf-8') as f:
    json.dump(dlq, f, ensure_ascii=False, indent=2)
print(f'  已从DLQ中删除测试消息: {test_msg_id}')

# 注意: 流水表中的测试记录需要手动删除或标记，这里只记录ID
if new_ids:
    print(f'  流水表中的测试记录ID（需后续清理）: {new_ids}')

print('\n' + '=' * 60)
print('V4-1 DLQ重试端到端验证完成')
print('=' * 60)
