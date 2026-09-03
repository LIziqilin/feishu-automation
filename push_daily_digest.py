#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日早报推送脚本 - 稳定版"""
import os
import json
import requests
from datetime import datetime

def main():
    print("=== 开始生成每日早报 ===")
    
    # 读取天气数据（如果存在）
    weather = None
    if os.path.exists('weather_data.json'):
        try:
            with open('weather_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and len(data) > 0:
                    weather = data[0]
            print("天气数据读取成功")
        except Exception as e:
            print(f"天气数据读取失败: {e}")
    else:
        print("weather_data.json不存在，跳过天气")
    
    # 读取学习内容（如果存在）
    articles = []
    if os.path.exists('learning_articles.json'):
        try:
            with open('learning_articles.json', 'r', encoding='utf-8') as f:
                articles = json.load(f)
            print(f"学习内容读取成功，共{len(articles)}条")
        except Exception as e:
            print(f"学习内容读取失败: {e}")
    else:
        print("learning_articles.json不存在，跳过学习内容")
    
    # 格式化消息
    today = datetime.now().strftime('%Y年%m月%d日')
    weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
    weekday = weekday_map.get(datetime.now().weekday(), '')
    
    message = f"📅 紫麒麟智能助理·每日早报\n{today} {weekday}\n\n"
    
    # 天气部分
    if weather:
        temp = weather.get('温度', '未知')
        weather_text = weather.get('天气', '未知')
        humidity = weather.get('湿度', '未知')
        message += "🌤️ 西安今日天气\n"
        message += "━━━━━━━━━━━━━\n"
        message += f"天气：{weather_text}\n"
        message += f"温度：{temp}°C\n"
        message += f"湿度：{humidity}%\n\n"
    else:
        message += "🌤️ 西安今日天气：暂无数据（需配置和风天气API）\n\n"
    
    # 学习内容部分
    if articles and len(articles) > 0:
        message += "📚 今日学习精选\n"
        message += "━━━━━━━━━━━━━\n"
        for i, article in enumerate(articles[:5]):
            title = article.get('标题', '')[:40]
            source = article.get('来源', '')
            category = article.get('分类', '')
            message += f"\n{i+1}. 【{category}】{title}\n"
            message += f"   来源：{source}\n"
        message += f"\n\n💡 共筛选出 {len(articles)} 条学习内容\n"
    else:
        message += "📚 今日学习精选：暂无相关内容\n"
    
    message += "\n━━━━━━━━━━━━━\n"
    message += "🤖 由紫麒麟智能助理自动推送\n"
    message += "⏰ 每天早上8:00准时送达"
    
    # 打印消息
    print("\n" + "=" * 50)
    print(message)
    print("=" * 50 + "\n")
    
    # 保存到文件
    try:
        with open('daily_digest.txt', 'w', encoding='utf-8') as f:
            f.write(message)
        print("早报已保存到daily_digest.txt")
    except Exception as e:
        print(f"保存文件失败: {e}")
    
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
            if data.get('code') == 0 or data.get('StatusCode') == 0:
                print("✅ 飞书消息推送成功")
            else:
                print(f"❌ 飞书消息推送失败: {data}")
        except Exception as e:
            print(f"❌ 飞书消息推送异常: {e}")
    else:
        print("⚠️ 未配置FEISHU_WEBHOOK，跳过推送")
    
    print("=== 每日早报生成完成 ===")

if __name__ == '__main__':
    main()
