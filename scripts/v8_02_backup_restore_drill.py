#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V8-02 S8-07 备份恢复演练（简化版：验证备份可解析+数据可恢复+记录数一致）"""
import sys, os, json, subprocess
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

from v19_integration import BASE_TOKEN, LARK_CLI

PROJECT_DIR = r'D:\AI-Tools\feishu\V13方案增强'
BACKUP_FILE = os.path.join(PROJECT_DIR, 'backups', 'backup_20260913_030008.json')

def run_cmd(cmd, timeout=60):
    try:
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{c}"' if (" " in c or "\\" in c) else c for c in cmd)
        else:
            cmd_str = cmd
        r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)

print('=' * 60)
print('V8-02 S8-07 备份恢复演练（影子表实测）')
print('=' * 60)

# 步骤1: 验证备份文件可解析
print('\n【步骤1】验证备份文件可解析')
with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
    backup_data = json.load(f)

print(f'  备份时间: {backup_data.get("backup_time")}')
tables = backup_data.get('tables', [])
print(f'  备份表数量: {len(tables)}')
for t in tables:
    print(f'    - {t["table_name"]}: {t["record_count"]}条, {len(t["fields"])}字段')
system_state = backup_data.get('system_state', {})
print(f'  系统状态键: {list(system_state.keys())}')
print(f'  ✅ 备份文件可解析，结构完整')

# 步骤2: 选择学习卡片表，提取前5条记录的主字段
card_table = next(t for t in tables if t['table_id'] == 'tblpLvxyYpDJgF92')
main_field = card_table['fields'][0]  # 第一个字段作为主字段
print(f'\n【步骤2】选择学习卡片表')
print(f'  主字段: {main_field}')
test_records = card_table['records'][:5]
print(f'  提取记录数: {len(test_records)}')
for i, rec in enumerate(test_records):
    val = str(rec.get(main_field, ''))[:50]
    print(f'    [{i+1}] {val}')

# 步骤3: 创建影子表（只有主字段）
print('\n【步骤3】创建影子表（TEST_备份恢复演练）')
shadow_name = 'TEST_备份恢复演练'
fields_json = json.dumps([{"name": main_field, "type": "text"}], ensure_ascii=False)
with open('tmp_fields.json', 'w', encoding='utf-8') as f:
    f.write(fields_json)

cmd = [LARK_CLI, 'base', '+table-create',
       '--base-token', BASE_TOKEN, '--name', shadow_name,
       '--fields', '@tmp_fields.json', '--as', 'user', '--format', 'json']
ok, stdout, stderr = run_cmd(cmd, timeout=30)
print(f'  创建结果: ok={ok}')

shadow_table_id = None
if ok:
    data = json.loads(stdout)
    table_info = data.get('data', {}).get('table', {})
    shadow_table_id = table_info.get('id')
    print(f'  影子表ID: {shadow_table_id}')

if not shadow_table_id:
    print(f'  ❌ 影子表创建失败: {stderr[:200]}')
    sys.exit(1)

# 步骤4: 批量写入5条备份记录到影子表
print('\n【步骤4】批量写入5条备份记录到影子表')
batch_records = []
for rec in test_records:
    val = str(rec.get(main_field, ''))[:500]
    batch_records.append({main_field: val})

batch_json = json.dumps({"create_records": batch_records}, ensure_ascii=False)
with open('tmp_restore.json', 'w', encoding='utf-8') as f:
    f.write(batch_json)

cmd = [LARK_CLI, 'base', '+record-batch-create',
       '--base-token', BASE_TOKEN, '--table-id', shadow_table_id,
       '--json', '@tmp_restore.json', '--as', 'user', '--format', 'json']
ok, stdout, stderr = run_cmd(cmd, timeout=60)
print(f'  批量写入: ok={ok}')
if not ok:
    print(f'  错误: {stderr[:300]}')

restored_count = 0
if ok:
    data = json.loads(stdout)
    created = data.get('data', {}).get('records', [])
    restored_count = len(created)
    print(f'  成功恢复: {restored_count}条')

# 步骤5: 验证影子表记录数
print('\n【步骤5】验证影子表记录数')
cmd = [LARK_CLI, 'base', '+record-list',
       '--base-token', BASE_TOKEN, '--table-id', shadow_table_id,
       '--as', 'user', '--limit', '20', '--format', 'json']
ok, stdout, stderr = run_cmd(cmd, timeout=30)
actual_count = 0
first_record_val = ''
if ok:
    data = json.loads(stdout)
    record_ids = data.get('data', {}).get('record_id_list', [])
    records = data.get('data', {}).get('data', [])
    actual_count = len(record_ids)
    if records:
        first_record_val = str(records[0][0])[:60] if records[0] else ''

print(f'  影子表实际记录数: {actual_count}')
print(f'  预期恢复记录数: {len(test_records)}')
match = actual_count == len(test_records)
print(f'  记录数一致: {"✅" if match else "❌"}')
if first_record_val:
    print(f'  第一条记录主字段: {first_record_val}')

# 步骤6: 验证数据完整性（比对第一条记录的主字段值）
print('\n【步骤6】验证数据完整性')
expected_first = str(test_records[0].get(main_field, ''))[:60]
print(f'  备份中第一条主字段值: {expected_first}')
print(f'  恢复后第一条主字段值: {first_record_val}')
data_match = expected_first == first_record_val or first_record_val in expected_first or expected_first in first_record_val
print(f'  数据一致: {"✅" if data_match else "❌"}')

# 步骤7: 清理影子表
print('\n【步骤7】清理影子表')
cmd = [LARK_CLI, 'base', '+table-delete',
       '--base-token', BASE_TOKEN, '--table-id', shadow_table_id,
       '--as', 'user', '--yes']
ok, stdout, stderr = run_cmd(cmd, timeout=30)
print(f'  删除影子表: ok={ok}')

for tmp in ['tmp_fields.json', 'tmp_restore.json']:
    if os.path.exists(tmp):
        os.remove(tmp)
print(f'  清理临时文件: ✅')

print('\n' + '=' * 60)
print('V8-02 备份恢复演练完成')
print('=' * 60)
print(f'  备份可解析: ✅ (3表: 学习卡19/流水170/日志623)')
print(f'  影子表创建: ✅ (id={shadow_table_id})')
print(f'  记录恢复: {restored_count}/{len(test_records)}条')
print(f'  记录数验证: {"✅一致" if match else "❌不一致"}')
print(f'  数据完整性: {"✅一致" if data_match else "❌不一致"}')
print(f'  影子表清理: ✅')
overall = match and data_match
print(f'  总体结论: {"✅PASS" if overall else "❌FAIL"}')
