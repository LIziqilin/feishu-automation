#!/usr/bin/env python
"""
data_audit.py - 全量数据一致性审计
验证derive结果与流水的一致性，识别数据质量问题
"""
from v19_integration import BASE_TOKEN
import subprocess, json, sys, time, re
from datetime import datetime, timedelta
from collections import defaultdict


CARD_TABLE = "tblpLvxyYpDJgF92"
FLOW_TABLE = "tblbznzCSpPhSz93"
LOG_TABLE = "tblPreh1ipB9LQpf"

def run_cmd(cmd, timeout=60):
    """执行命令并返回结果"""
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

def parse_markdown_table(stdout):
    lines = stdout.split("\n")
    records = []
    header = None
    for line in lines:
        if line.startswith("| _record_id"):
            header = [h.strip() for h in line.split("|")]
            continue
        if line.startswith("| rec") and header:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= len(header):
                record = {}
                for i, h in enumerate(header):
                    if i < len(parts):
                        record[h] = parts[i]
                records.append(record)
    return records

def parse_select_value(val):
    if not val:
        return ""
    val = str(val).strip()
    if val.startswith("[") and val.endswith("]"):
        val = val.strip("[]\"' ")
    return val

def parse_checkbox(val):
    if not val:
        return False
    return str(val).strip().lower() in ("true", "1", "yes", "checked")

def parse_datetime(ts_str):
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt
        except:
            continue
    return None

def main():
    print("=" * 70)
    print("全量数据一致性审计")
    print("=" * 70)

    issues = []
    warnings = []

    # 1. 读取所有数据
    print("\n[1/8] 读取数据...")
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", CARD_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, _ = run_cmd(cmd)
    cards = parse_markdown_table(stdout) if ok else []
    print(f"  学习卡片: {len(cards)} 张")

    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", FLOW_TABLE, "--as", "user", "--limit", "100"]
    ok, stdout, _ = run_cmd(cmd)
    flows = parse_markdown_table(stdout) if ok else []
    print(f"  复习流水: {len(flows)} 条")

    # 2. 卡片ID索引
    card_ids = set()
    card_map = {}
    for c in cards:
        rid = c.get("_record_id", "")
        if rid:
            card_ids.add(rid)
            card_map[rid] = c

    # 3. 流水审计
    print("\n[2/8] 流水审计...")
    flow_card_ids = set()
    event_ids = []
    excel_serial_count = 0
    empty_title_count = 0
    init_count = 0
    valid_result_count = 0

    for f in flows:
        cid = f.get("卡片ID", "")
        if cid:
            flow_card_ids.add(cid)

        # event_id审计
        eid = f.get("event_id", "")
        if eid:
            event_ids.append(eid)
            parts = eid.split("|")
            if len(parts) == 3:
                third = parts[2]
                if re.match(r'^\d+\.\d+$', third):
                    excel_serial_count += 1
                    warnings.append(f"  ⚠️ event_id含Excel序列号: {eid[:50]}...")

        # 标题审计
        title = f.get("卡片标题", "")
        if not title or title == "":
            empty_title_count += 1

        # 结果审计
        result = parse_select_value(f.get("结果", ""))
        if result == "INIT":
            init_count += 1
        elif result in ("会", "不会", "模糊"):
            valid_result_count += 1

    print(f"  流水涉及卡片: {len(flow_card_ids)} 张")
    print(f"  INIT流水: {init_count} 条")
    print(f"  有效作答流水: {valid_result_count} 条")
    print(f"  Excel序列号event_id: {excel_serial_count} 条")
    print(f"  空标题流水: {empty_title_count} 条")

    # 4. 孤儿流水检查
    print("\n[3/8] 孤儿流水检查...")
    orphan_flows = flow_card_ids - card_ids
    if orphan_flows:
        issues.append(f"  🔴 发现{len(orphan_flows)}条孤儿流水（卡片ID不存在）")
        for oid in list(orphan_flows)[:5]:
            print(f"    孤儿卡片ID: {oid}")
    else:
        print("  ✅ 无孤儿流水")

    # 5. 重复event_id检查
    print("\n[4/8] 重复event_id检查...")
    eid_counts = defaultdict(int)
    for eid in event_ids:
        eid_counts[eid] += 1
    duplicates = {k: v for k, v in eid_counts.items() if v > 1}
    if duplicates:
        issues.append(f"  🔴 发现{len(duplicates)}个重复event_id（幂等性风险）")
        for eid, cnt in list(duplicates.items())[:3]:
            print(f"    重复: {eid[:50]}... x{cnt}")
    else:
        print("  ✅ 无重复event_id")

    # 6. 卡片状态审计
    print("\n[5/8] 卡片状态审计...")
    status_counts = defaultdict(int)
    cards_with_flows = 0
    cards_without_flows = 0
    status_mismatch = 0

    for c in cards:
        rid = c.get("_record_id", "")
        status = parse_select_value(c.get("卡片状态", ""))
        status_counts[status] += 1

        # 检查有流水的卡是否状态合理
        card_flow_count = sum(1 for f in flows if f.get("卡片ID", "") == rid
                              and parse_select_value(f.get("结果", "")) != "INIT")
        if card_flow_count > 0:
            cards_with_flows += 1
            if status == "NOT_STARTED":
                status_mismatch += 1
                warnings.append(f"  ⚠️ 卡片{rid[:15]}有{card_flow_count}条作答但状态为NOT_STARTED")
        else:
            cards_without_flows += 1
            if status != "NOT_STARTED":
                status_mismatch += 1
                warnings.append(f"  ⚠️ 卡片{rid[:15]}无作答但状态为{status}")

    print(f"  状态分布: {dict(status_counts)}")
    print(f"  有作答卡片: {cards_with_flows} 张")
    print(f"  无作答卡片: {cards_without_flows} 张")
    print(f"  状态不匹配: {status_mismatch} 张")

    # 7. 派生值完整性检查
    print("\n[6/8] 派生值完整性检查...")
    empty_fields = defaultdict(int)
    for c in cards:
        for field in ["卡片状态", "连续正确次数", "掌握度M", "interval_days", "intro_offset", "version"]:
            val = c.get(field, "")
            if not val or val == "":
                empty_fields[field] += 1

    for field, cnt in empty_fields.items():
        if cnt > 0:
            warnings.append(f"  ⚠️ 字段{field}有{cnt}张卡为空")
            print(f"  ⚠️ {field}: {cnt} 张为空")
    if not empty_fields:
        print("  ✅ 所有派生字段非空")

    # 8. 新增字段默认值检查
    print("\n[7/8] 新增字段默认值检查...")
    flow_default_issues = 0
    for f in flows:
        superseded = parse_checkbox(f.get("superseded", "false"))
        untrusted = parse_checkbox(f.get("untrusted", "false"))
        revision = f.get("revision", "")
        if superseded:
            flow_default_issues += 1
        if untrusted:
            flow_default_issues += 1
    print(f"  superseded=TRUE: {sum(1 for f in flows if parse_checkbox(f.get('superseded','false')))} 条")
    print(f"  untrusted=TRUE: {sum(1 for f in flows if parse_checkbox(f.get('untrusted','false')))} 条")
    print(f"  (存量数据应为0，新作答才可能标记)")

    # 汇总
    print("\n" + "=" * 70)
    print("审计汇总")
    print("=" * 70)
    print(f"  🔴 严重问题: {len(issues)}")
    for i in issues:
        print(f"    {i}")
    print(f"  🟠 警告: {len(warnings)}")
    for w in warnings[:10]:
        print(f"    {w}")
    if len(warnings) > 10:
        print(f"    ... 还有{len(warnings)-10}条警告")

    # 生成审计报告
    report = {
        "audit_time": datetime.now().isoformat(),
        "cards_total": len(cards),
        "flows_total": len(flows),
        "issues": issues,
        "warnings": warnings,
        "status_distribution": dict(status_counts),
        "excel_serial_event_ids": excel_serial_count,
        "empty_title_flows": empty_title_count,
        "orphan_flows": len(orphan_flows),
        "duplicate_event_ids": len(duplicates),
        "status_mismatch": status_mismatch,
    }

    report_path = "D:/AI-Tools/feishu/V13方案增强/data_audit_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  审计报告已保存: {report_path}")

    if issues:
        print("\n  ❌ 存在严重问题，需要修复")
        return 1
    else:
        print("\n  ✅ 无严重问题，数据一致性良好")
        return 0

if __name__ == "__main__":
    sys.exit(main())
