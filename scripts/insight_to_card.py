#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
insight_to_card.py - 洞察沉淀引擎（"越用越聪明"核心）
============================================================
把洞察表中尚未沉淀的高价值洞察，自动转化为学习系统的知识卡片：
  洞察表（INSIGHT_TABLE）→ 知识卡片（CARD_TABLE）→ 进入艾宾浩斯复习循环

实现"知识自增长"闭环：
  每日三察/用户洞察 → 洞察表沉淀 → 本脚本自动转卡片 → 系统学习它 → 越用越聪明

用法：
  python insight_to_card.py              # 沉淀本轮所有"知识沉淀"类未沉淀洞察
  python insight_to_card.py --dry-run    # 只统计不写入
  python insight_to_card.py --limit 10   # 单次最多处理 N 条
"""
import os
import sys
import json
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from v19_integration import BASE_TOKEN, INSIGHT_TABLE, CARD_TABLE, EVENT_LOG_TABLE

LARK = "lark-cli"
SUBJECT_MAP = {"人性洞察": "人性", "自然规律": "认知", "社会规律": "认知"}


def run_cmd(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        err = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, out, err
    except Exception as e:
        return False, "", str(e)


def list_insights():
    """读取洞察表全部记录（列式投影分页，record_id 在 record_id_list）"""
    rows, offset = [], 0
    while True:
        cmd = [LARK, "base", "+record-list", "--base-token", BASE_TOKEN,
               "--table-id", INSIGHT_TABLE, "--as", "user",
               "--format", "json", "--limit", "200", "--offset", str(offset)]
        ok, out, err = run_cmd(cmd)
        if not ok:
            return None, err
        data = json.loads(out)["data"]
        items = data.get("data", []) or []
        fields = data.get("fields", []) or []
        ids = data.get("record_id_list", []) or []
        if not items:
            break
        for i, row in enumerate(items):
            rec = {"record_id": ids[i] if i < len(ids) else ""}
            for k, v in zip(fields, row):
                rec[k] = v
            rows.append(rec)
        offset += len(items)
        if not data.get("has_more"):
            break
    return rows, None


def cell(rec, field):
    """从列式投影记录提取字段值"""
    v = rec.get(field)
    if v is None:
        return None
    if isinstance(v, list):
        return v[0].get("text") if v and isinstance(v[0], dict) else (v[0] if v else None)
    if isinstance(v, dict):
        return v.get("text", str(v))
    return v


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    limit = 100
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    rows, err = list_insights()
    if rows is None:
        print("读取洞察表失败:", err[:120])
        sys.exit(1)
    print("洞察表总记录:", len(rows))

    # 筛选：未沉淀 & 知识沉淀类（含规律洞察日报来源）
    pending = []
    for r in rows:
        rid = r.get("record_id")
        status = cell(r, "沉淀状态")
        ins_type = cell(r, "洞察类型")
        source = cell(r, "来源") or ""
        done = cell(r, "是否已沉淀")
        if rid and (status != "已沉淀" and done not in ("true", True)) and (
                ins_type == "知识沉淀" or source == "规律洞察日报"):
            pending.append(r)
    print("待沉淀洞察:", len(pending))
    if not pending:
        print("无待沉淀记录，任务完成")
        return

    # 幂等保护：跳过已沉淀过卡片的洞察（避免失败重试产生重复卡片）
    existing_ids = set()
    off2 = 0
    while True:
        r2 = run_cmd([LARK, "base", "+record-list", "--base-token", BASE_TOKEN,
                      "--table-id", CARD_TABLE, "--as", "user",
                      "--format", "json", "--limit", "200", "--offset", str(off2)])
        if not r2[0]:
            break
        d2 = json.loads(r2[1])["data"]
        f2 = d2.get("fields", []) or []
        i2 = d2.get("record_id_list", []) or []
        for i, row in enumerate(d2.get("data", []) or []):
            rec = dict(zip(f2, row))
            src = rec.get("来源知识ID")
            if src:
                existing_ids.add(str(src))
        off2 += len(d2.get("data", []) or [])
        if not d2.get("has_more"):
            break

    pending = [r for r in pending if r.get("record_id") not in existing_ids]
    print("去重后待沉淀洞察:", len(pending))
    if not pending:
        print("均已沉淀，任务完成")
        return

    to_sink = pending[:limit]
    ts_ms = int(datetime.now().timestamp() * 1000)
    today = datetime.now().strftime("%Y-%m-%d")
    cards, updates = [], []
    for r in to_sink:
        rid = r.get("record_id")
        title = cell(r, "洞察标题") or cell(r, "内容") or "洞察"
        content = cell(r, "内容") or cell(r, "洞察内容") or ""
        subj = "认知"
        for k, v in SUBJECT_MAP.items():
            if k in (title or ""):
                subj = v
                break
        cards.append({
            "卡片问题正面": title,
            "标准答案背面": content,
            "科目": [subj],
            "标签": ["方法"],
            "来源": "洞察沉淀",
            "来源知识ID": rid,
            "SOP关联": "insight_to_card",
            "卡片状态": "LEARNING",
        })
        updates.append(rid)

    if dry:
        print("[DRY-RUN] 将创建 {} 张卡片，更新 {} 条洞察".format(len(cards), len(updates)))
        for c in cards:
            print("  +", c["卡片问题正面"][:40], "|", c["科目"][0])
        return

    # 1. 写卡片
    payload = {"create_records": cards}
    jf = os.path.join(SCRIPT_DIR, "_tmp_insight_cards.json")
    with open(jf, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    ok, out, err = run_cmd([LARK, "base", "+record-batch-create", "--base-token", BASE_TOKEN,
                            "--table-id", CARD_TABLE, "--json", "@" + jf,
                            "--as", "user", "--format", "json"])
    if os.path.exists(jf):
        os.remove(jf)
    if not ok:
        print("卡片写入失败:", err[:200])
        sys.exit(1)
    resp = json.loads(out) if out else {}
    created = len(resp.get("data", {}).get("record_id_list", []) or [])
    print("✅ 已创建卡片:", created)

    # 2. 更新洞察沉淀状态（update_records map 结构）
    upd = {"update_records": {rid: {"沉淀状态": ["已沉淀"],
                                    "是否已沉淀": True,
                                    "沉淀位置": "知识卡片库"} for rid in updates}}
    jf2 = os.path.join(SCRIPT_DIR, "_tmp_insight_mark.json")
    with open(jf2, "w", encoding="utf-8") as f:
        json.dump(upd, f, ensure_ascii=False)
    ok2, _, err2 = run_cmd([LARK, "base", "+record-batch-update", "--base-token", BASE_TOKEN,
                            "--table-id", INSIGHT_TABLE, "--json", "@" + jf2,
                            "--as", "user", "--format", "json"])
    if os.path.exists(jf2):
        os.remove(jf2)
    print("✅ 洞察标记已沉淀:", "OK" if ok2 else "失败 " + err2[:120])

    # 3. 事件日志
    log = {"create_records": [{
        "event_id": "itc_{}".format(datetime.now().strftime("%Y%m%d%H%M%S%f")),
        "timestamp": ts_ms,
        "message": "洞察沉淀→知识卡片：{}张（来源=规律洞察日报/知识沉淀）".format(len(cards)),
        "severity": "INFO", "source": "system", "log_type": "INSTRUCTION",
    }]}
    jf3 = os.path.join(SCRIPT_DIR, "_tmp_itc_log.json")
    with open(jf3, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False)
    ok3, _, _ = run_cmd([LARK, "base", "+record-batch-create", "--base-token", BASE_TOKEN,
                         "--table-id", EVENT_LOG_TABLE, "--json", "@" + jf3,
                         "--as", "user", "--format", "json"])
    if os.path.exists(jf3):
        os.remove(jf3)
    print("✅ 事件日志:", "OK" if ok3 else "失败")


if __name__ == "__main__":
    main()
