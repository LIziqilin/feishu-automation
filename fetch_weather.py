#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天气数据抓取脚本
功能：抓取指定城市的天气数据，保存为JSON供后续写入飞书
配置：在GitHub Secrets中设置 WEATHER_API_KEY（和风天气API密钥）
免费API：https://dev.qweather.com/  每天1000次免费调用
"""

import os
import json
import requests
from datetime import datetime

def fetch_weather():
    api_key = os.environ.get('WEATHER_API_KEY', '')
    city = os.environ.get('WEATHER_CITY', 'xian')
    
    if not api_key:
        print("未配置WEATHER_API_KEY，跳过天气抓取")
        return []
    
    try:
        # 和风天气实时天气API（免费版）
        url = f"https://devapi.qweather.com/v7/weather/now?location={city}&key={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('code') == '200':
            now = data['now']
            weather_data = [{
                '日期': datetime.now().strftime('%Y-%m-%d'),
                '城市': city,
                '天气': now.get('text', ''),
                '温度': now.get('temp', ''),
                '体感温度': now.get('feelsLike', ''),
                '湿度': now.get('humidity', ''),
                '风向': now.get('windDir', ''),
                '风力': now.get('windScale', ''),
                '抓取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '类型': '天气数据'
            }]
            
            with open('weather_data.json', 'w', encoding='utf-8') as f:
                json.dump(weather_data, f, ensure_ascii=False, indent=2)
            
            print(f"天气抓取成功: {city} {now.get('text')} {now.get('temp')}°C")
            return weather_data
        else:
            print(f"天气API返回错误: {data.get('code')} {data.get('message')}")
            return []
    except Exception as e:
        print(f"天气抓取失败: {e}")
        return []

if __name__ == '__main__':
    fetch_weather()
