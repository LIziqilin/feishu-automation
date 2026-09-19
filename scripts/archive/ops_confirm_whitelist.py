#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""确认log_type白名单 + 检查Watchdog/健康表逻辑 + 修复方案"""
import subprocess
import json
import os
import sys

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
LOG_TABLE = "tblPreh1ipB9LQpf"

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        return -1, "", str(e)

print("=" * 70)
print("【1】系统事件日志表现有记录的log_type分布")
print("=" * 70)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", LOG_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
log_type_dist = {}
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    print(f"总记录数: {len(rows)}")
    print(f"字段名: {fields}")
    # 找到log_type字段的索引
    log_type_idx = None
    for i, f in enumerate(fields):
        if "log" in f.lower() or "类型" in f or "type" in f.lower():
            log_type_idx = i
            print(f"log_type字段索引: {i}, 字段名: {f}")
            break
    if log_type_idx is not None:
        for row in rows:
            lt = row[log_type_idx]
            if isinstance(lt, list):
                lt = lt[0] if lt else "空"
            log_type_dist[lt] = log_type_dist.get(lt, 0) + 1
        print(f"log_type分布: {log_type_dist}")
except Exception as e:
    print(f"解析失败: {e}")
    print(f"stdout前500字: {stdout[:500]}")

print()
print("=" * 70)
print("【2】尝试写入不同log_type值，确认白名单")
print("=" * 70)
test_types = ["SYSTEM", "ERROR", "WARN", "SECURITY", "INSTRUCTION", "DEBUG", "INFO", "AUDIT"]
for lt in test_types:
    test_data = {
        "log_type": [lt],
        "message": f"V39白名单测试-{lt}",
        "severity": ["INFO"],
        "source": ["test"],
        "detail": f"测试log_type={lt}",
        "timestamp": "2026-09-14 11:20:00",
        "resolved": False,
    }
    tmp_file = os.path.join(scripts_dir, f"tmp_log_test_{lt}.json")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False)
    cmd = [LARK, "base", "+record-upsert", "--base-token", BASE,
           "--table-id", LOG_TABLE, "--as", "user", "--json", f"@{tmp_file}"]
    code, stdout, stderr = run_cmd(cmd, timeout=30)
    try:
        resp = json.loads(stdout)
        ok = resp.get("ok", False)
        if ok:
            print(f"  ✓ {lt}: 写入成功")
        else:
            err = resp.get("error", {})
            print(f"  ✗ {lt}: 写入失败 - {err.get('type','?')}/{err.get('subtype','?')}: {str(err.get('msg',''))[:80]}")
    except:
        print(f"  ? {lt}: 解析失败 - {stdout[:100]}")
    # 清理临时文件
    try:
        os.remove(tmp_file)
    except:
        pass

print()
print("=" * 70)
print("【3】v19_integration.py Watchdog类（行3883附近）")
print("=" * 70)
with open("v19_integration.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(3882, min(3920, len(lines))):
    print(f"  {i+1}: {lines[i].rstrip()}")

print()
print("=" * 70)
print("【4】v19_integration.py中SYSTEM_HEALTH_TABLE使用")
print("=" * 70)
for i, line in enumerate(lines):
    if "SYSTEM_HEALTH_TABLE" in line or "update_health" in line or "write_health" in line or "health_check" in line:
        print(f"  行{i+1}: {line.strip()[:120]}")

print()
print("诊断完成")
