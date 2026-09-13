#!/usr/bin/env python
"""
backup_with_rotation.py
7轮滚动备份：备份学习卡表、流水表、系统状态，保留最近7轮
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, os, time, shutil
from datetime import datetime


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")
MAX_BACKUPS = 7

TABLES_TO_BACKUP = [
    ("学习卡片表", "tblpLvxyYpDJgF92"),
    ("复习流水表", "tblbznzCSpPhSz93"),
    ("系统事件日志表", "tblPreh1ipB9LQpf"),
]

def run_cmd(cmd, timeout=60):
    try:
        # 如果是列表，转换为带引号的字符串
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

def backup_table(table_name, table_id):
    """备份单张表（使用JSON格式获取完整数据）"""
    all_records = []
    all_fields = []
    offset = 0
    limit = 200

    while True:
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", table_id, "--as", "user", "--limit", str(limit),
               "--offset", str(offset), "--format", "json"]
        ok, stdout, _ = run_cmd(cmd, timeout=60)
        if not ok:
            break

        try:
            data = json.loads(stdout)
            # 正确的JSON路径：data.data是二维数组，data.fields是字段名列表
            table_data = data.get("data", {})
            records_raw = table_data.get("data", [])
            fields = table_data.get("fields", [])
            record_ids = table_data.get("record_id_list", [])

            if not fields:
                break

            if not all_fields:
                all_fields = fields

            # 将二维数组转换为对象数组
            for i, row in enumerate(records_raw):
                record = {}
                for j, field in enumerate(fields):
                    if j < len(row):
                        record[field] = row[j]
                if i < len(record_ids):
                    record["_record_id"] = record_ids[i]
                all_records.append(record)

            has_more = table_data.get("has_more", False)
            if not has_more or len(records_raw) < limit:
                break
            offset += limit
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            # 如果JSON解析失败，尝试从表格格式中提取
            for line in stdout.split("\n"):
                if line.startswith("| ") and not line.startswith("| _record_id") and not line.startswith("| Meta:"):
                    all_records.append(line)
            break

    return {
        "table_name": table_name,
        "table_id": table_id,
        "record_count": len(all_records),
        "fields": all_fields,
        "records": all_records,
        "backup_time": datetime.now().isoformat(),
    }

def backup_system_state():
    """备份系统状态"""
    state_file = os.path.join(SCRIPTS_DIR, ".system_state.json")
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

    consume_file = os.path.join(SCRIPTS_DIR, ".consume_index.json")
    consume = {}
    if os.path.exists(consume_file):
        with open(consume_file, "r", encoding="utf-8") as f:
            consume = json.load(f)

    return {
        "system_state": state,
        "consume_index": consume,
        "backup_time": datetime.now().isoformat(),
    }

def cleanup_old_backups():
    """清理旧备份，保留最近7轮"""
    if not os.path.exists(BACKUP_DIR):
        return

    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("backup_") and f.endswith(".json"):
            fpath = os.path.join(BACKUP_DIR, f)
            backups.append((fpath, os.path.getmtime(fpath)))

    # 按修改时间排序，保留最近7个
    backups.sort(key=lambda x: x[1], reverse=True)
    for fpath, _ in backups[MAX_BACKUPS:]:
        try:
            os.remove(fpath)
            print(f"  清理旧备份: {os.path.basename(fpath)}")
        except Exception as e:
            print(f"  清理失败: {e}")

def main():
    print("=" * 60)
    print("7轮滚动备份")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 确保备份目录存在
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 备份所有表
    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "tables": [],
        "system_state": None,
    }

    for table_name, table_id in TABLES_TO_BACKUP:
        print(f"\n备份 {table_name} ({table_id})...")
        data = backup_table(table_name, table_id)
        if data:
            backup_data["tables"].append(data)
            print(f"  ✅ {data['record_count']} 条记录")
        else:
            print(f"  ❌ 备份失败")

    # 备份系统状态
    print(f"\n备份系统状态...")
    backup_data["system_state"] = backup_system_state()
    print(f"  ✅ 系统状态已备份")

    # 保存备份文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(backup_file)
    print(f"\n✅ 备份已保存: {os.path.basename(backup_file)} ({file_size} 字节)")

    # 清理旧备份
    print(f"\n清理旧备份（保留最近{MAX_BACKUPS}轮）...")
    cleanup_old_backups()

    # 列出当前备份
    print(f"\n当前备份列表:")
    if os.path.exists(BACKUP_DIR):
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")], reverse=True)
        for i, f in enumerate(backups):
            fpath = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            print(f"  [{i+1}] {f} ({size}字节, {mtime})")

    print(f"\n{'='*60}")
    print("备份完成")

if __name__ == "__main__":
    main()
