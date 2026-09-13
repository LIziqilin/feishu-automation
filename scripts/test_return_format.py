#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试record-upsert返回格式并清理测试数据"""
import sys
import json
import subprocess
import os

sys.path.insert(0, r'D:\AI-Tools\feishu\V13方案增强\scripts')
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

print('=== 测试record-upsert返回格式 ===')
print()

# 创建测试JSON
test_data = {
    "洞察标题": "测试返回格式-请删除",
    "洞察内容": "测试内容",
    "AI摘要": "测试摘要",
    "标签": ["其他"],
    "关联科目": ["通用知识"],
    "洞察类型": ["学习洞察"],
    "状态": ["待整理"],
    "沉淀状态": ["未沉淀"],
    "洞察日期": 1757700000000,
    "创建日期": 1757700000000
}

with open('test_return_format.json', 'w', encoding='utf-8') as f:
    json.dump(test_data, f, ensure_ascii=False)

# 执行record-upsert
cmd = ['lark-cli', 'base', '+record-upsert',
       '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
       '--table-id', 'tblaqKBl87V9C0q1',
       '--as', 'user',
       '--json', '@test_return_format.json',
       '--format', 'json']

proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
print(f'退出码: {proc.returncode}')
print(f'stdout: {proc.stdout[:1000]}')
print(f'stderr: {proc.stderr[:500]}')
print()

# 解析返回
if proc.returncode == 0:
    try:
        resp = json.loads(proc.stdout)
        print('返回结构:')
        print(json.dumps(resp, indent=2, ensure_ascii=False)[:1500])
        print()
        
        # 尝试不同路径获取record_id
        print('尝试获取record_id:')
        print(f'  data.record_id_list: {resp.get("data", {}).get("record_id_list")}')
        print(f'  data.record.record_id_list: {resp.get("data", {}).get("record", {}).get("record_id_list")}')
        print(f'  data.records: {resp.get("data", {}).get("records")}')
        
        # 获取record_id用于清理
        record_id = None
        if 'record_id_list' in resp.get('data', {}):
            record_id = resp['data']['record_id_list'][0] if resp['data']['record_id_list'] else None
        elif 'record' in resp.get('data', {}):
            record_id = resp['data']['record'].get('record_id_list', [None])[0]
        
        if record_id:
            print(f'\n获取到record_id: {record_id}')
            print('清理测试数据...')
            delete_cmd = ['lark-cli', 'base', '+record-delete',
                          '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
                          '--table-id', 'tblaqKBl87V9C0q1',
                          '--record-id', record_id,
                          '--as', 'user', '--yes']
            del_proc = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=30)
            print(f'删除退出码: {del_proc.returncode}')
            print(f'删除stdout: {del_proc.stdout[:300]}')
    except Exception as e:
        print(f'解析失败: {e}')

# 清理临时文件
if os.path.exists('test_return_format.json'):
    os.remove('test_return_format.json')

print()
print('=== 测试完成 ===')
