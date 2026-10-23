#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""daily_maintenance_cloud.py — V16 日常维护云端永续版（P0-A 恢复，2026-10-23）
GitHub Actions 云端运行：备份飞书多维表格核心 7 张表为 JSON -> backups/cloud_YYYYMMDD/，
由 workflow 的 upload-artifact 保存 30 天，实现"关机也可备份数据"。
零 npm/lark-cli 依赖：标准库 + 飞书 OpenAPI 直连（凭据走环境变量）。
用法：
  python daily_maintenance_cloud.py            # 云端全量备份
  python daily_maintenance_cloud.py --dry-run  # 只统计记录数并打印，不落盘（本地模拟验证）
"""
import os
import sys
import json
import urllib.request
from datetime import datetime

BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
APP_ID = os.environ.get("LARK_APP_ID", "")
APP_SECRET = os.environ.get("LARK_APP_SECRET", "")
TABLES = {
    "心跳": "tblJmm0ZIgqlYmyt",
    "事件日志": "tblPreh1ipB9LQpf",
    "任务表": "tblz3H4lV7PCrBrX",
    "学习卡片": "tblpLvxyYpDJgF92",
    "复习流水": "tblbznzCSpPhSz93",
    "洞察": "tblaqKBl87V9C0q1",
    "知识索引": "tbl0NiUFeQzH2r3n",
}
HOST = "https://open.feishu.cn/open-apis"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.path.join(SCRIPT_DIR, "..", "backups")
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


def main():
    if not (BASE_TOKEN and APP_ID and APP_SECRET):
        print("❌ 缺少 FEISHU_BASE_TOKEN / LARK_APP_ID / LARK_APP_SECRET 环境变量")
        sys.exit(2)

    tok = feishu_token()
    stamp = datetime.now().strftime("%Y%m%d")
    out_dir = os.path.join(BACKUP_ROOT, f"cloud_{stamp}")
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    report = []
    for name, table_id in TABLES.items():
        try:
            recs = list_all_records(tok, table_id)
            total += len(recs)
            if not DRY_RUN:
                fp = os.path.join(out_dir, f"{name}.json")
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(recs, f, ensure_ascii=False, indent=1)
                report.append(f"  {name}: {len(recs)} 条 -> {os.path.relpath(fp, BACKUP_ROOT)}")
            else:
                report.append(f"  {name}: {len(recs)} 条（DRY-RUN 不落盘）")
        except Exception as e:
            report.append(f"  {name}: ❌ {e}")
            print(f"[FAIL] {name}: {e}")

    print(f"云端维护备份 {stamp}：共 {len(TABLES)} 张表 / {total} 条记录")
    print("\n".join(report))
    sys.exit(0)


if __name__ == "__main__":
    main()
