#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""增加create_task action处理逻辑"""

# 读取文件
with open('learning_system.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到requery处理，在它之后增加create_task处理
old_code = '''        elif action == "requery":
            # 重新推送今日卡片
            reports = selector.format_morning_report(today_cards)
                time.sleep(0.5)'''

new_code = '''        elif action == "requery":
            # 重新推送今日卡片
            reports = selector.format_morning_report(today_cards)
                time.sleep(0.5)

        elif action == "create_task":
            # 新建任务
            task_name = data.get("task_name", "")
            print(f"  [新建任务] 收到任务: {task_name}")
            try:
                # 调用飞书API创建任务
                import urllib.request as ur
                import json as js
                from datetime import datetime as dt

                # 读取凭证
                env_path = r"C:\\Users\\Administrator\\AppData\\Local\\hermes\\profiles\\agent6_scheduler\\scripts\\feishu_insight_link.env"
                app_id = ""
                app_secret = ""
                for line in open(env_path, encoding="utf-8-sig"):
                    line = line.strip()
                    if line.startswith("FEISHU_APP_ID="):
                        app_id = line.split("=", 1)[1]
                    elif line.startswith("FEISHU_APP_SECRET="):
                        app_secret = line.split("=", 1)[1]

                # 获取token
                req = ur.Request(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    data=js.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with ur.urlopen(req, timeout=30) as r:
                    token = js.load(r)["tenant_access_token"]

                # 创建任务
                url = "https://open.feishu.cn/open-apis/bitable/v1/apps/X8N1bvN3na99dFsyu0gcU8zTnHf/tables/tblz3H4lV7PCrBrX/records"
                today_ms = int(dt.now().timestamp() * 1000)
                body = {
                    "fields": {
                        "任务名称": task_name,
                        "状态": "待办",
                        "优先级": "中",
                        "类别": "工作",
                        "截止日期": today_ms
                    }
                }
                req = ur.Request(
                    url,
                    data=js.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                    method="POST",
                )
                with ur.urlopen(req, timeout=30) as r:
                    resp = js.load(r)
                if resp.get("code") == 0:
                    sender._send_message(f"✅ 已创建任务：{task_name}")
                    print(f"  [新建任务] 成功: {task_name}")
                else:
                    sender._send_message(f"❌ 创建失败: {resp.get('msg', '未知错误')}")
            except Exception as e:
                sender._send_message(f"❌ 创建任务异常: {str(e)[:50]}")
                print(f"  [新建任务] 异常: {e}")'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('learning_system.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 已增加create_task处理逻辑')
else:
    print('❌ 未找到目标代码')
    # 找一下requery的位置
    lines = content.split('\\n')
    for i, line in enumerate(lines):
        if 'elif action == "requery"' in line:
            print(f'第{i+1}行: {line}')
