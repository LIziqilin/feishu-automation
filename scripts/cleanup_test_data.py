#!/usr/bin/env python
"""清理测试数据：删除TEST_C2_CROSSDAY和TEST_UPGRADE测试卡及流水"""
import sys, os, json, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"

CARD_TABLE = "tblpLvxyYpDJgF92"
FLOW_TABLE = "tblbznzCSpPhSz93"

def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        return False, "", str(e)

def get_records(table_id):
    """获取表记录"""
from v19_integration import BASE_TOKEN
    cmd = [LARK_CLI, "base", "+record-list",
           "--base-token", BASE_TOKEN, "--table-id", table_id,
           "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, stderr = run_cmd(cmd, timeout=60)
    if not ok:
        return [], []
    try:
        data = json.loads(stdout)
        fields = data["data"]["fields"]
        rows = data["data"]["data"]
        record_ids = data["data"].get("record_id_list", [])
        return fields, list(zip(rows, record_ids))
    except:
        return [], []

def delete_record(table_id, record_id):
    """删除记录"""
    cmd = [LARK_CLI, "base", "+record-delete",
           "--base-token", BASE_TOKEN, "--table-id", table_id,
           "--record-id", record_id, "--as", "user", "--yes"]
    ok, stdout, stderr = run_cmd(cmd, timeout=30)
    return ok

print("=" * 60)
print("清理测试数据")
print("=" * 60)

# 1. 清理流水表中的TEST记录
print("\n【1】清理流水表中的TEST记录")
fields, records = get_records(FLOW_TABLE)
test_flow_count = 0
deleted_flow_count = 0
if fields and "卡片ID" in fields:
    for row, record_id in records:
        card_id = row[fields.index("卡片ID")]
        if "TEST" in str(card_id):
            test_flow_count += 1
            print(f"  发现TEST流水: {card_id}, record_id={record_id}")
            if delete_record(FLOW_TABLE, record_id):
                deleted_flow_count += 1
                print(f"    ✅ 已删除")
            else:
                print(f"    ❌ 删除失败")
print(f"  共发现{test_flow_count}条TEST流水，删除{deleted_flow_count}条")

# 2. 清理学习卡表中的TEST记录
print("\n【2】清理学习卡表中的TEST记录")
fields, records = get_records(CARD_TABLE)
test_card_count = 0
deleted_card_count = 0
if fields and "卡片ID" in fields:
    for row, record_id in records:
        card_id = row[fields.index("卡片ID")]
        if "TEST" in str(card_id):
            test_card_count += 1
            print(f"  发现TEST卡片: {card_id}, record_id={record_id}")
            if delete_record(CARD_TABLE, record_id):
                deleted_card_count += 1
                print(f"    ✅ 已删除")
            else:
                print(f"    ❌ 删除失败")
print(f"  共发现{test_card_count}张TEST卡片，删除{deleted_card_count}张")

# 3. 验证清理结果
print("\n【3】验证清理结果")
fields, records = get_records(FLOW_TABLE)
remaining_test = 0
if fields and "卡片ID" in fields:
    for row, record_id in records:
        card_id = row[fields.index("卡片ID")]
        if "TEST" in str(card_id):
            remaining_test += 1
print(f"  流水表剩余TEST记录: {remaining_test}条")

fields, records = get_records(CARD_TABLE)
remaining_test_cards = 0
if fields and "卡片ID" in fields:
    for row, record_id in records:
        card_id = row[fields.index("卡片ID")]
        if "TEST" in str(card_id):
            remaining_test_cards += 1
print(f"  学习卡表剩余TEST记录: {remaining_test_cards}张")

print("\n" + "=" * 60)
print("清理完成")
print("=" * 60)
print(f"  删除TEST流水: {deleted_flow_count}条")
print(f"  删除TEST卡片: {deleted_card_count}张")
print(f"  剩余TEST流水: {remaining_test}条")
print(f"  剩余TEST卡片: {remaining_test_cards}张")
