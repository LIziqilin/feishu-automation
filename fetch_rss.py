#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS资讯抓取脚本
功能：抓取指定RSS源的最新文章，保存为JSON供后续写入飞书
配置：在GitHub Secrets中设置 RSS_URLS（多个URL用逗号分隔）
"""

import os
import json
import feedparser
from datetime import datetime

def fetch_rss():
    rss_urls = os.environ.get('RSS_URLS', '').split(',')
    rss_urls = [url.strip() for url in rss_urls if url.strip()]
    
    if not rss_urls:
        print("未配置RSS_URLS，跳过RSS抓取")
        return []
    
    articles = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get('title', url)
            for entry in feed.entries[:5]:  # 每个源最多取5条
                article = {
                    '标题': entry.get('title', ''),
                    '来源': source,
                    '链接': entry.get('link', ''),
                    '摘要': entry.get('summary', '')[:200],
                    '发布时间': entry.get('published', datetime.now().strftime('%Y-%m-%d')),
                    '抓取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    '类型': 'RSS资讯'
                }
                articles.append(article)
            print(f"成功抓取 {source}: {len(feed.entries[:5])} 条")
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    
    # 保存到文件
    with open('rss_articles.json', 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"共抓取 {len(articles)} 条RSS资讯，已保存到 rss_articles.json")
    return articles

if __name__ == '__main__':
    fetch_rss()
