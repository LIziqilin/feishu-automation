#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
H2-01 回归基线快照生成器
固化当前全量回归结果（数据基线 + 不变量断言 + 关键指标）为基线文件
验证：基线文件可重复生成，两次生成结果一致
"""
import sys, os, json, hashlib
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from v19_integration import BASE_TOKEN, LARK_CLI
from invariant_assertions import InvariantAssertion

# 表ID定义
TABLES = {
    "学习卡片表": "tblpLvxyYpDJgF92",
    "复习流水表": "tblbznzCSpPhSz93",
    "系统事件日志表": "tblPreh1ipB9LQpf",
    "任务总表": "tblz3H4lV7PCrBrX",
    "知识索引表": "tbl0NiUFeQzH2r3n",
    "系统健康表": "tblxJMndPNtZ7XyG",
    "系统心跳": "tblJmm0ZIgqlYmyt",
    "洞察笔记表": "tblaqKBl87V9C0q1",
    "自动化队列表": "tblN2nL4hP9Qz7fK",
}


def run_cmd(cmd, timeout=60):
    """执行命令"""
    try:
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{c}"' if (" " in c or "\\" in c) else c for c in cmd)
        else:
            cmd_str = cmd
        import subprocess
        r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)


def get_table_record_count(table_id):
    """获取表记录数（分页计数）"""
    total = 0
    offset = 0
    limit = 200
    while True:
        cmd = [LARK_CLI, 'base', '+record-list',
               '--base-token', BASE_TOKEN, '--table-id', table_id,
               '--as', 'user', '--limit', str(limit), '--offset', str(offset),
               '--format', 'json']
        ok, stdout, _ = run_cmd(cmd, timeout=30)
        if not ok:
            break
        try:
            data = json.loads(stdout)
            record_ids = data.get('data', {}).get('record_id_list', [])
            total += len(record_ids)
            has_more = data.get('data', {}).get('has_more', False)
            if not has_more or len(record_ids) < limit:
                break
            offset += limit
        except:
            break
    return total


def get_table_fields(table_id):
    """获取表字段列表"""
    cmd = [LARK_CLI, 'base', '+field-list',
           '--base-token', BASE_TOKEN, '--table-id', table_id,
           '--as', 'user', '--format', 'json']
    ok, stdout, _ = run_cmd(cmd, timeout=30)
    if not ok:
        return []
    try:
        data = json.loads(stdout)
        return data.get('data', {}).get('fields', [])
    except:
        return []


def get_all_records(table_id, max_records=2000):
    """获取表所有记录（分页）"""
    all_records = []
    all_fields = []
    offset = 0
    limit = 200
    while len(all_records) < max_records:
        cmd = [LARK_CLI, 'base', '+record-list',
               '--base-token', BASE_TOKEN, '--table-id', table_id,
               '--as', 'user', '--limit', str(limit), '--offset', str(offset),
               '--format', 'json']
        ok, stdout, _ = run_cmd(cmd, timeout=60)
        if not ok:
            break
        try:
            data = json.loads(stdout)
            fields = data.get('data', {}).get('fields', [])
            records_raw = data.get('data', {}).get('data', [])
            record_ids = data.get('data', {}).get('record_id_list', [])
            if not all_fields:
                all_fields = fields
            for i, row in enumerate(records_raw):
                rec = {}
                for j, field in enumerate(fields):
                    if j < len(row):
                        val = row[j]
                        if isinstance(val, list) and len(val) > 0:
                            val = val[0]
                        elif isinstance(val, list) and len(val) == 0:
                            val = ''
                        rec[field] = val
                if i < len(record_ids):
                    rec['_record_id'] = record_ids[i]
                all_records.append(rec)
            has_more = data.get('data', {}).get('has_more', False)
            if not has_more or len(records_raw) < limit:
                break
            offset += limit
        except:
            break
    return all_fields, all_records


def calculate_field_null_rate(records, fields):
    """计算字段空值率（fields可以是字符串列表或字典列表）"""
    if not records:
        return {}
    null_rates = {}
    for field in fields:
        # 处理字符串或字典类型的字段名
        if isinstance(field, str):
            field_name = field
        elif isinstance(field, dict):
            field_name = field.get('name', '')
        else:
            continue
        if not field_name or field_name.startswith('_'):
            continue
        null_count = 0
        for rec in records:
            val = rec.get(field_name)
            if val is None or val == '' or val == []:
                null_count += 1
        null_rate = round(null_count / len(records) * 100, 2)
        null_rates[field_name] = {
            "null_count": null_count,
            "total": len(records),
            "null_rate_percent": null_rate
        }
    return null_rates


def calculate_status_distribution(records, status_field):
    """计算状态分布"""
    distribution = {}
    for rec in records:
        status = rec.get(status_field, '未知')
        if status is None or status == '':
            status = '空'
        distribution[status] = distribution.get(status, 0) + 1
    return distribution


def generate_baseline():
    """生成回归基线快照"""
    print('=' * 60)
    print('H2-01 回归基线快照生成')
    print('=' * 60)

    baseline = {
        "baseline_version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "base_token": BASE_TOKEN,
        "table_counts": {},
        "card_status_distribution": {},
        "flow_result_distribution": {},
        "flow_source_distribution": {},
        "field_null_rates": {},
        "invariant_checks": {},
        "summary": {}
    }

    # 1. 各表记录数
    print('\n【1/5】收集各表记录数...')
    for name, tid in TABLES.items():
        count = get_table_record_count(tid)
        baseline["table_counts"][name] = count
        print(f'  {name}: {count}条')

    # 2. 学习卡状态分布
    print('\n【2/5】收集学习卡状态分布...')
    card_fields, card_records = get_all_records(TABLES["学习卡片表"])
    card_status = calculate_status_distribution(card_records, '卡片状态')
    baseline["card_status_distribution"] = card_status
    print(f'  状态分布: {card_status}')

    # 3. 流水结果构成
    print('\n【3/5】收集流水结果构成...')
    flow_fields, flow_records = get_all_records(TABLES["复习流水表"])
    flow_result = calculate_status_distribution(flow_records, '结果')
    flow_source = calculate_status_distribution(flow_records, '来源')
    baseline["flow_result_distribution"] = flow_result
    baseline["flow_source_distribution"] = flow_source
    print(f'  结果分布: {flow_result}')
    print(f'  来源分布: {flow_source}')

    # 4. 关键字段空值率（学习卡表 + 流水表）
    print('\n【4/5】计算关键字段空值率...')
    card_null = calculate_field_null_rate(card_records, card_fields)
    flow_null = calculate_field_null_rate(flow_records, flow_fields)
    baseline["field_null_rates"]["学习卡片表"] = card_null
    baseline["field_null_rates"]["复习流水表"] = flow_null
    # 只打印空值率>50%的字段
    high_null_cards = {k: v for k, v in card_null.items() if v["null_rate_percent"] > 50}
    high_null_flows = {k: v for k, v in flow_null.items() if v["null_rate_percent"] > 50}
    print(f'  学习卡表空值率>50%的字段: {len(high_null_cards)}个')
    print(f'  流水表空值率>50%的字段: {len(high_null_flows)}个')

    # 5. 不变量断言检查
    print('\n【5/5】运行不变量断言检查...')
    checker = InvariantAssertion()
    invariant_results = checker.check_all()
    baseline["invariant_checks"] = {
        k: {"pass": v.get("pass")} for k, v in invariant_results.items() if k != '_summary'
    }
    baseline["invariant_checks"]["_summary"] = invariant_results.get("_summary", {})
    print(f'  不变量检查: {invariant_results["_summary"]}')

    # 汇总
    baseline["summary"] = {
        "total_tables": len(baseline["table_counts"]),
        "total_records": sum(baseline["table_counts"].values()),
        "card_count": baseline["table_counts"].get("学习卡片表", 0),
        "flow_count": baseline["table_counts"].get("复习流水表", 0),
        "event_log_count": baseline["table_counts"].get("系统事件日志表", 0),
        "invariant_all_pass": baseline["invariant_checks"].get("_summary", {}).get("all_pass", False),
    }

    # 计算基线哈希（用于比对两次生成是否一致，排除时间戳字段）
    baseline_for_hash = {k: v for k, v in baseline.items() if k != 'generated_at'}
    baseline_str = json.dumps(baseline_for_hash, ensure_ascii=False, sort_keys=True, default=str)
    baseline["_baseline_hash"] = hashlib.md5(baseline_str.encode('utf-8')).hexdigest()

    return baseline


def main():
    # 生成第一次基线
    print('\n>>> 生成第一次基线...')
    baseline1 = generate_baseline()

    # 保存基线文件
    baseline_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'regression_baseline.json')
    with open(baseline_file, 'w', encoding='utf-8') as f:
        json.dump(baseline1, f, ensure_ascii=False, indent=2)
    print(f'\n基线文件已保存: {baseline_file}')
    print(f'基线哈希: {baseline1["_baseline_hash"]}')

    # 生成第二次基线（验证可重复性）
    print('\n>>> 生成第二次基线（验证可重复性）...')
    baseline2 = generate_baseline()

    # 比对两次基线
    hash1 = baseline1["_baseline_hash"]
    hash2 = baseline2["_baseline_hash"]
    reproducible = (hash1 == hash2)
    print(f'\n【可重复性验证】')
    print(f'  第一次哈希: {hash1}')
    print(f'  第二次哈希: {hash2}')
    print(f'  两次一致: {"✅ 是" if reproducible else "❌ 否"}')

    if not reproducible:
        # 找出差异
        for key in baseline1:
            if key == '_baseline_hash':
                continue
            if baseline1.get(key) != baseline2.get(key):
                print(f'  差异字段: {key}')

    # 输出基线摘要
    print(f'\n{"=" * 60}')
    print('基线摘要')
    print(f'{"=" * 60}')
    print(f'  生成时间: {baseline1["generated_at"]}')
    print(f'  表数量: {baseline1["summary"]["total_tables"]}')
    print(f'  总记录数: {baseline1["summary"]["total_records"]}')
    print(f'  学习卡: {baseline1["summary"]["card_count"]}条')
    print(f'  复习流水: {baseline1["summary"]["flow_count"]}条')
    print(f'  事件日志: {baseline1["summary"]["event_log_count"]}条')
    print(f'  不变量全部通过: {"✅" if baseline1["summary"]["invariant_all_pass"] else "❌"}')
    print(f'  可重复生成: {"✅" if reproducible else "❌"}')
    print(f'  基线文件: {baseline_file}')

    return 0 if reproducible else 1


if __name__ == '__main__':
    sys.exit(main())
