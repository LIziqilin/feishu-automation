#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日早报推送脚本 - 完整版V2（含天气、学习内容、签名校验、富文本）"""
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
# 获取西安天气（多源备用：wttr.in -> 中国天气网）
# ============================================================
def get_weather_xian():
    """获取西安今日天气（多源备用）"""
    # 方式1：wttr.in免费API
    try:
        print("  尝试wttr.in...")
        url = "https://wttr.in/Xian?format=j1&lang=zh"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        data = response.json()
        
        current = data.get('current_condition', [{}])[0]
        temp_c = current.get('temp_C', '未知')
        feels_like = current.get('FeelsLikeC', '未知')
        humidity = current.get('humidity', '未知')
        weather_desc = current.get('lang_zh', [{}])[0].get('value', 
                      current.get('weatherDesc', [{}])[0].get('value', '未知'))
        wind_dir = current.get('winddir16Point', '未知')
        wind_speed = current.get('windspeedKmph', '未知')
        
        today_forecast = data.get('weather', [{}])[0]
        max_temp = today_forecast.get('maxtempC', '未知')
        min_temp = today_forecast.get('mintempC', '未知')
        
        weather_info = (
            f"{weather_desc} {temp_c}°C（体感{feels_like}°C），"
            f"{min_temp}°C ~ {max_temp}°C，"
            f"{wind_dir}风{wind_speed}km/h，湿度{humidity}%"
        )
        return weather_info
    except Exception as e:
        print(f"  wttr.in失败: {e}")
    
    # 方式2：使用简化格式（更稳定）
    try:
        print("  尝试wttr.in简化格式...")
        url = "https://wttr.in/Xian?format=%C+%t+%h+%w&lang=zh"
        headers = {'User-Agent': 'curl/7.68.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and response.text.strip():
            return f"{response.text.strip()}（数据来源：wttr.in）"
    except Exception as e:
        print(f"  简化格式失败: {e}")
    
    return "暂无数据（天气API暂时不可用）"

# ============================================================
# 获取学习内容（RSS源）
# ============================================================
def get_learning_content():
    """从多个RSS源获取学习内容（学习效率、思维模式、沟通技巧等）"""
    # 预设的高质量学习类RSS源（精选稳定源）
    rss_sources = [
        {
            'name': '少数派',
            'url': 'https://sspai.com/feed',
            'category': '效率工具'
        },
        {
            'name': '知乎日报',
            'url': 'https://daily.zhihu.com/feed',
            'category': '知识精选'
        }
    ]
    
    # 从环境变量读取自定义RSS源（如果有）
    custom_rss = os.environ.get('RSS_URLS', '')
    if custom_rss:
        for i, url in enumerate(custom_rss.split(',')):
            url = url.strip()
            if url:
                rss_sources.append({
                    'name': f'自定义源{i+1}',
                    'url': url,
                    'category': '自定义'
                })
    
    contents = []
    try:
        import feedparser
        for source in rss_sources:
            try:
                print(f"  正在抓取 {source['name']}...")
                feed = feedparser.parse(source['url'])
                for entry in feed.entries[:2]:  # 每个源取前2条
                    title = entry.get('title', '无标题').strip()
                    link = entry.get('link', '')
                    # 过滤广告和无关内容
                    if any(kw in title for kw in ['广告', '推广', '优惠', '折扣', '抽奖']):
                        continue
                    contents.append({
                        'title': title,
                        'link': link,
                        'source': source['name'],
                        'category': source['category']
                    })
            except Exception as e:
                print(f"  ⚠️ {source['name']} 抓取失败: {e}")
    except ImportError:
        print("⚠️ 未安装feedparser，跳过学习内容获取")
    
    # 去重（按标题）
    seen_titles = set()
    unique_contents = []
    for item in contents:
        if item['title'] not in seen_titles:
            seen_titles.add(item['title'])
            unique_contents.append(item)
    
    return unique_contents[:5]  # 最多取5条

# ============================================================
# 构建富文本消息（post类型）
# ============================================================
def build_rich_text_message(today, weekday, weather, learning_contents):
    """构建飞书富文本消息"""
    content = {
        "post": {
            "zh_cn": {
                "title": "📅 紫麒麟智能助理·每日早报",
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
            source_tag = f"[{item['source']}]" if item.get('source') else ""
            content["post"]["zh_cn"]["content"].append([
                {"tag": "text", "text": f"{i}. {source_tag} {item['title']}\n"}
            ])
            if item.get('link'):
                content["post"]["zh_cn"]["content"].append([
                    {"tag": "a", "text": "  🔗 查看原文", "href": item['link']}
                ])
    else:
        content["post"]["zh_cn"]["content"].append([
            {"tag": "text", "text": "  暂无相关内容（RSS源暂时不可用）\n"}
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
# 构建纯文本消息（备用）
# ============================================================
def build_text_message(today, weekday, weather, learning_contents):
    """构建纯文本消息（备用）"""
    message = f"📅 紫麒麟智能助理·每日早报\n{today} {weekday}\n\n"
    message += f"🌤️ 西安今日天气：{weather}\n\n"
    message += "📚 今日学习精选：\n"
    if learning_contents:
        for i, item in enumerate(learning_contents, 1):
            source_tag = f"[{item['source']}]" if item.get('source') else ""
            message += f"{i}. {source_tag} {item['title']}\n"
            if item.get('link'):
                message += f"   🔗 {item['link']}\n"
    else:
        message += "  暂无相关内容（RSS源暂时不可用）\n"
    message += "\n━━━━━━━━━━━━━\n"
    message += "🤖 由紫麒麟智能助理自动推送\n"
    message += "⏰ 每天早上8:00准时送达"
    return message

# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 60)
    print("=== 开始生成每日早报 V2.0 ===")
    print("=" * 60)
    
    # 从环境变量读取配置
    webhook = os.environ.get('FEISHU_WEBHOOK', '')
    secret = os.environ.get('FEISHU_SECRET', '')
    
    print(f"\n⚙️ 配置检查:")
    print(f"  Webhook: {'已配置' if webhook else '❌ 未配置'}")
    print(f"  Secret: {'已配置' if secret else '❌ 未配置'}")
    
    if not webhook or not secret:
        print("❌ 缺少必要配置，请检查FEISHU_WEBHOOK和FEISHU_SECRET")
        sys.exit(1)
    
    # 格式化日期
    today = datetime.now().strftime('%Y年%m月%d日')
    weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 
                   4: '星期五', 5: '星期六', 6: '星期日'}
    weekday = weekday_map.get(datetime.now().weekday(), '')
    
    print(f"\n📆 日期: {today} {weekday}")
    
    # 获取西安天气
    print("\n🌤️ 正在获取西安天气...")
    weather = get_weather_xian()
    print(f"  天气: {weather}")
    
    # 获取学习内容
    print("\n📚 正在获取学习内容...")
    learning_contents = get_learning_content()
    print(f"  获取到 {len(learning_contents)} 条学习内容")
    for i, item in enumerate(learning_contents, 1):
        print(f"    {i}. [{item['source']}] {item['title'][:50]}")
    
    # 构建消息
    print("\n" + "=" * 60)
    print("=== 构建早报消息 ===")
    print("=" * 60)
    
    text_message = build_text_message(today, weekday, weather, learning_contents)
    print(text_message)
    
    # 保存到文件
    with open('daily_digest.txt', 'w', encoding='utf-8') as f:
        f.write(text_message)
    
    # 推送到飞书群
    print("\n" + "=" * 60)
    print("=== 推送到飞书群 ===")
    print("=" * 60)
    
    # 优先发送富文本消息
    print("\n📤 尝试发送富文本消息...")
    rich_content = build_rich_text_message(today, weekday, weather, learning_contents)
    success = send_feishu_message(webhook, secret, "post", rich_content)
    
    # 如果富文本失败，尝试纯文本
    if not success:
        print("\n📤 富文本发送失败，尝试纯文本消息...")
        text_content = {"text": text_message}
        success = send_feishu_message(webhook, secret, "text", text_content)
    
    if success:
        print("\n✅ 早报推送完成！")
    else:
        print("\n❌ 早报推送失败，请检查webhook和secret配置")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("=== 每日早报生成完成 V2.0 ===")
    print("=" * 60)

if __name__ == '__main__':
    main()

