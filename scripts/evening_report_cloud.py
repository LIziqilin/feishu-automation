#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""evening_report_cloud.py — V16 云端晚报（P1-4，2026-10-25）
GitHub Actions 云端运行：查任务表今日完成情况 + 明日待办 + 学习卡片今日复习汇总 -> 推总控群。
零 npm/lark-cli 依赖：标准库 + 飞书 OpenAPI 直连。
用法：
  python evening_report_cloud.py            # 查询+组消息+推送（云端）
  python evening_report_cloud.py --dry-run  # 只查询+组消息并打印，不推送
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
    lines = [f"🌆 云端晚报（关机可用·备援）{today}", ""]

    # 1) 任务表：今日完成 vs 剩余未完成
    try:
        tasks = list_all_records(tok, TASK_TABLE)
        done_today, remain = [], []
        for r in tasks:
            name = str(field(r, "任务名称") or "?")
            st = str(field(r, "状态") or "")
            upd = field(r, "更新时间")
            if st in ("已完成", "完成"):
                if isinstance(upd, (int, float)) and \
                        datetime.fromtimestamp(upd / 1000).strftime("%Y-%m-%d") == today:
                    done_today.append(name)
                else:
                    done_today.append(f"{name}(较早)")
            elif st not in ("已取消", "已归档"):
                remain.append(name)
        lines.append(f"✅ 今日已完成 {len(done_today)} 项")
        for n in done_today[:8]:
            lines.append(f"  · {n}")
        lines.append(f"📌 待办剩余 {len(remain)} 项")
        for n in remain[:8]:
            lines.append(f"  · {n}")
        if not remain:
            lines.append("  全部完成 🎉")
    except Exception as e:
        lines.append(f"⚠️ 任务表读取失败：{e}")

    lines.append("")

    # 2) 学习卡片：今日应复习 / 今日已答（按掌握度分布）
    try:
        cards = list_all_records(tok, CARD_TABLE)
        due_today, answered_today = 0, 0
        mastery = {"高": 0, "中": 0, "低": 0}
        for r in cards:
            st = str(field(r, "卡片状态") or "")
            if st in ("NOT_STARTED", "ARCHIVED"):
                continue
            nxt = field(r, "下次复习日期")
            if isinstance(nxt, (int, float)) and \
                    datetime.fromtimestamp(nxt / 1000).strftime("%Y-%m-%d") <= today:
                due_today += 1
            last = field(r, "最近答题时间")
            if isinstance(last, (int, float)) and \
                    datetime.fromtimestamp(last / 1000).strftime("%Y-%m-%d") == today:
                answered_today += 1
            m = str(field(r, "掌握度M") or "")
            key = "高" if m and float(str(m).replace("%", "")) >= 80 else \
                  ("中" if m and float(str(m).replace("%", "")) >= 60 else "低")
            mastery[key] = mastery.get(key, 0) + 1
        lines.append(f"📚 卡片：今日应复习 {due_today} 张，今日已答 {answered_today} 张")
        lines.append(f"  掌握度分布：高 {mastery['高']} / 中 {mastery['中']} / 低 {mastery['低']}")
    except Exception as e:
        lines.append(f"⚠️ 学习卡片读取失败：{e}")

    lines.append("")
    lines.append("明日待办请查看晨报，保持答题闭环。")
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
