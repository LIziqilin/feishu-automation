#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试source/severity白名单 + 确认测试记录写入"""
import json
import subprocess
import os

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
TABLE = "tblPreh1ipB9LQpf"

def write_log(log_type, severity, source, message):
    data = {
        "log_type": [log_type],
        "message": message,
        "severity": [severity],
        "source": [source],
        "detail": "V39白名单测试",
        "timestamp": "2026-09-14 11:35:00",
        "resolved": False,
    }
    fname = "tmp_log_test.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    r = subprocess.run(
        [LARK, "base", "+record-upsert", "--base-token", BASE,
         "--table-id", TABLE, "--as", "user", "--json", "@" + fname],
        capture_output=True, timeout=30
    )
    try:
        os.remove(fname)
    except:
        pass
    try:
        resp = json.loads(r.stdout.decode("utf-8", errors="replace"))
        return resp.get("ok", False), resp.get("error", {}), resp.get("data", {})
    except:
        return False, {"message": r.stdout[:200]}, {}

print("=" * 70)
print("【1】测试source字段白名单")
print("=" * 70)
sources = ["system", "user", "admin_override", "parser", "derive", "credential", "test", "unknown_source_xyz"]
for src in sources:
    ok, err, data = write_log("INSTRUCTION", "INFO", src, "V39-source测试-" + src)
    if ok:
        rid = data.get("record_id", "")
        print("  OK   " + src + " (record_id=" + rid + ")")
    else:
        print("  FAIL " + src + ": " + str(err.get("message", ""))[:100])

print()
print("=" * 70)
print("【2】测试severity字段白名单")
print("=" * 70)
severities = ["INFO", "WARN", "ERROR", "DEBUG", "CRITICAL", "UNKNOWN"]
for sev in severities:
    ok, err, data = write_log("INSTRUCTION", sev, "test", "V39-severity测试-" + sev)
    if ok:
        rid = data.get("record_id", "")
        print("  OK   " + sev + " (record_id=" + rid + ")")
    else:
        print("  FAIL " + sev + ": " + str(err.get("message", ""))[:100])

print()
print("=" * 70)
print("【3】查询最近10条记录，确认测试记录是否写入")
print("=" * 70)
r = subprocess.run(
    [LARK, "base", "+record-list", "--base-token", BASE,
     "--table-id", TABLE, "--as", "user", "--limit", "10", "--format", "json"],
    capture_output=True, timeout=30
)
try:
    d = json.loads(r.stdout.decode("utf-8", errors="replace"))
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    print("字段: " + str(fields))
    for i, row in enumerate(rows[:10]):
        rec = dict(zip(fields, row))
        msg = str(rec.get("message", ""))[:60]
        lt = rec.get("log_type", "")
        src = rec.get("source", "")
        sev = rec.get("severity", "")
        print("  " + str(i+1) + ". log_type=" + str(lt) + ", severity=" + str(sev) + ", source=" + str(src) + ", msg=" + msg)
except Exception as e:
    print("解析失败: " + str(e))
    print("stdout: " + r.stdout[:300])

print()
print("测试完成")
