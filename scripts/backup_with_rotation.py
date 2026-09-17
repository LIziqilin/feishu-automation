#!/usr/bin/env python
"""
backup_with_rotation.py
分层滚动备份：
  --tier daily  (默认) → backup_YYYYMMDD_HHMMSS.json，保留最近 7 轮
  --tier hourly        → hourly_YYYYMMDD_HHMMSS.json，保留最近 24 轮
两层互不驱逐，保证 RPO 可达 ≤1h 且不丢日备（R3 不删历史，仅轮换本层旧文件）。
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, os, time, shutil, argparse
from datetime import datetime


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")
MAX_BACKUPS = 7          # daily 层保留
MAX_HOURLY = 24          # hourly 层保留
TIER_PREFIX = {"daily": "backup_", "hourly": "hourly_"}

TABLES_TO_BACKUP = [
    ("学习卡片表", "tblpLvxyYpDJgF92"),
    ("复习流水表", "tblbznzCSpPhSz93"),
    ("任务总表", "tblz3H4lV7PCrBrX"),
    ("知识索引表", "tbl0NiUFeQzH2r3n"),
    ("决策日志表", "tblEA13tWW56lu3K"),
    ("洞察笔记表", "tblaqKBl87V9C0q1"),
    ("模板与SOP表", "tblRGEeU9M3pPnjT"),
    ("系统健康表", "tblxJMndPNtZ7XyG"),
    ("自动化队列表", "tblOMd9Pfiju2tz0"),
    ("系统心跳", "tblJmm0ZIgqlYmyt"),
    ("检索日志表", "tblCwZyAhZbmJra2"),
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

def _lark_record_list(table_id, limit, offset):
    """拉取一页记录：先 user 身份，失败则回退 bot 身份（避免静默 0 记录）"""
    for ident in ("user", "bot"):
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", table_id, "--as", ident, "--limit", str(limit),
               "--offset", str(offset), "--format", "json"]
        ok, stdout, _ = run_cmd(cmd, timeout=60)
        if ok:
            try:
                d = json.loads(stdout)
                if d.get("ok") and d.get("data"):
                    return d, ident
            except Exception:
                continue
    return None, None

def backup_table(table_name, table_id):
    """备份单张表（先user后bot回退；返回 (data, identity)）"""
    all_records = []
    all_fields = []
    offset = 0
    limit = 200
    identity = None

    while True:
        data, ident = _lark_record_list(table_id, limit, offset)
        if data is None:
            break
        identity = identity or ident
        try:
            table_data = data.get("data", {})
            records_raw = table_data.get("data", [])
            fields = table_data.get("fields", [])
            record_ids = table_data.get("record_id_list", [])

            if not fields:
                break
            if not all_fields:
                all_fields = fields

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
        except Exception as e:
            print(f"  解析失败: {e}")
            break

    return {
        "table_name": table_name,
        "table_id": table_id,
        "record_count": len(all_records),
        "fields": all_fields,
        "records": all_records,
        "identity": identity,
        "backup_time": datetime.now().isoformat(),
    }, identity

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

def cleanup_old_backups(tier="daily"):
    """清理本层旧备份（仅轮换本层，不影响另一层；不物理删除非本层文件）"""
    if not os.path.exists(BACKUP_DIR):
        return
    prefix = TIER_PREFIX[tier]
    keep = MAX_BACKUPS if tier == "daily" else MAX_HOURLY

    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith(prefix) and f.endswith(".json"):
            fpath = os.path.join(BACKUP_DIR, f)
            backups.append((fpath, os.path.getmtime(fpath)))

    backups.sort(key=lambda x: x[1], reverse=True)
    for fpath, _ in backups[keep:]:
        try:
            os.remove(fpath)
            print(f"  清理旧备份[{tier}]: {os.path.basename(fpath)}")
        except Exception as e:
            print(f"  清理失败: {e}")

def _notify_degraded(backup_file):
    """DEGRADED 告警（飞书）：不得静默"""
    try:
        import urllib.request
        aid = os.environ.get("FEISHU_APP_ID")
        asec = os.environ.get("FEISHU_APP_SECRET")
        for p in [os.path.join(SCRIPTS_DIR, "feishu_insight_link.env")]:
            if (not aid or not asec) and os.path.exists(p):
                for line in open(p, encoding="utf-8-sig"):
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        aid = aid or (v.strip() if k.strip() == "FEISHU_APP_ID" else None)
                        asec = asec or (v.strip() if k.strip() == "FEISHU_APP_SECRET" else None)
        if not (aid and asec):
            print("  告警未发送: 缺少 FEISHU_APP_ID/SECRET")
            return
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": aid, "app_secret": asec}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            token = json.load(r)["tenant_access_token"]
        text = (f"⚠️ 备份 DEGRADED（记录数为0）\n"
                f"时间：{datetime.now().isoformat(timespec='seconds')}\n"
                f"文件：{os.path.basename(backup_file)}\n"
                f"原因：lark-cli 身份失效或权限不足（user token_missing）\n"
                f"处理：检查 lark-cli auth / bot 是否在 Base 内圈")
        body = {"receive_id": "oc_1fe154e172ab04622b7ffa810ac172bc", "msg_type": "text",
                "content": json.dumps({"text": text})}
        req2 = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req2, timeout=20) as r:
            print("  DEGRADED告警: 已发送" if json.load(r).get("code") == 0 else "  DEGRADED告警: 失败")
    except Exception as e:
        print("  DEGRADED告警异常:", e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["daily", "hourly"], default="daily")
    args = ap.parse_args()
    tier = args.tier
    prefix = TIER_PREFIX[tier]
    keep = MAX_BACKUPS if tier == "daily" else MAX_HOURLY

    print("=" * 60)
    print(f"分层滚动备份 [{tier}]")
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
        data, ident = backup_table(table_name, table_id)
        if data:
            backup_data["tables"].append(data)
            print(f"  OK {data['record_count']} 条记录 (identity={ident})")
        else:
            print(f"  FAIL 备份失败")

    # 记录本轮失败的表（not_found/权限），不得静默为0
    failed_tables = [t["table_name"] for t in backup_data["tables"] if t.get("record_count", 0) == 0]
    total_records = sum(t.get("record_count", 0) for t in backup_data["tables"])
    degraded = (total_records == 0)
    backup_data["degraded"] = degraded
    backup_data["total_records"] = total_records
    backup_data["empty_tables"] = failed_tables

    # 备份系统状态
    print(f"\n备份系统状态...")
    backup_data["system_state"] = backup_system_state()
    print(f"  ✅ 系统状态已备份")

    # 保存备份文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"{prefix}{timestamp}.json")
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(backup_file)
    print(f"\n✅ 备份已保存: {os.path.basename(backup_file)} ({file_size} 字节, 共{total_records}条)")
    if backup_data.get("empty_tables"):
        print(f"  ⚠ 跳过/空表: {backup_data['empty_tables']}")

    if degraded:
        # R6：不得把 DEGRADED 当成功；不轮换旧备份，保留证据
        print("\n❌ DEGRADED: 全部表记录数为0（身份/权限异常），不执行轮换，保留旧备份")
        _notify_degraded(backup_file)
        return 3

    # 清理本层旧备份
    print(f"\n清理旧备份[{tier}]（保留最近{keep}轮）...")
    cleanup_old_backups(tier)

    # 列出当前备份
    print(f"\n当前备份列表:")
    if os.path.exists(BACKUP_DIR):
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(prefix)], reverse=True)
        for i, f in enumerate(backups):
            fpath = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            print(f"  [{i+1}] {f} ({size}字节, {mtime})")

    print(f"\n{'='*60}")
    print("备份完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())
