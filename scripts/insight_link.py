# -*- coding: utf-8 -*-
"""
insight_link.py — 洞察关联回填（12:37 错峰）
把「洞察笔记表」的每条洞察与「知识索引表」做标题/关键词匹配关联，
回填 来源知识ID 字段（若无匹配则置 未关联）。
幂等：仅更新无来源知识ID 的记录。
用法: python insight_link.py [--dry-run]
"""
import os, sys, io, json, time
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass


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
        insights = c.read_records(TABLES['洞察笔记表'], page_size=500,
                                  field_names=['AI摘要', '内容', '关联知识'])
        idx = c.read_records(TABLES['知识索引表'], page_size=500,
                             field_names=['标题'])
        title_to_id = {}
        for r in idx:
            t = plain(r.get('fields', {}).get('标题'))
            if t:
                title_to_id[str(t).strip()] = r['record_id']
        updates = []
        for ins in insights:
            f = ins.get('fields', {})
            if plain(f.get('关联知识')):
                continue  # 已关联
            title = str(plain(f.get('AI摘要')) or plain(f.get('内容')) or '')[:50]
            matched = None
            for t, tid in title_to_id.items():
                if title and (t in title or title in t):
                    matched = tid
                    break
            updates.append((ins['record_id'], matched))
        print('洞察总数 %d，待关联 %d，可匹配 %d' % (
            len(insights), len(updates), sum(1 for _, m in updates if m)))
        if not dry:
            for rid, mid in updates:
                try:
                    c.update_record(TABLES['洞察笔记表'], rid,
                                    {'关联知识': mid or '未关联'})
                except Exception as e:
                    print('更新失败 %s: %s' % (rid, e))
            print('已回填 %d 条' % len(updates))
        else:
            print('[dry-run] 未写库')
    except Exception as e:
        print('洞察关联异常: %s' % e)
    print('INSIGHT_LINK_DONE')


if __name__ == '__main__':
    main()
