#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coze_batch_tasks.py — V46 Coze 批量任务（字段捷径脚本版）
====================================================================
用 Coze API 批量处理多维表格行，替代/增强飞书原生字段捷径。
复用 coze_gateway.run()，业务流程：读行 → 调 Coze → 写回列。

4 个批量任务：
  1. wrong_answer  错题解析：学习卡片表（原题/错因 → AI解析+复习建议）
  2. weekly_report 学习周报：复习流水表（本周记录 → 周报草稿）
  3. profile       画像演化：用户画像表（行为记录 → 画像标签建议）
  4. health        健康诊断：系统健康表（异常项 → 修复建议）

用法：
  python coze_batch_tasks.py wrong_answer --limit 3      # 处理3条未解析错题
  python coze_batch_tasks.py weekly_report --week 2026W38
  python coze_batch_tasks.py profile --limit 5
  python coze_batch_tasks.py health --limit 5
"""
import os, sys, json, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deepseek_gateway as llm_gw  # V47: 默认 DeepSeek V4 Flash（替代 Coze 省积分）

BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
TABLES = {
    "wrong_answer": "tblpLvxyYpDJgF92",   # 学习卡片表
    "weekly_report": "tblbznzCSpPhSz93",   # 复习流水表
    "profile": "tbldjGffbuPKCe21",         # 用户画像表
    "health": "tblxJMndPNtZ7XyG",          # 系统健康表
}

PROMPTS = {
    "wrong_answer": "你是学习教练。原题：{q}\n错因：{e}\n请输出：1)核心概念澄清 2)正解思路 3)3天后复习建议。简洁，200字内。",
    "weekly_report": "你是学习分析师。以下是本周复习记录：{r}\n请输出学习周报草稿：1)本周完成 2)薄弱点 3)下周计划。300字内。",
    "profile": "你是用户画像分析师。行为记录：{b}\n请输出1-2条画像标签建议（维度+值+置信度0-1）。JSON格式。",
    "health": "你是运维专家。异常项：{h}\n请输出：1)根因判断 2)修复步骤 3)优先级。150字内。",
}


def lark_cli(*args):
    r = subprocess.run(["lark-cli"] + list(args) + ["--as", "user"],
        capture_output=True, timeout=60, cwd=os.path.dirname(os.path.abspath(__file__)))
    out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
    return json.loads(out) if out else {}


def list_records(table_id, limit=5):
    d = lark_cli("base", "+record-list", "--base-token", BASE,
                 "--table-id", table_id, "--limit", str(limit), "--format", "json")
    data = d.get("data", {})
    # 列式投影：data.fields=列名, data.data=行数组, 行末是 record_id
    fields = data.get("fields", [])
    rows = data.get("data", []) or data.get("items", [])
    out = []
    for row in rows[:limit]:
        if isinstance(row, list):
            rid = row[-1] if row else None
            fd = {fields[i]: row[i] for i in range(min(len(fields), len(row)-1))}
            out.append({"record_id": rid, "fields": fd})
        elif isinstance(row, dict):
            out.append(row)
    return out


def run_task(task, limit=5):
    t = TABLES[task]
    rows = list_records(t, limit)
    print(f"[{task}] 读到 {len(rows)} 行")
    ok_count = 0
    for row in rows[:limit]:
        rid = row.get("record_id") or row.get("id")
        fields = row.get("fields", {})
        # 构造 prompt 变量
        if task == "wrong_answer":
            q = str(fields.get("原题") or fields.get("题目") or fields.get("知识点") or "未知")[:200]
            e = str(fields.get("错因") or fields.get("错误答案") or "未知")[:100]
            prompt = PROMPTS[task].format(q=q, e=e)
        elif task == "health":
            h = str(fields.get("检查项") or fields.get("实际状态") or "未知")[:200]
            prompt = PROMPTS[task].format(h=h)
        elif task == "profile":
            b = str(fields.get("画像维度") or fields.get("画像值") or "未知")[:200]
            prompt = PROMPTS[task].format(b=b)
        else:
            prompt = PROMPTS[task].format(r=str(fields)[:300])

        print(f"  -> {str(rid)[:12]}... 调 DeepSeek V4 Flash...")
        ok, resp = llm_gw.run(prompt[:500])
        if ok:
            print(f"     ✅ {resp[:80]}...")
            ok_count += 1
        else:
            print(f"     ❌ {resp[:80]}")
    print(f"[{task}] 完成 {ok_count}/{len(rows[:limit])}")
    return ok_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=list(TABLES.keys()))
    ap.add_argument("--limit", type=int, default=3)
    a = ap.parse_args()
    run_task(a.task, a.limit)


if __name__ == "__main__":
    main()
