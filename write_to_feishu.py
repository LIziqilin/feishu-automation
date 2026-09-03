#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写入飞书多维表格脚本
功能：读取抓取的RSS和天气数据，写入飞书多维表格
配置：在GitHub Secrets中设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET
目标表：知识索引表（table_id: tbl0NiUFeQzH2r3n）或新建外部数据表
"""

import os
import json
import requests

def get_tenant_access_token():
    """获取飞书租户访问令牌"""
    app_id = os.environ.get('FEISHU_APP_ID', '')
    app_secret = os.environ.get('FEISHU_APP_SECRET', '')
    
    if not app_id or not app_secret:
        print("未配置FEISHU_APP_ID或FEISHU_APP_SECRET")
        return None
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": app_id, "app_secret": app_secret}
    response = requests.post(url, json=payload)
    data = response.json()
    
    if data.get('code') == 0:
        return data['tenant_access_token']
    else:
        print(f"获取令牌失败: {data}")
        return None

def write_records(token, base_token, table_id, records):
    """批量写入记录到飞书多维表格"""
    if not records:
        print("无数据可写入")
        return
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_token}/tables/{table_id}/records/batch_create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 转换为飞书格式
    feishu_records = [{"fields": record} for record in records]
    payload = {"records": feishu_records}
    
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    if data.get('code') == 0:
        print(f"成功写入 {len(records)} 条记录到飞书多维表格")
    else:
        print(f"写入失败: {data}")

def main():
    base_token = os.environ.get('FEISHU_BASE_TOKEN', 'X8N1bvN3na99dFsyu0gcU8zTnHf')
    # 目标表：建议新建"外部数据采集表"，这里用知识索引表作为示例
    table_id = os.environ.get('FEISHU_TABLE_ID', 'tbl0NiUFeQzH2r3n')
    
    token = get_tenant_access_token()
    if not token:
        return
    
    # 读取RSS数据
    all_records = []
    if os.path.exists('rss_articles.json'):
        with open('rss_articles.json', 'r', encoding='utf-8') as f:
            rss_data = json.load(f)
            all_records.extend(rss_data)
    
    # 读取天气数据
    if os.path.exists('weather_data.json'):
        with open('weather_data.json', 'r', encoding='utf-8') as f:
            weather_data = json.load(f)
            all_records.extend(weather_data)
    
    if all_records:
        write_records(token, base_token, table_id, all_records)
    else:
        print("无任何数据可写入")

if __name__ == '__main__':
    main()
