#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""解析field-list原始JSON + 检查健康表/系统日志写入逻辑"""
import json
import os
import re

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)

print("=" * 70)
print("【1】系统事件日志表字段结构（原始JSON解析）")
print("=" * 70)
with open("field_list_raw.json", "r", encoding="utf-8") as f:
    content = f.read()
idx = content.find("{")
if idx >= 0:
    d = json.loads(content[idx:])
    fields = d.get("data", {}).get("fields", [])
    print(f"总字段数: {len(fields)}")
    log_type_field = None
    for f in fields:
        fname = f.get("field_name", "?")
        ftype = f.get("type", "?")
        ui_type = f.get("ui_type", "?")
        opts = f.get("property", {}).get("options", [])
        opt_names = [o.get("name", "") for o in opts] if opts else []
        print(f"  {fname} (type={ftype}, ui_type={ui_type})")
        if opt_names:
            print(f"    选项: {opt_names}")
        if "log" in fname.lower() or "类型" in fname:
            log_type_field = fname
            log_type_options = opt_names

print()
print("=" * 70)
print("【2】learning_system.py中write_system_log调用的log_type值")
print("=" * 70)
with open("learning_system.py", "r", encoding="utf-8") as f:
    content = f.read()
matches = re.findall(r'write_system_log\(\s*["\']([^"\']+)["\']', content)
log_types_used = sorted(set(matches))
print(f"使用的log_type值: {log_types_used}")
if log_type_field and log_type_options:
    mismatched = [lt for lt in log_types_used if lt not in log_type_options]
    if mismatched:
        print(f"⚠ 不在白名单的值: {mismatched}")
        print(f"  白名单: {log_type_options}")
    else:
        print("✓ 所有log_type值都在白名单中")

print()
print("=" * 70)
print("【3】system_logger.py内容（前50行）")
print("=" * 70)
if os.path.exists("system_logger.py"):
    with open("system_logger.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines[:50]):
        print(f"  {i+1}: {line.rstrip()}")
else:
    print("  system_logger.py不存在")

print()
print("=" * 70)
print("【4】v19_integration.py中健康表相关代码")
print("=" * 70)
with open("v19_integration.py", "r", encoding="utf-8") as f:
    v19_content = f.read()
# 查找健康表相关
health_matches = [(i+1, line.strip()) for i, line in enumerate(v19_content.split("\n"))
                  if any(k in line for k in ["tblxJMnd", "健康表", "health_table", "HEALTH_TABLE", "update_health", "write_health"])]
if health_matches:
    for lineno, line in health_matches[:15]:
        print(f"  行{lineno}: {line[:120]}")
else:
    print("  未找到健康表写入代码")

# 查找Watchdog类
print()
print("【5】v19_integration.py中Watchdog/ConsumeIndexHealthChecker类")
watchdog_matches = [(i+1, line.strip()) for i, line in enumerate(v19_content.split("\n"))
                    if "class " in line and any(k in line for k in ["Watchdog", "HealthChecker", "Health"])]
for lineno, line in watchdog_matches:
    print(f"  行{lineno}: {line}")

print()
print("=" * 70)
print("【6】run_maintenance_wrapper.py中是否更新健康表")
print("=" * 70)
with open("run_maintenance_wrapper.py", "r", encoding="utf-8") as f:
    maint_content = f.read()
if "tblxJMnd" in maint_content or "健康表" in maint_content:
    print("  ✓ 包含健康表更新")
else:
    print("  ✗ 不包含健康表更新（需要添加）")

print()
print("诊断完成")
