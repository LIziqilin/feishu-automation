#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多维表格 Dashboard 健康巡检脚本（最终版系统纳入）
====================================================
背景：2026-09-17 修复了 4 个引用已删除字段 fld1rna1r0 的损坏组件（待复习卡片×2、
掌握度M分布、学习趋势近30天），并重建了配置错乱的任务状态分布图。
本脚本固化巡检能力：对目标 Base 的仪表盘逐组件 get + get-data 验证，
标记失效引用 / type=unknown / 计算失败，输出健康报告，防止再次退化。

用法：
    python dashboard_health_check.py              # 巡检 + 打印摘要
    python dashboard_health_check.py --json out   # 输出 JSON 报告到 out.json

依赖：config_local.py（BASE_TOKEN、表 ID、lark-cli 路径）
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config_local import BASE_TOKEN, LARK_NODE_EXE, LARK_CLI_SCRIPT
except Exception as e:  # 允许从任意 cwd 运行
    sys.path.insert(0, ".")
    from config_local import BASE_TOKEN, LARK_NODE_EXE, LARK_CLI_SCRIPT

# 目标仪表盘（2026-09-17 盘点）
DASHBOARDS = [
    {"id": "blkYtXPlVlKu25x5", "name": "总仪表盘"},
    {"id": "blkwkb3SHQVyVli9", "name": "学习卡片仪表盘"},
    {"id": "blkxDBmVwBsgM1U3", "name": "知识健康度"},
]

# 已知损坏组件（修复后应健康；若再次出现 ok=false 说明退化）
KNOWN_BROKEN = {
    "chtcniKX6EctE9vcnODtJ7pU1le": "总仪表盘/待复习卡片(statistics)",
    "chtcnObKxWArxY3812KA7ZDyTpd": "总仪表盘/掌握度M分布(column)",
    "chtcnb645mOGBeAmt7MZT86M6kh": "总仪表盘/学习趋势近30天(line)",
    "chtcn1eHkZZbvtmbPTpsBA7lBGr": "知识健康度/待复习卡片(statistics)",
}
# 已重建组件（旧ID已删除，新ID应健康）
REBUILT = {
    "chtcn5AEiejNIWlXMIWCmC9vKhg": "总仪表盘/任务状态分布图(pie, 重建于20260917)",
    "chtcnoAWoyIR6n0b2rQdsAkji7j": "总仪表盘/学习进度概览(pie, 重建于20260917, 学习卡片表卡片状态分布)",
    "chtcneR6lGH7KJzHO8QKJL43ukb": "总仪表盘/本周完成任务数(statistics, 重建于20260917, 任务总表filter本周已完成)",
    "chtcn3d2gehnHY0kAKB6ONuiQRg": "总仪表盘/科目分布(column, 重建于20260917, 任务总表科目分布)",
}
# 关键动态公式字段（2026-09-17 创建，Dashboard 依赖）
KEY_FORMULA_FIELDS = {
    "tblpLvxyYpDJgF92|fldODKL3En": "学习卡片表/今日待复习(公式checkbox)",
    "tblpLvxyYpDJgF92|fldYtgO0u4": "学习卡片表/近30天已复习(公式checkbox)",
    "tblpLvxyYpDJgF92|fld3NebJue": "学习卡片表/掌握度档位(公式文本)",
    "tblz3H4lV7PCrBrX|fldFtfTFNW": "任务总表/本周已完成(公式checkbox)",
}
# 已重建的 unknown 组件（旧ID已删除，仅存档）
ARCHIVED_UNKNOWN = {
    "chtcnb5S9ZBbzxMJGPzkZzRTslh": "总仪表盘/学习进度概览(旧, unknown, 已删除)",
    "chtcn8ekRGVYZDGlUsrZz4ZcD5d": "总仪表盘/本周完成任务数(旧, unknown, 已删除)",
    "chtcnlfviLRYb0OVAn6jeTW4wrh": "总仪表盘/科目分布(旧, unknown, 已删除)",
}


def run_cli(*args):
    """执行 lark-cli，返回 (ok, parsed)"""
    cmd = [LARK_NODE_EXE, LARK_CLI_SCRIPT, "base"] + list(args) + [
        "--base-token", BASE_TOKEN, "--as", "user", "--format", "json"
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        out = p.stdout + p.stderr
    except Exception as e:
        return False, {"error": str(e)}
    idx = out.find("{")
    if idx < 0:
        return False, {"error": "no JSON in output", "raw": out[:200]}
    try:
        parsed = json.loads(out[idx:])
    except Exception as e:
        return False, {"error": f"JSON parse: {e}", "raw": out[:200]}
    return parsed.get("ok", False), parsed


def list_blocks(dash_id):
    ok, d = run_cli("+dashboard-block-list", "--dashboard-id", dash_id)
    if not ok:
        return None, d
    items = d.get("data", {}).get("items", [])
    return items, None


def get_block(dash_id, block_id):
    ok, d = run_cli("+dashboard-block-get", "--dashboard-id", dash_id, "--block-id", block_id)
    if not ok:
        return None, d.get("error", {})
    return d.get("data", {}).get("block", {}), None


def get_data(block_id):
    ok, d = run_cli("+dashboard-block-get-data", "--block-id", block_id)
    if not ok:
        return None, d.get("error", {})
    return d.get("data", {}), None


def main():
    out_json = "--json" in sys.argv
    report = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "dashboards": [], "issues": []}
    for dash in DASHBOARDS:
        items, err = list_blocks(dash["id"])
        dd = {"id": dash["id"], "name": dash["name"], "blocks": []}
        if items is None:
            dd["error"] = err
            report["issues"].append({"dashboard": dash["name"], "issue": f"list失败: {err}"})
            report["dashboards"].append(dd)
            continue
        print(f"\n=== {dash['name']} ({len(items)} 组件) ===")
        for it in items:
            bid = it.get("block_id")
            bname = it.get("block_name") or "?"
            btype = it.get("block_type")
            blk, gerr = get_block(dash["id"], bid)
            entry = {"block_id": bid, "name": bname, "cli_type": btype}
            if blk is None:
                entry["status"] = "BROKEN"
                entry["error"] = gerr
                report["issues"].append({"dashboard": dash["name"], "block": bname or bid,
                                         "issue": f"get失败: {gerr}"})
                print(f"  [BROKEN] {bname or bid}: {gerr}")
            else:
                entry["status"] = "OK"
                entry["type"] = blk.get("type")
                entry["data_config"] = blk.get("data_config")
                if blk.get("type") == "unknown":
                    entry["status"] = "UNKNOWN_TYPE"
                    report["issues"].append({"dashboard": dash["name"], "block": bname or bid,
                                             "issue": "type=unknown（可计算但CLI不识别类型，语义待确认）"})
                if blk.get("type") not in ("text", None):
                    data, derr = get_data(bid)
                    if data is None:
                        entry["status"] = "DATA_FAIL"
                        entry["error"] = derr
                        report["issues"].append({"dashboard": dash["name"], "block": bname or bid,
                                                 "issue": f"get-data失败: {derr}"})
                    else:
                        md = data.get("main_data", [])
                        entry["data_rows"] = len(md)
                        entry["data_sample"] = md[:2]
                flag = "OK" if entry["status"] == "OK" else entry["status"]
                print(f"  [{flag}] {bname or bid} | type={blk.get('type')}")
            dd["blocks"].append(entry)
            time.sleep(0.3)  # 串行限速
        report["dashboards"].append(dd)

    # 校验关键动态公式字段（Dashboard 数据源依赖）
    formula_issues = 0
    for key, label in KEY_FORMULA_FIELDS.items():
        table_id, field_id = key.split("|")
        ok, d = run_cli("+field-get", "--table-id", table_id, "--field-id", field_id)
        if not ok:
            formula_issues += 1
            report["issues"].append({"dashboard": "公式字段", "block": label,
                                     "issue": f"field-get失败: {d.get('error', {}).get('message', '')[:100]}"})
            print(f"  [MISSING] 公式字段 {label}: {d.get('error', {}).get('message', '')[:100]}")
        else:
            print(f"  [OK] 公式字段 {label} 在位")
        time.sleep(0.2)

    # 汇总
    total = sum(len(d.get("blocks", [])) for d in report["dashboards"])
    issues = len(report["issues"])
    print(f"\n===== 巡检汇总：{total} 组件，{issues} 个问题 =====")
    for i in report["issues"]:
        print(f"  - [{i['dashboard']}] {i.get('block','')}: {i['issue']}")
    if out_json:
        path = sys.argv[sys.argv.index("--json") + 1] if len(sys.argv) > sys.argv.index("--json") + 1 else "dashboard_health.json"
        if not path.endswith(".json"):
            path += ".json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已写入 {os.path.abspath(path)}")
    return 0 if issues == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
