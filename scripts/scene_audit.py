# -*- coding: utf-8 -*-
"""
scene_audit.py — V13 波次2 应用场景两段式周检
REVIEWING 卡场景填充率（验收>=50%）；MASTERED 毕业必须 三选一（场景/费曼/实战）
用法: python scene_audit.py [--threshold 50]
"""
import sys, io, argparse
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
import study_planner as sp


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=int, default=50)
    a = ap.parse_args()
    c = FeishuClient()
    cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                           field_names=['卡片问题正面', '卡片状态', '应用场景', '费曼自检', '实战留痕'])
    reviewing, mastered = [], []
    for r in cards:
        f = r.get('fields', {})
        st = plain(f.get('卡片状态'))
        scene = plain(f.get('应用场景'))
        has_output = any(plain(f.get(k)) for k in ('应用场景', '费曼自检', '实战留痕'))
        title = str(plain(f.get('卡片问题正面')))[:16]
        if st == 'REVIEWING':
            reviewing.append((title, bool(scene)))
        elif st == 'MASTERED':
            mastered.append((title, has_output))
    total = len(reviewing)
    filled = sum(1 for _, s in reviewing if s)
    rate = filled * 100 / total if total else 100.0
    print('=== 应用场景两段式周检 ===')
    print('REVIEWING 卡 %d 张：场景填充 %d 张 = %.0f%%（验收阈值 >=%d%%）'
          % (total, filled, rate, a.threshold))
    for t, s in reviewing:
        print('  [%s] %s' % ('✓' if s else '✗未填', t))
    blocked = [t for t, o in mastered if not o]
    print('MASTERED 卡 %d 张：毕业阻断 %d 张（缺 场景/费曼/实战 三选一）'
          % (len(mastered), len(blocked)))
    for t in blocked:
        print('  [阻断] %s' % t)
    ok = rate >= a.threshold and not blocked
    print('AUDIT_PASS' if ok else 'AUDIT_NEEDS_ACTION')


if __name__ == '__main__':
    main()
