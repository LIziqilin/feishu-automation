#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日早报推送脚本
功能：整合西安天气和学习类内容，格式化为早报消息推送到飞书群
配置：在GitHub Secrets中设置 FEISHU_WEBHOOK（群机器人webhook地址）
"""

import os
import json
import requests
from datetime import datetime

def get_weather_info():
    """读取天气数据"""
    if os.path.exists('weather_data.json'):
        with open('weather_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if data:
                return data[0]
    return None

def get_learning_articles():
    """读取学习内容"""
    if os.path.exists('learning_articles.json'):
        with open('learning_articles.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_clothing_advice(temp):
    """根据温度给出穿衣建议"""
    try:
        temp = int(temp)
        if temp >= 30:
            return "天气炎热，建议穿短袖、短裤等清凉透气衣物"
        elif temp >= 25:
            return "天气较热，建议穿短袖、薄长裙等夏季衣物"
        elif temp >= 20:
            return "天气舒适，建议穿长袖衬衫、薄外套等春秋衣物"
        elif temp >= 15:
            return "天气较凉，建议穿风衣、薄毛衣等保暖衣物"
        elif temp >= 10:
            return "天气寒冷，建议穿厚外套、毛衣等冬季衣物"
        else:
            return "天气严寒，建议穿羽绒服、厚棉衣等防寒衣物"
    except:
        return "请根据实际天气情况选择衣物"

def format_daily_digest(weather, articles):
    """格式化为每日早报消息"""
    today = datetime.now().strftime('%Y年%m月%d日')
    weekday = datetime.now().strftime('%A')
    weekday_map = {
        'Monday': '星期一', 'Tuesday': '星期二', 'Wednesday': '星期三',
        'Thursday': '星期四', 'Friday': '星期五', 'Saturday': '星期六', 'Sunday': '星期日'
    }
    weekday_cn = weekday_map.get(weekday, '')
    
    message = f"📅 紫麒麟智能助理·每日早报\n{today} {weekday_cn}\n\n"
    
    # 天气部分
    if weather:
        temp = weather.get('温度', '未知')
        weather_text = weather.get('天气', '未知')
        humidity = weather.get('湿度', '未知')
        wind_dir = weather.get('风向', '')
        wind_scale = weather.get('风力', '')
        advice = get_clothing_advice(temp)
        
        message += "🌤️ 西安今日天气\n"
        message += f"━━━━━━━━━━━━━\n"
        message += f"天气：{weather_text}\n"
        message += f"温度：{temp}°C\n"
        message += f"湿度：{humidity}%\n"
        if wind_dir and wind_scale:
            message += f"风向：{wind_dir} {wind_scale}级\n"
        message += f"👔 穿衣建议：{advice}\n\n"
    else:
        message += "🌤️ 西安今日天气：暂无数据（需配置和风天气API密钥）\n\n"
    
    # 学习内容部分
    if articles:
        message += "📚 今日学习精选\n"
        message += "━━━━━━━━━━━━━\n"
        
        # 按分类分组
        category_articles = {}
        for article in articles:
            category = article.get('分类', '其他').split('、')[0]
            if category not in category_articles:
                category_articles[category] = []
            category_articles[category].append(article)
        
        # 每个分类最多显示2条
        category_icons = {
            "学习效率": "⏱️", "思维模式": "🧠", "思维框架": "📐",
            "沟通技巧": "💬", "表达方式": "✍️"
        }
        
        item_count = 0
        for category, cat_articles in category_articles.items():
            if item_count >= 6:  # 总共最多显示6条
                break
            icon = category_icons.get(category, "📌")
            message += f"\n{icon} 【{category}】\n"
            for i, article in enumerate(cat_articles[:2]):
                if item_count >= 6:
                    break
                title = article.get('标题', '')[:50]
                source = article.get('来源', '')
                link = article.get('链接', '')
                message += f"  {i+1}. {title}\n"
                message += f"     来源：{source}\n"
                if link:
                    message += f"     🔗 {link}\n"
                item_count += 1
        
        message += f"\n\n💡 共筛选出 {len(articles)} 条学习相关内容\n"
    else:
        message += "📚 今日学习精选：暂无相关内容（可配置更多RSS源）\n"
    
    message += "\n━━━━━━━━━━━━━\n"
    message += "🤖 由紫麒麟智能助理自动推送\n"
    message += "⏰ 每天早上8:00准时送达"
    
    return message

def send_to_feishu(webhook, message):
    """发送消息到飞书群"""
    if not webhook:
        print("未配置FEISHU_WEBHOOK，跳过推送")
        return False
    
    url = webhook
    payload = {
        "msg_type": "text",
        "content": {
            "text": message
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if data.get('code') == 0 or data.get('StatusCode') == 0:
            print("飞书消息推送成功")
            return True
        else:
            print(f"飞书消息推送失败: {data}")
            return False
    except Exception as e:
        print(f"飞书消息推送异常: {e}")
        return False

def main():
    # 读取数据
    weather = get_weather_info()
    articles = get_learning_articles()
    
    # 格式化为早报
    message = format_daily_digest(weather, articles)
    
    # 打印消息（用于调试）
    print("=" * 50)
    print(message)
    print("=" * 50)
    
    # 保存消息到文件
    with open('daily_digest.txt', 'w', encoding='utf-8') as f:
        f.write(message)
    
    # 推送到飞书群
    webhook = os.environ.get('FEISHU_WEBHOOK', '')
    send_to_feishu(webhook, message)

if __name__ == '__main__':
    main()
