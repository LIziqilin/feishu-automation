#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日早报推送脚本 - 完整版（含签名校验、富文本、天气、学习内容）"""
import os
import sys
import json
import time
import hmac
import hashlib
import base64
import requests
from datetime import datetime

# ============================================================
# 飞书群机器人签名计算
# ============================================================
def gen_sign(secret, timestamp):
    """生成飞书群机器人签名"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

# ============================================================
# 发送飞书消息（支持text和post类型）
# ============================================================
def send_feishu_message(webhook, secret, msg_type, content):
    """发送飞书群机器人消息（含签名校验）"""
    timestamp = str(int(time.time()))
    sign = gen_sign(secret, timestamp)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": msg_type,
        "content": content
    }
    
    try:
        response = requests.post(webhook, json=payload, timeout=15)
        data = response.json()
        print(f"飞书返回: {data}")
        if data.get('code') == 0:
            print("✅ 飞书消息推送成功")
            return True
        else:
            print(f"❌ 飞书消息推送失败: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"❌ 飞书消息推送异常: {e}")
        return False

# ============================================================
# 获取西安天气（和风天气API）
# ============================================================
def get_weather(api_key):
    """获取西安今日天气"""
    if not api_key:
        return "暂无数据（需配置和风天气API）"
    
    try:
        # 和风天气API - 西安城市ID: 101110101
        url = f"https://devapi.qweather.com/v7/weather/now?location=101110101&key={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('code') == '200':
            now = data.get('now', {})
            temp = now.get('temp', '未知')
            text = now.get('text', '未知')
            wind_dir = now.get('windDir', '未知')
            wind_scale = now.get('windScale', '未知')
            humidity = now.get('humidity', '未知')
            return f"{text} {temp}°C，{wind_dir}风{wind_scale}级，湿度{humidity}%"
        else:
            return f"获取失败: {data.get('code')}"
    except Exception as e:
        return f"获取异常: {str(e)}"

# ============================================================
# 获取学习内容（RSS源）
# ============================================================
def get_learning_content(rss_urls):
    """从RSS源获取学习内容"""
    if not rss_urls:
        return []
    
    contents = []
    try:
        import feedparser
        for url in rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:  # 每个源取前3条
                    contents.append({
                        'title': entry.get('title', '无标题'),
                        'link': entry.get('link', ''),
                        'summary': entry.get('summary', '')[:100]
                    })
            except Exception as e:
                print(f"⚠️ RSS源 {url} 获取失败: {e}")
    except ImportError:
        print("⚠️ 未安装feedparser，跳过学习内容获取")
    
    return contents[:5]  # 最多取5条

# ============================================================
# 生成富文本消息（post类型）
# ============================================================
def build_rich_text_message(today, weekday, weather, learning_contents):
    """构建飞书富文本消息"""
    content = {
        "post": {
            "zh_cn": {
                "title": f"📅 紫麒麟智能助理·每日早报",
                "content": [
                    [
                        {"tag": "text", "text": f"📆 {today} {weekday}\n\n"}
                    ],
                    [
                        {"tag": "text", "text": f"🌤️ 西安今日天气：{weather}\n\n"}
                    ],
                    [
                        {"tag": "text", "text": "📚 今日学习精选：\n"}
                    ]
                ]
            }
        }
    }
    
    # 添加学习内容
    if learning_contents:
        for i, item in enumerate(learning_contents, 1):
            content["post"]["zh_cn"]["content"].append([
                {"tag": "text", "text": f"{i}. {item['title']}\n"}
            ])
            if item.get('link'):
                content["post"]["zh_cn"]["content"].append([
                    {"tag": "a", "text": "  查看原文", "href": item['link']}
                ])
    else:
        content["post"]["zh_cn"]["content"].append([
            {"tag": "text", "text": "  暂无相关内容\n"}
        ])
    
    # 添加分隔线和页脚
    content["post"]["zh_cn"]["content"].append([
        {"tag": "text", "text": "\n━━━━━━━━━━━━━\n"}
    ])
    content["post"]["zh_cn"]["content"].append([
        {"tag": "text", "text": "🤖 由紫麒麟智能助理自动推送\n"}
    ])
    content["post"]["zh_cn"]["content"].append([
        {"tag": "text", "text": "⏰ 每天早上8:00准时送达"}
    ])
    
    return content

# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 50)
    print("=== 开始生成每日早报 ===")
    print("=" * 50)
    
    # 从环境变量读取配置
    webhook = os.environ.get('FEISHU_WEBHOOK', '')
    secret = os.environ.get('FEISHU_SECRET', '')
    weather_api_key = os.environ.get('QWEATHER_API_KEY', '')
    rss_urls_str = os.environ.get('RSS_URLS', '')
    
    print(f"Webhook: {'已配置' if webhook else '未配置'}")
    print(f"Secret: {'已配置' if secret else '未配置'}")
    print(f"天气API: {'已配置' if weather_api_key else '未配置'}")
    
    # 格式化日期
    today = datetime.now().strftime('%Y年%m月%d日')
    weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 
                   4: '星期五', 5: '星期六', 6: '星期日'}
    weekday = weekday_map.get(datetime.now().weekday(), '')
    
    print(f"\n📆 日期: {today} {weekday}")
    
    # 获取天气
    print("\n🌤️ 正在获取天气...")
    weather = get_weather(weather_api_key)
    print(f"天气: {weather}")
    
    # 获取学习内容
    print("\n📚 正在获取学习内容...")
    rss_urls = [url.strip() for url in rss_urls_str.split(',') if url.strip()] if rss_urls_str else []
    learning_contents = get_learning_content(rss_urls)
    print(f"学习内容: 获取到 {len(learning_contents)} 条")
    
    # 生成纯文本消息（备用）
    text_message = f"📅 紫麒麟智能助理·每日早报\n{today} {weekday}\n\n"
    text_message += f"🌤️ 西安今日天气：{weather}\n\n"
    text_message += "📚 今日学习精选：\n"
    if learning_contents:
        for i, item in enumerate(learning_contents, 1):
            text_message += f"{i}. {item['title']}\n"
    else:
        text_message += "  暂无相关内容\n"
    text_message += "\n━━━━━━━━━━━━━\n"
    text_message += "🤖 由紫麒麟智能助理自动推送\n"
    text_message += "⏰ 每天早上8:00准时送达"
    
    print("\n" + "=" * 50)
    print("=== 早报内容 ===")
    print("=" * 50)
    print(text_message)
    
    # 保存到文件
    with open('daily_digest.txt', 'w', encoding='utf-8') as f:
        f.write(text_message)
    
    # 推送到飞书群
    if webhook and secret:
        print("\n" + "=" * 50)
        print("=== 推送到飞书群 ===")
        print("=" * 50)
        
        # 优先发送富文本消息
        print("\n尝试发送富文本消息...")
        rich_content = build_rich_text_message(today, weekday, weather, learning_contents)
        success = send_feishu_message(webhook, secret, "post", rich_content)
        
        # 如果富文本失败，尝试纯文本
        if not success:
            print("\n富文本发送失败，尝试纯文本消息...")
            text_content = {"text": text_message}
            success = send_feishu_message(webhook, secret, "text", text_content)
        
        if success:
            print("\n✅ 早报推送完成！")
        else:
            print("\n❌ 早报推送失败，请检查webhook和secret配置")
            sys.exit(1)
    else:
        print("\n⚠️ 未配置FEISHU_WEBHOOK或FEISHU_SECRET，跳过推送")
        if not webhook:
            print("  - 请配置FEISHU_WEBHOOK环境变量")
        if not secret:
            print("  - 请配置FEISHU_SECRET环境变量")
    
    print("\n" + "=" * 50)
    print("=== 每日早报生成完成 ===")
    print("=" * 50)

if __name__ == '__main__':
    main()

