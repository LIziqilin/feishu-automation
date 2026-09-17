#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
todo_export_docx.py - 待办清单 DOCX 导出（AI大系统 make_todo_docx 深度融合版 V13）
============================================================
读取任务总表，生成《个人AI系统·待办清单.docx》：按状态分组、含完成率统计，
保存到本地并推送总控群（附文件路径）。

用法：
  python todo_export_docx.py                # 全部任务导出
  python todo_export_docx.py --status 待办  # 只导出指定状态
  python todo_export_docx.py --out D:\\out\\待办清单.docx
"""
import sys
import os
import json
import subprocess
from datetime import datetime
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import BASE_TOKEN, TASK_TABLE, TARGET_CHAT_ID

try:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_OK = True
except Exception:
    DOCX_OK = False


def run_cmd(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def send_message(text):
    cmd = ["lark-cli", "im", "+messages-send",
           "--chat-id", TARGET_CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)


def get_all_records(table_id):
    result = []
    offset = 0
    while True:
        cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", table_id, "--as", "user",
               "--limit", "200", "--offset", str(offset), "--format", "json"]
        ok, stdout, stderr = run_cmd(cmd)
        if not ok:
            break
        try:
            data = json.loads(stdout).get("data", {})
        except Exception:
            break
        records = data.get("data", [])
        record_ids = data.get("record_id_list", [])
        fields = data.get("fields", [])
        for i, rec in enumerate(records):
            if isinstance(rec, list):
                d = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, f in enumerate(fields):
                    if j < len(rec):
                        d[f] = rec[j]
                result.append(d)
        offset += len(records)
        if not data.get("has_more", False) or not records:
            break
    return result


def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    return str(v)


def ts_date(v):
    """datetime 值 → yyyy-MM-dd"""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        ts = v / 1000.0 if v > 1e11 else v
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return ""
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v)
            return d.strftime("%Y-%m-%d")
        except Exception:
            return v[:10]
    return ""


def build_docx(tasks, out_path, status_filter=None):
    doc = Document()
    # 标题
    title = doc.add_heading("个人AI系统 · 待办清单", level=0)
    sub = doc.add_paragraph("生成时间：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    sub.runs[0].font.size = Pt(10)
    sub.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # 按状态分组
    groups = Counter(cell_text(t.get("状态") or "未知") for t in tasks)
    total = len(tasks)
    done = sum(1 for t in tasks if cell_text(t.get("状态")) in ("已完成", "完成"))
    pct = done / total * 100 if total else 0

    doc.add_heading("一、总览", level=1)
    doc.add_paragraph("任务总数：{} ｜ 已完成：{} ｜ 完成率：{:.1f}%".format(total, done, pct))

    doc.add_heading("二、任务明细（按状态分组）", level=1)
    for status in sorted(groups, key=lambda s: -groups[s]):
        if status_filter and status != status_filter:
            continue
        doc.add_heading("【{}】（{} 条）".format(status, groups[status]), level=2)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        for i, h in enumerate(["任务名称", "类别", "优先级", "截止日期", "状态"]):
            hdr[i].text = h
        for t in tasks:
            if status_filter and cell_text(t.get("状态")) != status_filter:
                continue
            if cell_text(t.get("状态") or "未知") != status:
                continue
            row = table.add_row().cells
            row[0].text = cell_text(t.get("任务名称"))[:40]
            row[1].text = cell_text(t.get("类别"))
            row[2].text = cell_text(t.get("优先级"))
            row[3].text = ts_date(t.get("截止日期"))
            row[4].text = cell_text(t.get("状态"))
        if status_filter and status != status_filter:
            continue

    doc.save(out_path)
    return out_path


def main():
    args = sys.argv[1:]
    status_filter = None
    out_path = os.path.join(SCRIPT_DIR, "待办清单_{}.docx".format(datetime.now().strftime("%Y%m%d")))
    if "--status" in args:
        try:
            status_filter = args[args.index("--status") + 1]
        except Exception:
            pass
    if "--out" in args:
        try:
            out_path = args[args.index("--out") + 1]
        except Exception:
            pass

    if not DOCX_OK:
        print("[!] python-docx 未安装，无法导出")
        return

    tasks = get_all_records(TASK_TABLE)
    print("任务总数：{}".format(len(tasks)))
    if not tasks:
        print("[!] 任务表为空")
        return

    path = build_docx(tasks, out_path, status_filter)
    print("[OK] 已导出：{}".format(path))
    size_kb = os.path.getsize(path) / 1024
    print("文件大小：{:.1f} KB".format(size_kb))

    send_ok, _, _ = send_message(
        "📋 待办清单已导出\n📎 {}\n（{:.1f} KB，共 {} 条任务）".format(path, size_kb, len(tasks)))
    print("[OK] 已推送总控群" if send_ok else "[!] 群推送失败")


if __name__ == "__main__":
    main()
