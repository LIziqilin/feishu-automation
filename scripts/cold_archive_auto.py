#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V35修复：冷归档自动执行脚本（S7-04）
功能：
1. 180天无反馈的卡片自动归档（cold_archived=true）
2. 错因"已过期"的卡片自动归档
3. 人工归档支持（命令行参数指定record_id）
4. 归档后不出题（选题逻辑已过滤cold_archived=true）
"""
import sys, os, json, subprocess, argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v19_integration import BASE_TOKEN, LARK_CLI, CARD_TABLE, FLOW_TABLE

def run_lark(args):
    cmd = [LARK_CLI, 'base'] + args + ['--base-token', BASE_TOKEN, '--as', 'user', '--format', 'json']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        return json.loads(result.stdout)
    except:
        return {'error': result.stderr[:500]}

def get_all_cards():
    """获取所有学习卡片"""
    all_cards = []
    offset = 0
    while True:
        result = run_lark(['+record-list', '--table-id', CARD_TABLE, '--limit', '200', '--offset', str(offset)])
        data = result.get('data', {})
        rows = data.get('data', [])
        fields = data.get('fields', [])
        rids = data.get('record_id_list', [])
        if not rows:
            break
        for i, row in enumerate(rows):
            record = dict(zip(fields, row))
            record['_record_id'] = rids[i] if i < len(rids) else ''
            all_cards.append(record)
        if not data.get('has_more'):
            break
        offset += len(rows)
    return all_cards

def get_last_feedback_date(card_id):
    """获取卡片最后一次答题反馈日期"""
    offset = 0
    latest_date = None
    while True:
        result = run_lark(['+record-list', '--table-id', FLOW_TABLE, '--limit', '200', '--offset', str(offset)])
        data = result.get('data', {})
        rows = data.get('data', [])
        fields = data.get('fields', [])
        if not rows:
            break
        for row in rows:
            record = dict(zip(fields, row))
            cid = record.get('卡片ID', '')
            if isinstance(cid, list):
                cid = cid[0] if cid else ''
            if cid == card_id:
                result_val = record.get('结果', '')
                if isinstance(result_val, list):
                    result_val = result_val[0] if result_val else ''
                if result_val in ('会', '不会', '模糊'):
                    ts = record.get('客户端时间戳', '') or record.get('创建时间', '')
                    if ts:
                        try:
                            if isinstance(ts, str) and 'T' in ts:
                                dt = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+08:00', ''))
                            elif isinstance(ts, (int, float)):
                                dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
                            else:
                                dt = datetime.strptime(str(ts)[:10], '%Y-%m-%d')
                            if latest_date is None or dt > latest_date:
                                latest_date = dt
                        except:
                            pass
        if not data.get('has_more'):
            break
        offset += len(rows)
    return latest_date

def archive_card(record_id, reason='自动归档'):
    """归档卡片：设置cold_archived=true"""
    patch = {
        'cold_archived': True,
        '状态': ['ARCHIVED']
    }
    result = run_lark(['+record-upsert', '--table-id', CARD_TABLE, '--record-id', record_id, '--json', json.dumps(patch, ensure_ascii=False)])
    success = result.get('ok') or result.get('code') == 0 or 'record_id' in str(result)
    return success, result

def main():
    parser = argparse.ArgumentParser(description='冷归档自动执行')
    parser.add_argument('--dry-run', action='store_true', help='只检查不执行')
    parser.add_argument('--archive-id', type=str, help='人工归档指定record_id')
    parser.add_argument('--days', type=int, default=180, help='无反馈天数阈值（默认180）')
    args = parser.parse_args()

    print('=== 冷归档自动执行（S7-04）===')
    print(f'归档阈值: {args.days}天无反馈')
    print(f'执行模式: {"检查模式(不执行)" if args.dry_run else "执行模式"}')
    print()

    # 人工归档
    if args.archive_id:
        print(f'人工归档: {args.archive_id}')
        if not args.dry_run:
            success, result = archive_card(args.archive_id, '人工归档')
            print(f'归档结果: {"成功" if success else "失败"}')
            if not success:
                print(f'错误: {str(result)[:200]}')
        else:
            print('检查模式：跳过执行')
        return

    # 自动归档
    print('【1】获取所有学习卡片...')
    cards = get_all_cards()
    print(f'卡片总数: {len(cards)}')

    to_archive = []
    now = datetime.now()

    print()
    print('【2】检查每张卡片的最后反馈时间...')
    for card in cards:
        rid = card.get('_record_id', '')
        status = card.get('状态', '')
        if isinstance(status, list):
            status = status[0] if status else ''
        cold = card.get('cold_archived', False)
        if isinstance(cold, list):
            cold = cold[0] if cold else False
        
        # 已归档的跳过
        if cold or status == 'ARCHIVED':
            continue
        
        # 检查错因"已过期"
        error_type = card.get('错因', '')
        if isinstance(error_type, list):
            error_type = error_type[0] if error_type else ''
        if error_type == '已过期':
            to_archive.append((rid, card, '错因=已过期'))
            print(f'  待归档(错因已过期): {rid} - {str(card.get("问题", ""))[:30]}')
            continue
        
        # 检查最后反馈时间
        last_feedback = get_last_feedback_date(rid)
        if last_feedback:
            days_since = (now - last_feedback).days
            if days_since >= args.days:
                to_archive.append((rid, card, f'{days_since}天无反馈'))
                print(f'  待归档({days_since}天无反馈): {rid} - {str(card.get("问题", ""))[:30]}')
        else:
            # 无反馈记录，检查创建时间
            created = card.get('创建日期', '')
            if created:
                try:
                    if isinstance(created, str) and 'T' in created:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+08:00', ''))
                    else:
                        created_dt = datetime.strptime(str(created)[:10], '%Y-%m-%d')
                    days_since_created = (now - created_dt).days
                    if days_since_created >= args.days * 2:  # 创建时间超过360天且无反馈
                        to_archive.append((rid, card, f'创建{days_since_created}天无反馈'))
                        print(f'  待归档(创建{days_since_created}天无反馈): {rid} - {str(card.get("问题", ""))[:30]}')
                except:
                    pass

    print()
    print(f'【3】待归档卡片数: {len(to_archive)}')

    if args.dry_run:
        print('检查模式：不执行归档')
        print('待归档清单:')
        for rid, card, reason in to_archive:
            print(f'  {rid}: {reason} - {str(card.get("问题", ""))[:40]}')
    else:
        print('【4】执行归档...')
        success_count = 0
        for rid, card, reason in to_archive:
            success, result = archive_card(rid, reason)
            if success:
                success_count += 1
                print(f'  ✅ 归档成功: {rid} ({reason})')
            else:
                print(f'  ❌ 归档失败: {rid} - {str(result)[:100]}')
        print(f'归档完成: 成功{success_count}/{len(to_archive)}')

    print()
    print('=== 执行完成 ===')

if __name__ == '__main__':
    main()
