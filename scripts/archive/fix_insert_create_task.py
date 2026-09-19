#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在requery处理后增加create_task处理"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 elif action == "requery": 这一行，在它对应的代码块结束后插入create_task
found_requery = False
insert_after = -1
for i, line in enumerate(lines):
    if 'elif action == "requery":' in line:
        found_requery = True
        print(f'找到requery在第{i+1}行')
        # 找这个代码块结束的位置（下一个elif或同级缩进的行）
        indent = len(line) - len(line.lstrip())
        for j in range(i+1, min(i+20, len(lines))):
            next_line = lines[j]
            # 如果下一行是同级缩进的elif/else，说明requery块结束了
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 999
            if next_indent == indent and (next_line.strip().startswith('elif') or next_line.strip().startswith('else:')):
                insert_after = j - 1
                print(f'requery块结束在第{j}行')
                break
        break

if insert_after > 0:
    # 插入create_task处理
    new_code = [
        '\n',
        '        elif action == "create_task":\n',
        '            # 新建任务\n',
        '            task_name = data.get("task_name", "")\n',
        '            print(f"  [新建任务] 收到任务: {task_name}")\n',
        '            try:\n',
        '                import urllib.request as ur\n',
        '                import json as js\n',
        '                from datetime import datetime as dt\n',
        '                env_path = r"C:\\Users\\Administrator\\AppData\\Local\\hermes\\profiles\\agent6_scheduler\\scripts\\feishu_insight_link.env"\n',
        '                app_id = ""\n',
        '                app_secret = ""\n',
        '                for line in open(env_path, encoding="utf-8-sig"):\n',
        '                    line = line.strip()\n',
        '                    if line.startswith("FEISHU_APP_ID="):\n',
        '                        app_id = line.split("=", 1)[1]\n',
        '                    elif line.startswith("FEISHU_APP_SECRET="):\n',
        '                        app_secret = line.split("=", 1)[1]\n',
        '                req = ur.Request(\n',
        '                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",\n',
        '                    data=js.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),\n',
        '                    headers={"Content-Type": "application/json"},\n',
        '                )\n',
        '                with ur.urlopen(req, timeout=30) as r:\n',
        '                    token = js.load(r)["tenant_access_token"]\n',
        '                url = "https://open.feishu.cn/open-apis/bitable/v1/apps/X8N1bvN3na99dFsyu0gcU8zTnHf/tables/tblz3H4lV7PCrBrX/records"\n',
        '                today_ms = int(dt.now().timestamp() * 1000)\n',
        '                body = {\n',
        '                    "fields": {\n',
        '                        "任务名称": task_name,\n',
        '                        "状态": "待办",\n',
        '                        "优先级": "中",\n',
        '                        "类别": "工作",\n',
        '                        "截止日期": today_ms\n',
        '                    }\n',
        '                }\n',
        '                req = ur.Request(\n',
        '                    url,\n',
        '                    data=js.dumps(body).encode(),\n',
        '                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},\n',
        '                    method="POST",\n',
        '                )\n',
        '                with ur.urlopen(req, timeout=30) as r:\n',
        '                    resp = js.load(r)\n',
        '                if resp.get("code") == 0:\n',
        '                    sender._send_message(f"✅ 已创建任务：{task_name}")\n',
        '                    print(f"  [新建任务] 成功: {task_name}")\n',
        '                else:\n',
        '                    sender._send_message(f"❌ 创建失败: {resp.get(\'msg\', \'未知错误\')}")\n',
        '            except Exception as e:\n',
        '                sender._send_message(f"❌ 创建任务异常: {str(e)[:50]}")\n',
        '                print(f"  [新建任务] 异常: {e}")\n',
    ]
    
    # 插入到insert_after位置之后
    lines = lines[:insert_after+1] + new_code + lines[insert_after+1:]
    
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'✅ 已在第{insert_after+1}行后插入create_task处理逻辑')
else:
    print('❌ 未找到插入位置')
