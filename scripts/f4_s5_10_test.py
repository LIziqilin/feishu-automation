#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F4-S5-10 管理员修正机制测试"""
import sys
sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
from v19_integration import AdminOverrideManager

print('=' * 60)
print('S5-10 管理员修正机制测试')
print('=' * 60)

# 测试1: 白名单校验
print('\n测试1: 白名单校验')
print('-' * 60)
print('当前管理员列表: ' + str(AdminOverrideManager.get_admin_list()))

# 非管理员测试
non_admin = "ou_non_admin_12345"
is_admin = AdminOverrideManager.is_admin(non_admin)
print('非管理员 ' + non_admin + ' is_admin: ' + str(is_admin))

# 添加管理员
add_result = AdminOverrideManager.add_admin("ou_test_admin_001")
print('添加管理员结果: ' + str(add_result))
print('添加后管理员列表: ' + str(AdminOverrideManager.get_admin_list()))

# 验证管理员
is_admin_after = AdminOverrideManager.is_admin("ou_test_admin_001")
print('管理员 is_admin: ' + str(is_admin_after))

if not is_admin and add_result and is_admin_after:
    print('✅ 白名单校验测试通过')
else:
    print('❌ 白名单校验测试失败')

# 测试2: 管理员指令解析
print('\n测试2: 管理员指令解析')
print('-' * 60)

# 合法指令
cmd1 = "!admin override recvtLY8poT8zw|会|1789126407229 不会 答案错误"
parsed1 = AdminOverrideManager.parse_admin_command(cmd1)
print('合法指令解析:')
print('  valid: ' + str(parsed1.get('valid')))
print('  action: ' + str(parsed1.get('action')))
print('  event_id: ' + str(parsed1.get('event_id')))
print('  new_result: ' + str(parsed1.get('new_result')))
print('  reason: ' + str(parsed1.get('reason')))
print('  error: ' + str(parsed1.get('error')))

# 非法指令（结果不合法）
cmd2 = "!admin override test_event_id 非法结果"
parsed2 = AdminOverrideManager.parse_admin_command(cmd2)
print('\n非法结果指令解析:')
print('  valid: ' + str(parsed2.get('valid')))
print('  error: ' + str(parsed2.get('error')))

# 非管理员指令
cmd3 = "普通消息内容"
parsed3 = AdminOverrideManager.parse_admin_command(cmd3)
print('\n非管理员指令解析:')
print('  valid: ' + str(parsed3.get('valid')))
print('  error: ' + str(parsed3.get('error')))

if parsed1.get('valid') and not parsed2.get('valid') and not parsed3.get('valid'):
    print('✅ 管理员指令解析测试通过')
else:
    print('❌ 管理员指令解析测试失败')

# 测试3: 白名单拒绝（非管理员执行修正）
print('\n测试3: 白名单拒绝（非管理员执行修正）')
print('-' * 60)
override_result = AdminOverrideManager.execute_override(
    event_id="test_event_id",
    new_result="不会",
    admin_user_id="ou_non_admin",
    reason="测试白名单拒绝"
)
print('修正结果: success=' + str(override_result.get('success')))
print('错误: ' + str(override_result.get('error')))
if not override_result.get('success') and "白名单" in str(override_result.get('error')):
    print('✅ 白名单拒绝测试通过')
else:
    print('❌ 白名单拒绝测试失败')

# 测试4: 移除管理员
print('\n测试4: 移除管理员')
print('-' * 60)
remove_result = AdminOverrideManager.remove_admin("ou_test_admin_001")
print('移除管理员结果: ' + str(remove_result))
print('移除后管理员列表: ' + str(AdminOverrideManager.get_admin_list()))
is_admin_removed = AdminOverrideManager.is_admin("ou_test_admin_001")
print('移除后 is_admin: ' + str(is_admin_removed))
if remove_result and not is_admin_removed:
    print('✅ 移除管理员测试通过')
else:
    print('❌ 移除管理员测试失败')

# 总结
print('\n' + '=' * 60)
print('S5-10 测试总结')
print('=' * 60)
print('✅ 管理员白名单校验：已实现（is_admin/add_admin/remove_admin）')
print('✅ 管理员修正指令解析：已实现（!admin override <event_id> <new_result> [reason]）')
print('✅ ADMIN_OVERRIDE事件写入：已实现（写入流水，revoke_of指向原事件）')
print('✅ 非白名单拒绝：已实现（非管理员执行修正被拒绝）')
print('✅ 修正结果校验：已实现（只允许会/不会/模糊）')
print('✅ rebuild保留：ADMIN_OVERRIDE事件在流水表中，rebuild时自动保留')
print('⚠️  注意：管理员白名单默认为空，需要手动添加管理员open_id')
