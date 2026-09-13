#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5-10 管理员修正+白名单单元级验证（使用mock，不影响生产数据）"""
import sys
import os
import json
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S5-10 管理员修正+白名单单元级验证 ═══')
print()

# 导入AdminOverrideManager
try:
    from v19_integration import AdminOverrideManager
    print('【1 AdminOverrideManager导入成功】')
except Exception as e:
    print(f'【1 AdminOverrideManager导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法
print()
print('【2 关键方法检查】')
methods = ['is_admin', 'add_admin', 'remove_admin', 'parse_admin_command', 'execute_override', 'get_admin_list']
for method in methods:
    if hasattr(AdminOverrideManager, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

# 检查白名单配置
print()
print('【3 白名单配置检查】')
whitelist = AdminOverrideManager.get_admin_list()
print(f'  当前白名单管理员数: {len(whitelist)}')
print(f'  白名单内容: {whitelist}')
print(f'  ALLOWED_RESULTS: {AdminOverrideManager.ALLOWED_RESULTS}')

# 测试白名单校验
print()
print('【4 白名单校验测试】')
# 非白名单用户
non_admin_id = "ou_non_admin_12345"
is_non_admin = AdminOverrideManager.is_admin(non_admin_id)
print(f'  非白名单用户 {non_admin_id}: is_admin={is_non_admin}')
assert not is_non_admin, "非白名单用户应返回False"
print('  → 非白名单用户被正确拒绝 ✅')

# 添加管理员
admin_id = "ou_admin_test_12345"
AdminOverrideManager.add_admin(admin_id)
is_admin = AdminOverrideManager.is_admin(admin_id)
print(f'  添加管理员 {admin_id}: is_admin={is_admin}')
assert is_admin, "添加后应返回True"
print('  → 管理员添加成功，白名单校验通过 ✅')

# 移除管理员
AdminOverrideManager.remove_admin(admin_id)
is_admin_after_remove = AdminOverrideManager.is_admin(admin_id)
print(f'  移除管理员 {admin_id}: is_admin={is_admin_after_remove}')
assert not is_admin_after_remove, "移除后应返回False"
print('  → 管理员移除成功 ✅')

# 测试指令解析
print()
print('【5 指令解析测试】')
# 正常指令
cmd1 = "!admin override evt_001 会 修正错误"
result1 = AdminOverrideManager.parse_admin_command(cmd1)
print(f'  指令1: {cmd1}')
print(f'    valid={result1["valid"]}, action={result1["action"]}, event_id={result1["event_id"]}, new_result={result1["new_result"]}, reason={result1["reason"]}')
assert result1["valid"] and result1["action"] == "override" and result1["event_id"] == "evt_001" and result1["new_result"] == "会"
print('  → 正常指令解析正确 ✅')

# 缺少参数
cmd2 = "!admin override evt_001"
result2 = AdminOverrideManager.parse_admin_command(cmd2)
print(f'  指令2（缺少参数）: {cmd2}')
print(f'    valid={result2["valid"]}, error={result2["error"]}')
assert not result2["valid"]
print('  → 缺少参数正确报错 ✅')

# 不合法结果
cmd3 = "!admin override evt_001 无效结果"
result3 = AdminOverrideManager.parse_admin_command(cmd3)
print(f'  指令3（不合法结果）: {cmd3}')
print(f'    valid={result3["valid"]}, error={result3["error"]}')
assert not result3["valid"]
print('  → 不合法结果正确报错 ✅')

# 非管理员指令
cmd4 = "普通消息"
result4 = AdminOverrideManager.parse_admin_command(cmd4)
print(f'  指令4（非管理员指令）: {cmd4}')
print(f'    valid={result4["valid"]}, error={result4["error"]}')
assert not result4["valid"]
print('  → 非管理员指令正确识别 ✅')

# 测试execute_override白名单拒绝（使用mock）
print()
print('【6 execute_override白名单拒绝测试】')
# 非白名单用户执行修正
with patch('v19_integration.run_cmd') as mock_run_cmd:
    result = AdminOverrideManager.execute_override(
        event_id="evt_test_001",
        new_result="会",
        admin_user_id="ou_non_admin_12345",
        reason="测试修正"
    )
    print(f'  非白名单用户执行修正: success={result["success"]}, error={result["error"]}')
    assert not result["success"] and "白名单" in result["error"]
    print('  → 非白名单用户被正确拒绝（安全红线）✅')
    # 确认没有调用lark-cli（没有写入流水）
    assert not mock_run_cmd.called, "非白名单用户不应调用lark-cli"
    print('  → 非白名单用户没有写入流水（安全红线）✅')

# 测试execute_override查找原记录和写入ADMIN_OVERRIDE流水（使用mock）
print()
print('【7 execute_override执行修正测试（mock）】')
# 添加测试管理员
AdminOverrideManager.add_admin("ou_admin_mock_12345")

# 模拟流水表返回数据
mock_records = [
    ["evt_test_001", "rec_card_001", "测试卡片", "会", "2026-09-13T10:00:00", False, "", "", "", "", "", "", "", "", ""]
]
mock_fields = ["event_id", "卡片ID", "卡片标题", "结果", "客户端时间戳", "superseded", "revoke_of", "错因", "来源", "event_type", "revision", "untrusted", "record_hash", "卡片问题正面", "自然日"]
mock_record_ids = ["rec_flow_001"]
mock_response = json.dumps({
    "code": 0,
    "data": {
        "fields": mock_fields,
        "data": mock_records,
        "record_id_list": mock_record_ids
    }
})

with patch('v19_integration.run_cmd') as mock_run_cmd:
    # 第一次调用：查找原记录
    # 第二次调用：写入ADMIN_OVERRIDE流水
    mock_run_cmd.side_effect = [
        (True, mock_response, ""),  # 查找原记录成功
        (True, '{"code":0,"data":{"record":{"record_id_list":["rec_flow_admin_001"]}}}', "")  # 写入成功
    ]
    
    result = AdminOverrideManager.execute_override(
        event_id="evt_test_001",
        new_result="不会",
        admin_user_id="ou_admin_mock_12345",
        reason="测试修正为不会"
    )
    
    print(f'  管理员执行修正: success={result["success"]}')
    print(f'  new_event_id: {result.get("new_event_id", "N/A")}')
    print(f'  original_found: {result.get("original_found", "N/A")}')
    print(f'  error: {result.get("error", "N/A")}')
    
    assert result["success"], "管理员修正应成功"
    assert result["original_found"], "应找到原记录"
    assert "ADMIN_OVERRIDE" in result["new_event_id"], "新event_id应包含ADMIN_OVERRIDE"
    print('  → 管理员修正执行成功，ADMIN_OVERRIDE流水写入 ✅')
    
    # 确认调用了两次lark-cli（查找+写入）
    assert mock_run_cmd.call_count == 2, f"应调用2次lark-cli，实际{mock_run_cmd.call_count}次"
    print('  → 调用了2次lark-cli（查找原记录+写入ADMIN_OVERRIDE流水）✅')

# 移除测试管理员
AdminOverrideManager.remove_admin("ou_admin_mock_12345")

# 测试rebuild后ADMIN_OVERRIDE保留（mark_superseded_same_day排除ADMIN_OVERRIDE）
print()
print('【8 rebuild后ADMIN_OVERRIDE保留检查】')
try:
    import inspect
    # 读取learning_system.py中的mark_superseded_same_day函数
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查mark_superseded_same_day是否排除ADMIN_OVERRIDE
    has_valid_answer = 'valid_answer_results' in content
    has_admin_override_excluded = '"会", "不会", "模糊"' in content or "'会', '不会', '模糊'" in content
    
    print(f'  mark_superseded_same_day包含valid_answer_results: {has_valid_answer}')
    print(f'  排除ADMIN_OVERRIDE（只保留会/不会/模糊）: {has_admin_override_excluded}')
    
    if has_valid_answer and has_admin_override_excluded:
        print('  → mark_superseded_same_day排除ADMIN_OVERRIDE，rebuild后保留 ✅')
    else:
        print('  → mark_superseded_same_day可能未排除ADMIN_OVERRIDE ⚠️')
except Exception as e:
    print(f'  检查失败: {e}')

# 测试!admin指令已接线到learning_system.py
print()
print('【9 !admin指令接线检查】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    has_admin_import = 'AdminOverrideManager' in content
    has_admin_command = 'text.startswith("!admin")' in content or "text.startswith('!admin')" in content
    has_whitelist_check = 'AdminOverrideManager.is_admin' in content
    has_reject_msg = '权限拒绝' in content or '白名单' in content
    has_execute = 'AdminOverrideManager.execute_override' in content
    
    print(f'  导入AdminOverrideManager: {has_admin_import}')
    print(f'  识别!admin指令: {has_admin_command}')
    print(f'  白名单校验: {has_whitelist_check}')
    print(f'  非白名单拒绝消息: {has_reject_msg}')
    print(f'  执行修正: {has_execute}')
    
    if all([has_admin_import, has_admin_command, has_whitelist_check, has_reject_msg, has_execute]):
        print('  → !admin指令已完整接线到消息处理流程 ✅')
    else:
        print('  → !admin指令接线不完整 ⚠️')
except Exception as e:
    print(f'  检查失败: {e}')

print()
print('═══ 单元级验证完成 ═══')
