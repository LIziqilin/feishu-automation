#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试log_type白名单"""
import json
import subprocess
import os

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
TABLE = "tblPreh1ipB9LQpf"

test_types = ["SYSTEM", "ERROR", "WARN", "SECURITY", "INSTRUCTION", "DEBUG", "AUDIT"]
results = {}

for lt in test_types:
    data = {
        "log_type": [lt],
        "message": "V39白名单测试-" + lt,
        "severity": ["INFO"],
        "source": ["test"],
        "detail": "测试",
        "timestamp": "2026-09-14 11:30:00",
        "resolved": False,
    }
    fname = "tmp_log_" + lt + ".json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    r = subprocess.run(
        [LARK, "base", "+record-upsert", "--base-token", BASE,
         "--table-id", TABLE, "--as", "user", "--json", "@" + fname],
        capture_output=True, timeout=30
    )
    try:
        resp = json.loads(r.stdout.decode("utf-8", errors="replace"))
        ok = resp.get("ok", False)
        if ok:
            rid = resp.get("data", {}).get("record_id", "")
            print("  OK  " + lt + ": 写入成功 record_id=" + rid)
            results[lt] = "OK"
        else:
            err = resp.get("error", {})
            msg = str(err.get("message", ""))[:120]
            print("  FAIL " + lt + ": " + err.get("type", "") + "/" + err.get("subtype", "") + ": " + msg)
            results[lt] = "FAIL: " + msg
    except Exception as e:
        print("  ERR  " + lt + ": 解析失败 " + str(e))
        results[lt] = "ERR"
    try:
        os.remove(fname)
    except:
        pass

print()
print("白名单测试结果:")
for lt, res in results.items():
    print("  " + lt + ": " + res)
