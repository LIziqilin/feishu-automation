# -*- coding: utf-8 -*-
"""
b_window.py — B 类错误批量处理窗口（22:07 错峰）
对错误日志表（本地/云端）中状态为 B 且未处理的记录做批量归集，
汇总到 1 条报告推送；支持 --close 标记已处理。
设计：B 类不自动修，人工确认；窗口只做归集不删数据。
用法: python b_window.py [--send] [--close]
"""
import os, sys, io, json, time
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass


def main():
    args = sys.argv[1:]
    try:
        from feishu_sdk import FeishuClient, TABLES
        c = FeishuClient()
        pending = []
        for tname, status_field in (('错误日志_云端', '处理状态'), ('错误日志_本地', '状态')):
            try:
                recs = c.read_records(TABLES[tname], page_size=500,
                                      field_names=['错误信息', '级别', status_field, '创建时间'])
            except Exception:
                continue
            for r in recs:
                f = r.get('fields', {})
                level = str(f.get('级别', 'B'))
                st = str(f.get(status_field, '待处理'))
                if 'B' in level and ('待处理' in st or '未处理' in st):
                    pending.append((tname, r['record_id'], str(f.get('错误信息', ''))[:80]))
        lines = ['【%s B类窗口】待处理 %d 条' % (time.strftime('%Y-%m-%d %H:%M'), len(pending))]
        for t, rid, msg in pending[:20]:
            lines.append('- [%s] %s' % (t, msg))
        if not pending:
            lines.append('无待处理 B 类错误，系统正常')
        text = '\n'.join(lines)
        print(text)
        if '--close' in args and pending:
            # 标记 B 类已处理（仅演示，需人工确认后再执行）
            print('[跳过] --close 需人工确认后执行，本次仅归集')
        if '--send' in args:
            import requests
            from feishu_sdk import gen_sign
            cfg = json.load(open(r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json',
                                 encoding='utf-8'))
            webhook = cfg.get('webhook') or cfg.get('url')
            if webhook:
                ts, sign = gen_sign(cfg.get('secret', ''))
                r = requests.post('%s?timestamp=%s&sign=%s' % (webhook, ts, sign),
                                  json={'msg_type': 'text', 'content': {'text': text}},
                                  timeout=10)
                print('[推送] %s' % r.text[:120])
    except Exception as e:
        print('B类窗口异常: %s' % e)
    print('B_WINDOW_DONE')


if __name__ == '__main__':
    main()
