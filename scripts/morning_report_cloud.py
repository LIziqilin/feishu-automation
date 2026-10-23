#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""morning_report_cloud.py — V16 早报云端永续版（P0-A 恢复，2026-10-23）
GitHub Actions 云端运行：查任务表今日待办 + 学习卡片表今日复习 -> 组早报 -> 推总控群。
零 npm/lark-cli 依赖：标准库 + 飞书 OpenAPI 直连（凭据走环境变量，与 insight_daily 同模式）。
用法：
  python morning_report_cloud.py            # 查询+组消息+推送（云端）
  python morning_report_cloud.py --dry-run  # 只查询+组消息并打印，不推送（本地模拟验证）
"""
import os
import sys
import json
import urllib.request
from datetime import datetime

BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
APP_ID = os.environ.get("LARK_APP_ID", "")
APP_SECRET = os.environ.get("LARK_APP_SECRET", "")
CHAT_ID = os.environ.get("CHAT_ID", "oc_1fe154e172ab04622b7ffa810ac172bc")
TASK_TABLE = "tblz3H4lV7PCrBrX"
CARD_TABLE = "tblpLvxyYpDJgF92"
HOST = "https://open.feishu.cn/open-apis"
DRY_RUN = "--dry-run" in sys.argv


def post(url, body, headers=None, timeout=30):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def get(url, headers=None, timeout=30):
    h = {}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def feishu_token():
    d = post(f"{HOST}/auth/v3/tenant_access_token/internal",
             {"app_id": APP_ID, "app_secret": APP_SECRET})
    if d.get("code") != 0:
        raise RuntimeError(f"token失败 code={d.get('code')} msg={d.get('msg')}")
    return d["tenant_access_token"]


def list_all_records(tok, table, page_size=500):
    """分页拉全表记录，过滤在本地做（简化云端依赖）"""
    out, page = [], None
    while True:
        url = f"{HOST}/bitable/v1/apps/{BASE_TOKEN}/tables/{table}/records?page_size={page_size}"
        if page:
            url += f"&page_token={page}"
        d = get(url, {"Authorization": f"Bearer {tok}"})
        if d.get("code") != 0:
            raise RuntimeError(f"records失败 code={d.get('code')} msg={d.get('msg')}")
        items = d["data"].get("items", [])
        out.extend(items)
        if d["data"].get("has_more"):
            page = d["data"].get("page_token")
        else:
            break
    return out


def field(rec, name):
    """字段取值归一：文本->str；日期->毫秒时间戳；单选->文本；多选->list[str]"""
    v = rec.get("fields", {}).get(name)
    if v is None:
        return None
    if isinstance(v, dict):
        if "text" in v:
            return v["text"]
        if "value" in v and isinstance(v["value"], list):
            return [x.get("name") for x in v["value"] if isinstance(x, dict)]
        return v.get("name")
    return v


def api_send_message(text):
    if not (APP_ID and APP_SECRET):
        return False, "缺少 LARK_APP_ID/LARK_APP_SECRET 环境变量"
    try:
        tok = feishu_token()
        payload = json.dumps({
            "receive_id": CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{HOST}/im/v1/messages?receive_id_type=chat_id",
            data=payload, headers={"Content-Type": "application/json",
                                   "Authorization": f"Bearer {tok}"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8", errors="replace"))
        return res.get("code") == 0, json.dumps(res, ensure_ascii=False)[:300]
    except Exception as e:
        return False, str(e)


def main():
    if not (BASE_TOKEN and APP_ID and APP_SECRET):
        print("❌ 缺少 FEISHU_BASE_TOKEN / LARK_APP_ID / LARK_APP_SECRET 环境变量")
        sys.exit(2)

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    tok = feishu_token()
    lines = [f"☀️ 云端早报（关机可用·备援）{today}", ""]

    # 1) 任务表：进行中/待办/已逾期
    try:
        tasks = list_all_records(tok, TASK_TABLE)
        active = []
        for r in tasks:
            st = str(field(r, "状态") or "")
            if st in ("已完成", "完成", "已取消", "已归档"):
                continue
            name = str(field(r, "任务名称") or "?")
            due = field(r, "截止日期")
            due_str = ""
            if isinstance(due, (int, float)):
                due_str = datetime.fromtimestamp(due / 1000).strftime("%m-%d")
            prio = str(field(r, "优先级") or "低")
            active.append((prio, st, name, due_str))
        prio_rank = {"高": 0, "中": 1, "低": 2, "P3": 3}
        active.sort(key=lambda x: (prio_rank.get(x[0], 9), x[3] or ""))
        lines.append(f"📋 今日任务（未完成 {len(active)} 项）")
        if active:
            for prio, st, name, due in active[:8]:
                flag = "❗" if (due and due <= now.strftime("%m-%d")) else "·"
                lines.append(f"  {flag}[{prio}][{st}] {name}" + (f"（截止{due}）" if due else ""))
        else:
            lines.append("  无未完成任务 🎉")
    except Exception as e:
        lines.append(f"⚠️ 任务表读取失败：{e}")

    lines.append("")

    # 2) 学习卡片：今日待复习（下次复习日期 <= 今天 且 非未开始/已掌握/已归档）
    try:
        cards = list_all_records(tok, CARD_TABLE)
        today_cards = []
        for r in cards:
            st = str(field(r, "卡片状态") or "")
            if st in ("NOT_STARTED", "MASTERED", "ARCHIVED"):
                continue
            nxt = field(r, "下次复习日期")
            if isinstance(nxt, (int, float)):
                nd = datetime.fromtimestamp(nxt / 1000).strftime("%Y-%m-%d")
                if nd <= today:
                    q = str(field(r, "卡片问题正面") or "?")
                    subj = str(field(r, "科目") or "")
                    today_cards.append((q, subj))
        lines.append(f"📚 今日复习（{len(today_cards)} 张）")
        if today_cards:
            for q, subj in today_cards[:8]:
                lines.append(f"  · [{subj or '未分类'}] {q}")
        else:
            lines.append("  今日无待复习卡片 ✅")
    except Exception as e:
        lines.append(f"⚠️ 学习卡片读取失败：{e}")

    lines.append("")
    lines.append("回复「会 / 不会 / 模糊」复习卡片，任务完成请更新多维表格，保持闭环。")
    text = "\n".join(lines)

    if DRY_RUN:
        print(text)
        print("\n[DRY-RUN] 未推送。")
        sys.exit(0)

    ok, err = api_send_message(text)
    print(text)
    print(f"\n推送结果: ok={ok} err={err}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
