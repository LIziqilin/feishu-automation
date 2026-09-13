#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清理残留的TEST表"""
import subprocess, json, os, sys
os.chdir(r'D:\AI-Tools\feishu\V13方案增强\scripts')

cmd = ['lark-cli', 'base', '+table-list', '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf', '--as', 'user', '--format', 'json']
r = subprocess.run(' '.join(cmd), capture_output=True, shell=True)
data = json.loads(r.stdout)
items = data.get('data', {}).get('items', [])
print('表数量:', len(items))
for t in items:
    name = t.get('name', '')
    if 'TEST' in name:
        tid = t.get('table_id', '')
        print('删除残留:', tid, '|', name)
        del_cmd = ['lark-cli', 'base', '+table-delete', '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf', '--table-id', tid, '--as', 'user', '--yes']
        subprocess.run(' '.join(del_cmd), capture_output=True, shell=True)
print('清理完成')
