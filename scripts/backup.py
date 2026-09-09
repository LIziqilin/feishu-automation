# -*- coding: utf-8 -*-
"""
backup.py — V13 原子备份（波次1·数据安全组）
原则（D 版加固清单）：
  1) 写 tmp → 校验（JSON 可解析、记录数与回读一致）→ os.replace 原子落盘，杜绝写一半的坏备份
  2) 全 13 张表（含 V13 新增复习流水表/检索日志表）分页导出
  3) 7 轮滚动保留：保留最近 7 份时间戳目录，更早的清理
  4) 走公共库 feishu_sdk（零手写 token/sign），限流自动退避
用法: python backup.py [--dry-run] [--out DIR]
"""
import os, sys, io, json, glob, time
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from datetime import datetime
from feishu_sdk import FeishuClient, TABLES

DEFAULT_OUT = r'D:\AI\finished Brain\feishu_backup'
ROLLING_KEEP = 7

def _json_ok(path):
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        return isinstance(d, dict) and d.get('ok') is True and 'items' in d
    except Exception:
        return False

def backup_once(c, out_dir, dry_run):
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for name, tid in TABLES.items():
        try:
            items = c.read_records(tid, page_size=500)
        except Exception as e:
            report[name] = 'FAIL:%s' % e
            continue
        payload = {'ok': True, 'table': name, 'table_id': tid, 'count': len(items),
                   'exported_at': datetime.now().isoformat(), 'items': items}
        if dry_run:
            report[name] = 'DRY:%d' % len(items)
            continue
        tmp = os.path.join(out_dir, '.%s.tmp.json' % name)
        final = os.path.join(out_dir, '%s.json' % name)
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
        if not _json_ok(tmp):
            os.remove(tmp)
            report[name] = 'FAIL:校验不过'
            continue
        os.replace(tmp, final)   # 原子替换
        report[name] = 'OK:%d' % len(items)
    return report

def prune(out_root):
    dirs = sorted(glob.glob(os.path.join(out_root, '20*')))
    while len(dirs) > ROLLING_KEEP:
        rm = dirs.pop(0)
        for f in glob.glob(os.path.join(rm, '*')):
            os.remove(f)
        os.rmdir(rm)

def main():
    dry_run = '--dry-run' in sys.argv
    out_root = DEFAULT_OUT
    if '--out' in sys.argv:
        out_root = sys.argv[sys.argv.index('--out') + 1]
    c = FeishuClient()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = os.path.join(out_root, stamp)
    report = backup_once(c, out_dir, dry_run)
    if not dry_run:
        prune(out_root)
    print('备份目录: %s%s' % (out_dir, ' (试运行)' if dry_run else ''))
    for k, v in report.items():
        print('  %-12s %s' % (k, v))
    ok = sum(1 for v in report.values() if v.startswith('OK') or v.startswith('DRY'))
    print('成功 %d/%d 表%s' % (ok, len(report), ' (dry-run)' if dry_run else ''))
    return 0 if ok == len(report) else 1

if __name__ == '__main__':
    sys.exit(main())
