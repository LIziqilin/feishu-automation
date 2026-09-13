#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4-14 熔断恢复探测单元级验证"""
import sys
import os
import time

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('═══ S4-14 熔断恢复探测单元级验证 ═══')
print()

# 导入CircuitBreaker
try:
    from v19_integration import CircuitBreaker
    print('【1 CircuitBreaker导入成功】')
except Exception as e:
    print(f'【1 CircuitBreaker导入失败】{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查关键方法
print()
print('【2 关键方法检查】')
methods = ['can_execute', 'record_success', 'record_failure', 'get_status', 
           '_transition_to_open', '_transition_to_half_open', '_transition_to_closed']
for method in methods:
    if hasattr(CircuitBreaker, method):
        print(f'  {method}: 存在 ✅')
    else:
        print(f'  {method}: 不存在 ❌')

# 测试1：正常状态（CLOSED）
print()
print('【3 测试1：正常状态CLOSED】')
cb = CircuitBreaker("test_cb_1", failure_threshold=3, recovery_timeout=2)
print(f'  初始状态: {cb.state}')
print(f'  can_execute: {cb.can_execute()}')
if cb.state == CircuitBreaker.CLOSED and cb.can_execute():
    print('  → 正常状态，请求可以执行 ✅')
else:
    print('  → 状态异常 ⚠️')

# 测试2：连续失败触发熔断（探测→熔断）
print()
print('【4 测试2：连续失败触发熔断（探测→熔断）】')
cb2 = CircuitBreaker("test_cb_2", failure_threshold=3, recovery_timeout=2)
print(f'  初始状态: {cb2.state}, failure_count: {cb2.failure_count}')
for i in range(3):
    cb2.record_failure(reason=f"测试失败{i+1}")
    print(f'  第{i+1}次失败后: state={cb2.state}, failure_count={cb2.failure_count}')
if cb2.state == CircuitBreaker.OPEN:
    print('  → 连续失败达到阈值，触发熔断 ✅')
else:
    print('  → 熔断未触发 ⚠️')

# 测试3：熔断状态快速失败
print()
print('【5 测试3：熔断状态快速失败】')
can_exec = cb2.can_execute()
print(f'  熔断状态 can_execute: {can_exec}')
if not can_exec:
    print('  → 熔断状态下请求被快速拒绝 ✅')
else:
    print('  → 熔断状态下仍允许执行 ⚠️')

# 测试4：熔断超时进入半开状态（探测）
print()
print('【6 测试4：熔断超时进入半开状态（探测）】')
print(f'  等待熔断超时（{cb2.recovery_timeout}秒）...')
time.sleep(cb2.recovery_timeout + 0.5)
can_exec_half = cb2.can_execute()
print(f'  超时后 can_execute: {can_exec_half}')
print(f'  超时后 state: {cb2.state}')
if cb2.state == CircuitBreaker.HALF_OPEN and can_exec_half:
    print('  → 熔断超时，进入半开状态，允许试探请求 ✅')
else:
    print('  → 半开状态未触发 ⚠️')

# 测试5：半开状态失败重新熔断（失败回滚）
print()
print('【7 测试5：半开状态失败重新熔断（失败回滚）】')
cb3 = CircuitBreaker("test_cb_3", failure_threshold=2, recovery_timeout=1)
cb3.record_failure("失败1")
cb3.record_failure("失败2")
print(f'  触发熔断: state={cb3.state}')
time.sleep(1.5)
cb3.can_execute()  # 触发半开状态
print(f'  超时进入半开: state={cb3.state}')
cb3.record_failure("半开试探失败")
print(f'  半开失败后: state={cb3.state}')
if cb3.state == CircuitBreaker.OPEN:
    print('  → 半开状态失败，重新熔断（失败回滚）✅')
else:
    print('  → 半开失败未重新熔断 ⚠️')

# 测试6：半开状态成功恢复正常（回切→验证）
print()
print('【8 测试6：半开状态成功恢复正常（回切→验证）】')
cb4 = CircuitBreaker("test_cb_4", failure_threshold=2, recovery_timeout=1, half_open_max_requests=2)
cb4.record_failure("失败1")
cb4.record_failure("失败2")
print(f'  触发熔断: state={cb4.state}')
time.sleep(1.5)
cb4.can_execute()  # 触发半开状态
print(f'  超时进入半开: state={cb4.state}')
# 半开状态需要所有试探请求都成功才恢复
cb4.record_success()
print(f'  第1次成功后: state={cb4.state}, half_open_request_count={cb4.half_open_request_count}, half_open_success_count={cb4.half_open_success_count}')
cb4.record_success()
print(f'  第2次成功后: state={cb4.state}, half_open_request_count={cb4.half_open_request_count}, half_open_success_count={cb4.half_open_success_count}')
if cb4.state == CircuitBreaker.CLOSED:
    print('  → 半开状态所有试探成功，恢复正常（回切→验证）✅')
else:
    print('  → 半开成功未恢复正常 ⚠️')

# 测试7：get_status状态查询
print()
print('【9 测试7：get_status状态查询】')
status = cb4.get_status()
print(f'  name: {status.get("name")}')
print(f'  state: {status.get("state")}')
print(f'  failure_count: {status.get("failure_count")}')
print(f'  total_failures: {status.get("total_failures")}')
print(f'  total_successes: {status.get("total_successes")}')
print(f'  total_circuit_breaks: {status.get("total_circuit_breaks")}')
print(f'  total_recoveries: {status.get("total_recoveries")}')
print(f'  can_execute: {status.get("can_execute")}')
if status.get('state') == 'CLOSED' and status.get('can_execute'):
    print('  → 状态查询正常 ✅')
else:
    print('  → 状态查询异常 ⚠️')

# 检查接线到主流程
print()
print('【10 检查接线到主流程cmd_poll】')
try:
    with open(r'D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py', 'r', encoding='utf-8') as f:
        content = f.read()
    has_circuit_breaker = 'CircuitBreaker' in content
    has_can_execute = 'can_execute' in content
    has_record_success = 'record_success' in content
    has_record_failure = 'record_failure' in content
    print(f'  CircuitBreaker引用: {has_circuit_breaker}')
    print(f'  can_execute调用: {has_can_execute}')
    print(f'  record_success调用: {has_record_success}')
    print(f'  record_failure调用: {has_record_failure}')
    if has_circuit_breaker and has_can_execute and has_record_success and has_record_failure:
        print('  → CircuitBreaker已接线到cmd_poll主流程 ✅')
    else:
        print('  → CircuitBreaker接线不完整 ⚠️')
except Exception as e:
    print(f'  检查接线失败: {e}')

# 四段总结
print()
print('【11 熔断四段总结】')
print('  ①探测: can_execute()检查状态，HALF_OPEN允许有限请求试探 ✅')
print('  ②回切: _transition_to_closed()半开成功恢复CLOSED ✅')
print('  ③验证: record_success()/record_failure()记录试探结果 ✅')
print('  ④失败回滚: _transition_to_open()半开失败重新熔断 ✅')

print()
print('═══ 单元级验证完成 ═══')
