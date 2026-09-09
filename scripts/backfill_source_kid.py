# -*- coding: utf-8 -*-
"""
backfill_source_kid.py — V13 波次2 学习卡「来源知识ID」回填
按标题包含匹配（学习卡标题 ↔ 知识索引标题），把匹配到的知识索引 record_id 写入学习卡来源知识ID
- 匹配规则：学习卡标题核心词（去标点后>=4字）被知识索引标题包含，或反向包含
- 幂等：已有来源知识ID的卡跳过
用法: python backfill_source_kid.py [--dry-run] [--apply]
"""
import sys, io, argparse, re
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def norm(s):
    return re.sub(r'[\s，。？！、,.!?【】\[\]（）()：:""\'\']+', '', str(s or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    c = FeishuClient()

    cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                           field_names=['卡片问题正面', '来源知识ID', '科目'])
    idx = c.read_records(TABLES['知识索引表'], page_size=500,
                         field_names=['标题', '科目'])
    # 建知识索引标题索引（按归一化标题）
    idx_by_title = {}
    for r in idx:
        t = norm(plain(r.get('fields', {}).get('标题')))
        if len(t) >= 4:
            idx_by_title.setdefault(t, []).append(r['record_id'])

    matches = []
    for r in cards:
        f = r.get('fields', {})
        rid = r['record_id']
        if plain(f.get('来源知识ID')):
            continue
        q = norm(plain(f.get('卡片问题正面')))
        if len(q) < 4:
            continue
        hit = None
        # 精确标题匹配优先
        if q in idx_by_title:
            hit = idx_by_title[q][0]
        else:
            # 包含匹配：知识索引标题包含问题核心，或问题含知识索引标题
            for t, ids in idx_by_title.items():
                if t in q or (len(t) >= 6 and q in t):
                    hit = ids[0]
                    break
        if hit:
            matches.append((rid, hit, str(plain(f.get('卡片问题正面')))[:18]))
    print('可回填 %d 张学习卡:' % len(matches))
    for rid, kid, title in matches:
        print('  %s <- %s (%s)' % (title, kid, rid))
    if a.dry_run or not a.apply:
        print('\n[dry-run] 未写库。--apply 执行回填')
        return 0
    for rid, kid, title in matches:
        c.update_record(TABLES['学习卡片表'], rid, {'来源知识ID': kid})
    print('已回填 %d 张' % len(matches))
    print('BACKFILL_DONE')


if __name__ == '__main__':
    main()
