#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习类内容抓取脚本
功能：抓取RSS资讯，按关键词过滤出学习效率、思维模式、思维框架、沟通技巧、表达方式相关内容
配置：在GitHub Secrets中设置 RSS_URLS（多个URL用逗号分隔）
"""

import os
import json
import feedparser
from datetime import datetime

# 关键词分类配置
KEYWORD_CATEGORIES = {
    "学习效率": ["学习效率", "学习方法", "记忆", "专注力", "时间管理", "费曼", "艾宾浩斯", "复盘", "知识管理", "元认知"],
    "思维模式": ["思维模式", "认知", "心智模型", "底层逻辑", "第一性原理", "系统思维", "批判性思维", "成长型思维"],
    "思维框架": ["思维框架", "分析框架", "决策模型", "结构化思维", "MECE", "金字塔原理", "SWOT", "PDCA", "5W2H"],
    "沟通技巧": ["沟通技巧", "表达", "演讲", "谈判", "说服力", "倾听", "反馈", "非暴力沟通", "高情商"],
    "表达方式": ["表达方式", "写作", "文案", "逻辑表达", "结构化表达", "讲故事", "隐喻", "类比"]
}

# 所有关键词合并
ALL_KEYWORDS = []
for keywords in KEYWORD_CATEGORIES.values():
    ALL_KEYWORDS.extend(keywords)

def classify_article(title, summary):
    """根据标题和摘要判断文章分类"""
    content = (title + " " + summary).lower()
    categories = []
    for category, keywords in KEYWORD_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in content:
                categories.append(category)
                break
    return categories if categories else ["其他"]

def fetch_rss():
    rss_urls = os.environ.get('RSS_URLS', '').split(',')
    rss_urls = [url.strip() for url in rss_urls if url.strip()]
    
    # 默认RSS源（如果未配置）
    if not rss_urls:
        rss_urls = [
            "https://36kr.com/feed",
            "https://sspai.com/feed",
            "https://daily.zhihu.com/feed"
        ]
        print("未配置RSS_URLS，使用默认源")
    
    articles = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get('title', url)
            for entry in feed.entries[:10]:  # 每个源最多取10条
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                categories = classify_article(title, summary)
                
                # 只保留与学习相关的内容（排除"其他"分类）
                if "其他" in categories and len(categories) == 1:
                    continue
                
                article = {
                    '标题': title,
                    '来源': source,
                    '链接': entry.get('link', ''),
                    '摘要': summary[:300],
                    '分类': "、".join(categories),
                    '发布时间': entry.get('published', datetime.now().strftime('%Y-%m-%d')),
                    '抓取时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    '类型': '学习内容'
                }
                articles.append(article)
            print(f"成功抓取 {source}: {len(feed.entries[:10])} 条，过滤后保留相关内容")
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
    
    # 按分类排序
    category_order = ["学习效率", "思维模式", "思维框架", "沟通技巧", "表达方式"]
    articles.sort(key=lambda x: category_order.index(x['分类'].split('、')[0]) if x['分类'].split('、')[0] in category_order else 99)
    
    # 保存到文件
    with open('learning_articles.json', 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"共抓取 {len(articles)} 条学习相关内容，已保存到 learning_articles.json")
    return articles

if __name__ == '__main__':
    fetch_rss()
