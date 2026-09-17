#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V36 T5: 多维表格批量导出为JSON"""
import sys, os, json, subprocess, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v19_integration import BASE_TOKEN

LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tables")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TABLES = [
    ("学习卡表", "tblpLvxyYpDJgF92"),
    ("复习流水表", "tblbznzCSpPhSz93"),
    ("系统事件日志表", "tblPreh1ipB9LQpf"),
    ("心跳表", "tblJmm0ZIgqlYmyt"),
    ("任务总表", "tblz3H4lV7PCrBrX"),
    ("知识索引表", "tbl0NiUFeQzH2r3n"),
    ("系统健康表", "tblxJMndPNtZ7XyG"),
    ("洞察笔记表", "tblaqKBl87V9C0q1"),
    ("自动化队列表", "tblN2nL4hP9Qz7fK"),
]

def run_cmd(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        return False, "", str(e)

def export_table(table_name, table_id):
    """分页导出整张表"""
    all_records = []
    all_fields = []
    offset = 0
    page = 0
    while True:
        page += 1
        cmd = [LARK_CLI, "base", "+record-list",
               "--base-token", BASE_TOKEN, "--table-id", table_id,
               "--as", "user", "--limit", "200", "--offset", str(offset),
               "--format", "json"]
        ok, stdout, stderr = run_cmd(cmd, timeout=120)
        if not ok:
            print(f"  ✗ {table_name} 第{page}页失败: {stderr[:200]}")
            return None, 0
        try:
            data = json.loads(stdout)
        except:
            print(f"  ✗ {table_name} 第{page}页JSON解析失败: {stdout[:200]}")
            return None, 0
        if page == 1:
            all_fields = data.get("data", {}).get("fields", [])
        rows = data.get("data", {}).get("data", [])
        record_ids = data.get("data", {}).get("record_id_list", [])
        for i, row in enumerate(rows):
            rec = {"record_id": record_ids[i] if i < len(record_ids) else None}
            for j, field in enumerate(all_fields):
                rec[field] = row[j] if j < len(row) else None
            all_records.append(rec)
        has_more = data.get("data", {}).get("has_more", False)
        print(f"  第{page}页: {len(rows)}条, 累计{len(all_records)}条, has_more={has_more}")
        if not has_more or len(rows) == 0:
            break
        offset += len(rows)
        time.sleep(0.5)
    return {"fields": all_fields, "records": all_records, "count": len(all_records)}, len(all_records)

def main():
    date_str = datetime.now().strftime("%Y%m%d")
    print("=" * 60)
    print(f"V36 T5: 多维表格批量导出 ({date_str})")
    print("=" * 60)
    index = []
    for table_name, table_id in TABLES:
        print(f"\n【导出】{table_name} ({table_id})")
        result, count = export_table(table_name, table_id)
        if result is None:
            index.append({"表名": table_name, "table_id": table_id, "记录数": 0, "状态": "导出失败/DEGRADED", "文件": ""})
            continue
        filename = f"{table_name}_{date_str}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        file_size = os.path.getsize(filepath)
        print(f"  ✓ 导出完成: {filename} ({count}条, {file_size}字节)")
        index.append({"表名": table_name, "table_id": table_id, "记录数": count, "状态": "成功", "文件": filename, "大小": file_size})
    # 生成索引文件
    index_path = os.path.join(OUTPUT_DIR, "_索引.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"# 多维表格导出索引\n\n")
        f.write(f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"| 表名 | table_id | 记录数 | 状态 | 文件 | 大小 |\n")
        f.write(f"|---|---|---|---|---|---|\n")
        for item in index:
            size = f"{item.get('大小',0)}字节" if item.get('大小') else "-"
            f.write(f"| {item['表名']} | {item['table_id']} | {item['记录数']} | {item['状态']} | {item.get('文件','')} | {size} |\n")
        f.write(f"\n**导出总数**: {sum(i['记录数'] for i in index)} 条\n")
        f.write(f"**成功表数**: {sum(1 for i in index if i['状态']=='成功')}/{len(index)}\n")
    print(f"\n{'='*60}")
    print(f"导出完成，索引文件: {index_path}")
    print(f"成功: {sum(1 for i in index if i['状态']=='成功')}/{len(index)} 张表")
    print(f"总记录数: {sum(i['记录数'] for i in index)}")

if __name__ == "__main__":
    main()
