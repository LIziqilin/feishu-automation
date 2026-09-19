#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""获取流水表来源字段选项"""
import json
import subprocess

result = subprocess.run([
    'lark-cli', 'base', '+field-list',
    '--base-token', 'X8N1bvN3na99dFsyu0gcU8zTnHf',
    '--table-id', 'tblbznzCSpPhSz93',
    '--as', 'user', '--format', 'json'
], capture_output=True, text=True, cwd=r'D:\AI-Tools\feishu\V13方案增强\scripts')

data = json.loads(result.stdout)
for field in data['data']['fields']:
    if field['name'] == '来源':
        print('来源字段选项:')
        for opt in field.get('options', []):
            print('  - ' + opt['name'])
        print('总选项数: ' + str(len(field.get('options', []))))
