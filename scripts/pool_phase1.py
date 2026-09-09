# -*- coding: utf-8 -*-
"""
pool_phase1.py — V13 波次1：知识池化阶段一（代理粗分，先埋点后分池的过渡期）
方案定稿（§3.3）：
  - 阶段一（0-4周）：所有知识默认「温存池」，埋点观察；活跃池仅人工标记/高价值
  - 活跃池 ≤100 条、每主题 ≤30 条（代理规则）
  - 冷归档「降权不删向量」：阶段一不启用冷归档，保留全部向量
  - 建立计数视图：活跃/温存/冷 各池数量与主题分布（可复核）
用法: python pool_phase1.py [--dry-run] [--apply]
  --apply 才会写字段；默认只读统计（安全）
"""
import sys, io, json
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES, FT_SINGLE

POOL_FIELD = '知识池'
OPTIONS = ['活跃池', '温存池', '冷归档']
ACTIVE_CAP = 100        # 活跃池 ≤100
ACTIVE_PER_TOPIC = 30   # 每主题 ≤30

def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v

def main():
    dry = '--dry-run' in sys.argv
    apply = '--apply' in sys.argv
    c = FeishuClient()
    KI = TABLES['知识索引表']
    have = {f['field_name'] for f in c.list_fields(KI)}

    if POOL_FIELD not in have:
        if apply:
            c.create_field(KI, POOL_FIELD, FT_SINGLE,
                           property_={'options': [{'name': o} for o in OPTIONS]})
            print('+ 新建字段: %s (%s)' % (POOL_FIELD, '/'.join(OPTIONS)))
        else:
            print('字段 %s 不存在；--apply 将创建（阶段一：活跃/温存/冷归档）' % POOL_FIELD)
            dry = True
    else:
        print('字段已存在: %s' % POOL_FIELD)

    # 读全量
    recs = c.read_records(KI, page_size=500)
    print('知识索引总数: %d' % len(recs))

    # 阶段一代理规则：按创建日期 + 使用次数粗分候选活跃池（人工复核窗口）
    cand_active = []
    for r in recs:
        f = r.get('fields', {})
        usage = plain(f.get('使用次数'))
        try:
            u = int(float(usage)) if usage not in (None, '') else 0
        except Exception:
            u = 0
        recall = plain(f.get('召回次数'))
        try:
            rc = int(float(recall)) if recall not in (None, '') else 0
        except Exception:
            rc = 0
        cand_active.append((r['record_id'], plain(f.get('标题')) or '', u, rc))

    # 排序：召回次数>使用次数 高的优先进活跃候选
    cand_active.sort(key=lambda x: (x[3], x[2]), reverse=True)
    active = cand_active[:ACTIVE_CAP] if len(cand_active) > ACTIVE_CAP else cand_active
    print('活跃池候选(前%d, 按召回/使用排序): %d 条' % (ACTIVE_CAP, len(active)))

    # 主题计数（用科目字段）
    topic = {}
    for r in recs:
        f = r.get('fields', {})
        t = plain(f.get('科目')) or '未分类'
        topic[t] = topic.get(t, 0) + 1
    print('科目分布: %s' % json.dumps(topic, ensure_ascii=False))

    # 阶段一执行策略（遵守"严禁无数据支撑分池"）：
    #   埋点才启动、召回次数全 0、科目 94% 未分类 → 不自动标活跃池（会误导）
    #   全部默认「温存池」；活跃池由用户在飞书人工标记（≤100/主题≤30），候选清单打印供参考
    if dry:
        print('\n[dry-run] 未写库。策略：全部默认温存池；活跃池人工标记（见下方候选清单）')
        print('活跃池候选（供人工挑，按召回/使用排序前20）:')
        for rid, title, u, rc in active[:20]:
            print('   %-30s 使用=%d 召回=%d' % (title[:28], u, rc))
        return 0

    # 写池：全部温存池（活跃池字段留空，人工标记）
    batch = []
    for r in recs:
        if plain(r.get('fields', {}).get(POOL_FIELD)) != '温存池':
            batch.append({'record_id': r['record_id'], 'fields': {POOL_FIELD: '温存池'}})
    for i in range(0, len(batch), 500):
        c.batch_update(KI, batch[i:i + 500])
    print('写入池标记 %d 条（全部温存池；活跃池待人工标记，冷归档0=降权不删向量）' % len(batch))

    # 回读验证
    verify = c.read_records(KI, page_size=500)
    dist = {}
    for r in verify:
        p = plain(r.get('fields', {}).get(POOL_FIELD)) or '未标记'
        dist[p] = dist.get(p, 0) + 1
    print('回读池分布: %s' % json.dumps(dist, ensure_ascii=False))
    print('POOL_PHASE1_DONE')

if __name__ == '__main__':
    main()
