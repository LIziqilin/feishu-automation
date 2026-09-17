#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深度排查心跳表：查询全部记录+手动写入验证+检查app直连"""
import subprocess, json, os, sys, datetime

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
HEARTBEAT_TABLE = "tblJmm0ZIgqlYmyt"

print("=" * 60)
print("【1】心跳表全部记录（按时间倒序）")
print("=" * 60)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", HEARTBEAT_TABLE, "--as", "user",
       "--limit", "50", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    print(f"  总记录数: {len(rows)}")
    print(f"  字段: {fields}")
    # 按心跳时间排序
    def get_time(row):
        rec = dict(zip(fields, row))
        t = rec.get("心跳时间", "")
        return str(t)
    rows_sorted = sorted(rows, key=get_time, reverse=True)
    for i, row in enumerate(rows_sorted[:10]):
        rec = dict(zip(fields, row))
        print(f"  {i+1}. 时间={rec.get('心跳时间')}, 来源={rec.get('来源')}, 状态={rec.get('状态')}, 备注={rec.get('备注')}")
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {r.stdout[:500]}")

print()
print("=" * 60)
print("【2】手动用lark-cli写入一条心跳记录")
print("=" * 60)
now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
fields = {
    "来源": "ManualFix",
    "心跳时间": now_str,
    "状态": "正常",
    "备注": f"手动修复心跳 {now_str}"
}
cmd = [LARK, "base", "+record-upsert", "--base-token", BASE,
       "--table-id", HEARTBEAT_TABLE, "--as", "user",
       "--json", json.dumps(fields, ensure_ascii=False), "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
print(f"  退出码: {r.returncode}")
stdout = r.stdout.decode("utf-8", errors="replace")
stderr = r.stderr.decode("utf-8", errors="replace")
if stdout:
    print(f"  stdout: {stdout[:500]}")
if stderr:
    print(f"  stderr: {stderr[:500]}")

print()
print("=" * 60)
print("【3】验证心跳表是否更新（查询最近3条）")
print("=" * 60)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", HEARTBEAT_TABLE, "--as", "user",
       "--limit", "3", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    fields = d["data"]["fields"]
    for row in d["data"]["data"]:
        rec = dict(zip(fields, row))
        print(f"  时间={rec.get('心跳时间')}, 来源={rec.get('来源')}, 备注={rec.get('备注')}")
except Exception as e:
    print(f"  解析失败: {e}")

print()
print("=" * 60)
print("【4】检查heartbeat.py的app凭证是否存在")
print("=" * 60)
env_candidates = [
    r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env",
    r"D:\AI-Tools\feishu\飞书高阶用法\feishu_insight_link.env",
    os.path.join(scripts_dir, "feishu_insight_link.env"),
]
for p in env_candidates:
    exists = os.path.exists(p)
    print(f"  {'✓' if exists else '✗'} {p}")
    if exists:
        try:
            with open(p, encoding="utf-8-sig") as f:
                content = f.read()
            has_app_id = "FEISHU_APP_ID" in content
            has_app_secret = "FEISHU_APP_SECRET" in content
            print(f"    FEISHU_APP_ID: {'存在' if has_app_id else '缺失'}")
            print(f"    FEISHU_APP_SECRET: {'存在' if has_app_secret else '缺失'}")
        except Exception as e:
            print(f"    读取失败: {e}")
