#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日早报推送脚本 - 极简测试版"""
import os
import requests
from datetime import datetime

def main():
    print("=== 开始生成每日早报 ===")
    
    # 格式化消息
    today = datetime.now().strftime('%Y年%m月%d日')
    weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
    weekday = weekday_map.get(datetime.now().weekday(), '')
    
    message = f"📅 紫麒麟智能助理·每日早报\n{today} {weekday}\n\n"
    message += "🌤️ 西安今日天气：暂无数据（需配置和风天气API）\n\n"
    message += "📚 今日学习精选：暂无相关内容\n\n"
    message += "━━━━━━━━━━━━━\n"
    message += "🤖 由紫麒麟智能助理自动推送\n"
    message += "⏰ 每天早上8:00准时送达"
    
    print(message)
    
    # 保存到文件
    with open('daily_digest.txt', 'w', encoding='utf-8') as f:
        f.write(message)
    
    # 推送到飞书群
    webhook = os.environ.get('FEISHU_WEBHOOK', '')
    if webhook:
        print(f"正在推送到飞书群...")
        payload = {
            "msg_type": "text",
            "content": {"text": message}
        }
        try:
            response = requests.post(webhook, json=payload, timeout=15)
            data = response.json()
            print(f"飞书返回: {data}")
            if data.get('code') == 0:
                print("✅ 飞书消息推送成功")
            else:
                print(f"❌ 飞书消息推送失败")
        except Exception as e:
            print(f"❌ 飞书消息推送异常: {e}")
    else:
        print("⚠️ 未配置FEISHU_WEBHOOK，跳过推送")
    
    print("=== 每日早报生成完成 ===")

if __name__ == '__main__':
    main()
