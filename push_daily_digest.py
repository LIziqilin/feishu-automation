#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日早报推送脚本 - V3.0优化版（学习内容分类+强广告过滤+天气多源）"""
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
# 广告/推广内容过滤关键词（加强版）
# ============================================================
AD_KEYWORDS = [
    # 直接广告类
    '广告', '推广', '促销', '秒杀', '团购', '带货', '种草',
    # 优惠活动类
    '优惠', '折扣', '抽奖', '限时', '免费领', '红包', '福利',
    '满减', '优惠券', '拼团', '砍价',
    # 产品发布类
    '新品上市', '新品发布', '开售', '预售', '首发', '重磅推出',
    # 电商平台类
    '淘宝', '京东', '拼多多', '天猫', '苏宁', '唯品会',
    '双11', '618', '年货节', '购物节',
    # 产品测评类（非学习内容）
    '开箱', '上手', '真机', '参数', '跑分',
    # 其他无关内容
    '招聘', '求职', '简历', '面试经',
]

# ============================================================
# 学习内容分类关键词
# ============================================================
CATEGORY_KEYWORDS = {
    '学习效率': ['学习', '效率', '方法', '记忆', '专注', '时间管理', 'GTD', '番茄', '费曼', '艾宾浩斯'],
    '思维模式': ['思维', '思考', '逻辑', '认知', '心智', '模型', '框架', '底层', '本质', '第一性原理'],
    '沟通技巧': ['沟通', '表达', '演讲', '说服', '谈判', '倾听', '反馈', '情商', '社交', '人际关系'],
    '个人成长': ['成长', '习惯', '自律', '目标', '行动', '复盘', '反思', '精进', '提升', '蜕变'],
}

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
# 发送飞书消息
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
# 获取西安天气（多源备用：wttr.in -> Open-Meteo）
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
    
    # 方式2：Open-Meteo免费API（不需要密钥，更稳定）
    try:
        print("  尝试Open-Meteo...")
        # 西安坐标：34.3416°N, 108.9398°E
        url = ("https://api.open-meteo.com/v1/forecast?"
               "latitude=34.3416&longitude=108.9398"
               "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
               "&daily=temperature_2m_max,temperature_2m_min"
               "&timezone=Asia%2FShanghai")
        response = requests.get(url, timeout=15)
        data = response.json()
        
        current = data.get('current', {})
        temp = current.get('temperature_2m', '未知')
        feels_like = current.get('apparent_temperature', '未知')
        humidity = current.get('relative_humidity_2m', '未知')
        wind_speed = current.get('wind_speed_10m', '未知')
        weather_code = current.get('weather_code', 0)
        
        # 天气代码映射
        weather_map = {
            0: '晴', 1: '大部晴', 2: '局部多云', 3: '阴',
            45: '雾', 48: '雾凇',
            51: '小毛毛雨', 53: '毛毛雨', 55: '大毛毛雨',
            61: '小雨', 63: '中雨', 65: '大雨',
            71: '小雪', 73: '中雪', 75: '大雪',
            80: '阵雨', 81: '强阵雨', 82: '暴雨',
            95: '雷暴', 96: '雷暴伴冰雹', 99: '强雷暴伴冰雹'
        }
        weather_desc = weather_map.get(weather_code, '未知')
        
        daily = data.get('daily', {})
        max_temp = daily.get('temperature_2m_max', ['未知'])[0]
        min_temp = daily.get('temperature_2m_min', ['未知'])[0]
        
        weather_info = (
            f"{weather_desc} {temp}°C（体感{feels_like}°C），"
            f"{min_temp}°C ~ {max_temp}°C，"
            f"风速{wind_speed}km/h，湿度{humidity}%"
        )
        return weather_info
    except Exception as e:
        print(f"  Open-Meteo失败: {e}")
    
    return "暂无数据（天气API暂时不可用）"

# ============================================================
# 判断是否为广告内容
# ============================================================
def is_ad_content(title, summary=''):
    """判断内容是否为广告/推广"""
    text = (title + ' ' + summary).lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in text:
            return True
    return False

# ============================================================
# 内容分类
# ============================================================
def classify_content(title, summary=''):
    """对学习内容进行分类"""
    text = title + ' ' + summary
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return '知识精选'

# ============================================================
# 获取学习内容（RSS源，加强广告过滤）
# ============================================================
def get_learning_content():
    """从多个高质量学习类RSS源获取内容（学习效率、思维模式、沟通技巧等）"""
    # 精选高质量学习类RSS源（按类别）
    rss_sources = [
        # 学习效率类
        {
            'name': '战隼的学习探索',
            'url': 'https://www.read.org.cn/feed',
            'category': '学习效率'
        },
        {
            'name': '褪墨',
            'url': 'https://www.mifengtd.cn/feed',
            'category': '学习效率'
        },
        # 思维模式类
        {
            'name': '阮一峰的网络日志',
            'url': 'https://www.ruanyifeng.com/blog/atom.xml',
            'category': '思维模式'
        },
        {
            'name': '左岸读书',
            'url': 'https://www.zreading.cn/feed',
            'category': '思维模式'
        },
        # 沟通技巧类
        {
            'name': '哈佛商业评论中文网',
            'url': 'https://www.hbrchina.org/feed',
            'category': '沟通技巧'
        },
        # 综合知识类
        {
            'name': '少数派',
            'url': 'https://sspai.com/feed',
            'category': '知识精选'
        },
        {
            'name': '知乎日报',
            'url': 'https://daily.zhihu.com/feed',
            'category': '知识精选'
        },
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
                for entry in feed.entries[:3]:  # 每个源取前3条
                    title = entry.get('title', '无标题').strip()
                    link = entry.get('link', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    
                    # 强广告过滤
                    if is_ad_content(title, summary):
                        print(f"    过滤广告内容: {title[:30]}...")
                        continue
                    
                    # 内容分类
                    category = classify_content(title, summary)
                    
                    contents.append({
                        'title': title,
                        'link': link,
                        'source': source['name'],
                        'category': category
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
    
    # 按类别排序，优先学习效率、思维模式、沟通技巧
    category_order = ['学习效率', '思维模式', '沟通技巧', '个人成长', '知识精选', '自定义']
    unique_contents.sort(key=lambda x: category_order.index(x['category']) if x['category'] in category_order else 99)
    
    return unique_contents[:6]  # 最多取6条

# ============================================================
# 构建富文本消息（按分类展示）
# ============================================================
def build_rich_text_message(today, weekday, weather, learning_contents):
    """构建飞书富文本消息（按分类展示学习内容）"""
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
    
    # 按分类添加学习内容
    if learning_contents:
        current_category = None
        for i, item in enumerate(learning_contents, 1):
            # 如果类别变化，添加类别标题
            if item['category'] != current_category:
                current_category = item['category']
                category_emoji = {
                    '学习效率': '⚡',
                    '思维模式': '🧠',
                    '沟通技巧': '💬',
                    '个人成长': '🌱',
                    '知识精选': '📖',
                    '自定义': '🔖'
                }.get(current_category, '📌')
                content["post"]["zh_cn"]["content"].append([
                    {"tag": "text", "text": f"\n{category_emoji} {current_category}：\n"}
                ])
            
            source_tag = f"[{item['source']}]" if item.get('source') else ""
            content["post"]["zh_cn"]["content"].append([
                {"tag": "text", "text": f"  {i}. {source_tag} {item['title']}\n"}
            ])
            if item.get('link'):
                content["post"]["zh_cn"]["content"].append([
                    {"tag": "a", "text": "     🔗 查看原文", "href": item['link']}
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
        current_category = None
        for i, item in enumerate(learning_contents, 1):
            if item['category'] != current_category:
                current_category = item['category']
                category_emoji = {
                    '学习效率': '⚡', '思维模式': '🧠', '沟通技巧': '💬',
                    '个人成长': '🌱', '知识精选': '📖', '自定义': '🔖'
                }.get(current_category, '📌')
                message += f"\n{category_emoji} {current_category}：\n"
            
            source_tag = f"[{item['source']}]" if item.get('source') else ""
            message += f"  {i}. {source_tag} {item['title']}\n"
            if item.get('link'):
                message += f"     🔗 {item['link']}\n"
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
    print("=== 开始生成每日早报 V3.0（优化版）===")
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
    print(f"\n  最终获取到 {len(learning_contents)} 条学习内容")
    for i, item in enumerate(learning_contents, 1):
        print(f"    {i}. [{item['category']}] [{item['source']}] {item['title'][:50]}")
    
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
    print("=== 每日早报生成完成 V3.0（优化版）===")
    print("=" * 60)

if __name__ == '__main__':
    main()

