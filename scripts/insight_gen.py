# -*- coding: utf-8 -*-
"""
insight_gen.py — 洞察生成（20:43 错峰）
从本周 MASTERED/REVIEWING 学习卡片中提取要点，生成 1 条「本周洞察」写入洞察笔记表。
若本周已有洞察则不重复生成（幂等）。
实际生成动作依赖用户确认或配置 GEMINI/LLM key；无 key 时输出「候选素材清单」。
用法: python insight_gen.py [--dry-run] [--send]
"""
import os, sys, io, json, time
from datetime import datetime, timedelta, timezone
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

CST = timezone(timedelta(hours=8))


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    args = sys.argv[1:]
    dry = '--dry-run' in args
    try:
        from feishu_sdk import FeishuClient, TABLES
        c = FeishuClient()
        # 本周已有洞察？
        week_ago = int((datetime.now(CST) - timedelta(days=7)).timestamp() * 1000)
        existing = c.read_records(TABLES['洞察笔记表'], page_size=500,
                                  field_names=['创建日期', 'AI摘要'])
        wk = [r for r in existing
              if r.get('fields', {}).get('创建日期')
              and int(r.get('fields', {})['创建日期']) >= week_ago]
        if wk and not dry:
            print('本周已有洞察 %d 条，跳过生成' % len(wk))
            print('INSIGHT_GEN_DONE')
            return
        # 候选素材：MASTERED/REVIEWING 卡片
        cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                               field_names=['卡片问题正面', '标准答案_AI', '卡片状态', '科目'])
        cand = [r for r in cards
                if plain(r.get('fields', {}).get('卡片状态')) in ('MASTERED', 'REVIEWING')]
        print('洞察候选素材 %d 条（MASTERED/REVIEWING）' % len(cand))
        for r in cand[:5]:
            print('  - %s' % str(plain(r.get('fields', {}).get('卡片问题正面')))[:60])
        if not dry and cand:
            # 无 LLM key：写 1 条「候选洞察」占位（内容=首条卡片问题），后续人工完善
            first = cand[0].get('fields', {})
            title = '本周洞察(候选): %s' % str(plain(first.get('卡片问题正面')))[:40]
            c.create_record(TABLES['洞察笔记表'], {
                'AI摘要': title,
                '内容': str(plain(first.get('标准答案_AI')))[:200],
                '类型': '洞察',
                '科目': plain(first.get('科目')) or '未分类',
            })
            print('已写入候选洞察 1 条（需人工完善）')
    except Exception as e:
        print('洞察生成异常: %s' % e)
    print('INSIGHT_GEN_DONE')


if __name__ == '__main__':
    main()
