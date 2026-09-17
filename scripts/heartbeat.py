# -*- coding: utf-8 -*-
"""P2-2 心跳写入脚本 v2：向系统心跳表写入心跳行，供静默失败检测（>12h 无心跳=告警）
用法: python heartbeat.py [--dry-run]
来源: TaskScheduler（8:00/14:00/22:00）
v2 变更（2026-09-08）: 新增 app 直连写入为第一通道（app 已获心跳表授权），
lark-cli 用户通道降级为兜底 —— 解决任务计划环境 token_missing 导致 Last Result=1。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.request

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
HEARTBEAT_TABLE = 'tblJmm0ZIgqlYmyt'
HEALTH_TABLE = 'tblxJMndPNtZ7XyG'
ENV_CANDIDATES = [
    r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env",
    r"D:\AI-Tools\feishu\飞书的高阶用法\feishu_insight_link.env",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu_insight_link.env"),
]


def load_secret(key):
    v = os.environ.get(key)
    if v:
        return v
    for p in ENV_CANDIDATES:
        try:
            for line in open(p, encoding="utf-8-sig"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    if k.strip() == key:
                        return val.strip()
        except Exception:
            continue
    return ""


def get_token(app_id, app_secret):
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def write_via_app(fields):
    """app 直连：tenant_access_token 写心跳表（第一通道，2026-09-08 起 app 已获授权）"""
    app_id = load_secret("FEISHU_APP_ID")
    app_secret = load_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        return None, "no app credentials"
    tr = get_token(app_id, app_secret)
    if tr.get("code") != 0:
        return None, "token_fail:" + str(tr.get("msg"))
    token = tr["tenant_access_token"]
    url = "https://open.feishu.cn/open-apis/bitable/v1/apps/%s/tables/%s/records" % (BASE, HEARTBEAT_TABLE)
    req = urllib.request.Request(
        url,
        data=json.dumps({"fields": fields}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return True, "app_ok"
        return None, "app_code_%s:%s" % (resp.get("code"), resp.get("msg"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        return None, "app_http_%s:%s" % (e.code, body)


def write_via_larkcli(fields):
    """兜底：lark-cli 用户通道（sandbox 环境有用户 token）"""
    lark_candidates = [
        r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\sandbox_envs_dir\envs\9d7cacae-22ee-40c0-ad48-57bf6023ce73\override_dlcs\lark-cli.exe",
        r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd",
        "lark-cli",
    ]
    lark_cmd = next((c for c in lark_candidates if os.path.isfile(c) or c == "lark-cli"), "lark-cli")
    if lark_cmd.lower().endswith(".cmd") or lark_cmd.lower().endswith(".bat"):
        argv = ["cmd", "/c", lark_cmd, "base", "+record-upsert",
                "--base-token", BASE, "--table-id", HEARTBEAT_TABLE,
                "--json", json.dumps(fields, ensure_ascii=False), "--format", "json"]
    else:
        argv = [lark_cmd, "base", "+record-upsert",
                "--base-token", BASE, "--table-id", HEARTBEAT_TABLE,
                "--json", json.dumps(fields, ensure_ascii=False), "--format", "json"]
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8-sig")
    out = r.stdout.strip()
    if '"ok": true' in out:
        return True, "lark_ok"
    return None, "lark_fail:" + out[:200]


def write_health_via_app(fields):
    """app 直连写系统健康表（心跳时同步更新健康表）"""
    app_id = load_secret("FEISHU_APP_ID")
    app_secret = load_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        return None, "no app credentials"
    tr = get_token(app_id, app_secret)
    if tr.get("code") != 0:
        return None, "token_fail:" + str(tr.get("msg"))
    token = tr["tenant_access_token"]
    url = "https://open.feishu.cn/open-apis/bitable/v1/apps/%s/tables/%s/records" % (BASE, HEALTH_TABLE)
    req = urllib.request.Request(
        url,
        data=json.dumps({"fields": fields}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return True, "health_app_ok"
        return None, "health_app_code_%s:%s" % (resp.get("code"), resp.get("msg"))
    except Exception as e:
        return None, "health_app_err:" + str(e)[:100]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ms = int(datetime.datetime.now().timestamp() * 1000)  # 心跳时间字段存毫秒时间戳
    fields_app = {
        "来源": "TaskScheduler",
        "心跳时间": now_ms,
        "状态": "正常",  # select 单选字段用字符串
        "备注": f"heartbeat {now_str}",
    }
    fields_lark = {
        "来源": "TaskScheduler",
        "心跳时间": now_str,
        "状态": "正常",
        "备注": f"heartbeat {now_str}",
    }
    if args.dry_run:
        print("DRY_RUN ok, would write:", json.dumps(fields_app, ensure_ascii=False))
        sys.exit(0)

    ok, note = write_via_app(fields_app)
    if not ok:
        ok2, note2 = write_via_larkcli(fields_lark)
        if ok2:
            print("HEARTBEAT_OK (fallback lark-cli)")
        else:
            print("WRITE_FAIL", json.dumps({"app": note, "lark": note2}, ensure_ascii=False))
            sys.exit(1)
    else:
        print("HEARTBEAT_OK (app)")

    # V39修复：心跳时同步更新系统健康表（解决健康表6天未更新问题）
    # V41增强（2026-09-17）：补充"组件健康度/系统健康评分"字段——系统监控中心页面按此 Avg 渲染，
    # 缺值会导致页面显示 0.0/5.0、心跳 0%。正常心跳 = 组件健康度100 + 系统健康评分5.0。
    health_fields = {
        "检查项": "心跳-TaskScheduler",
        "实际状态": "正常",
        "最近检查时间": now_ms,  # datetime字段需要毫秒时间戳
        "处理状态": "正常",
        "类型": "心跳",
        "组件健康度": 100,
        "系统健康评分": 5.0,
    }
    h_ok, h_note = write_health_via_app(health_fields)
    if h_ok:
        print("HEALTH_UPDATE_OK")
    else:
        print("HEALTH_UPDATE_SKIP:", h_note)  # 健康表更新失败不影响心跳主流程


if __name__ == "__main__":
    main()
