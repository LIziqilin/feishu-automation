#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
H1-01 核心不变量断言模块
目标：把"靠人发现"变成"代码自动拦截"

三个核心不变量：
1. 流水表记录数在 derive 执行前后不变（防 derive 违规写流水）
2. 事件溯源表无白名单外枚举值（DERIVED/ERROR/TEST_ 一律拒绝）
3. 学习卡表无 formula 类型字段

使用方式：
    from invariant_assertions import InvariantAssertion
    checker = InvariantAssertion()
    result = checker.check_all()
    # 或在 derive 前后调用：
    checker.assert_flow_count_unchanged(before_count)
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from v19_integration import BASE_TOKEN, LARK_CLI

# 白名单定义
SOURCE_WHITELIST = {'derive', 'parser', 'selection', 'monitor', 'alert', 'user', 'system', 'migration'}
# 注意：test 不在白名单中，测试来源应被拒绝
LOG_TYPE_WHITELIST = {'RETRIEVAL', 'INSTRUCTION', 'ALERT', 'DEGRADE', 'AUDIT', 'USER_STATE', 'SYSTEM'}
# 注意：ERROR/WARN/DEBUG 不在白名单中，应使用 severity 字段而非 log_type

# 表ID
FLOW_TABLE_ID = "tblbznzCSpPhSz93"       # 复习流水表
EVENT_LOG_TABLE_ID = "tblPreh1ipB9LQpf"  # 系统事件日志表
CARD_TABLE_ID = "tblpLvxyYpDJgF92"        # 学习卡片表


class InvariantViolation(Exception):
    """不变量违规异常"""
    def __init__(self, invariant_name, message, details=None):
        self.invariant_name = invariant_name
        self.message = message
        self.details = details or {}
        super().__init__(f"[{invariant_name}] {message}")


class InvariantAssertion:
    """核心不变量断言检查器"""

    def __init__(self, base_token=None):
        self.base_token = base_token or BASE_TOKEN
        self.violations = []

    def _run_cmd(self, cmd, timeout=60):
        """执行命令"""
        try:
            if isinstance(cmd, list):
                cmd_str = " ".join(f'"{c}"' if (" " in c or "\\" in c) else c for c in cmd)
            else:
                cmd_str = cmd
            r = subprocess.run(cmd_str, capture_output=True, timeout=timeout, shell=True)
            stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
            stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
            return r.returncode == 0, stdout, stderr
        except Exception as e:
            return False, "", str(e)

    def get_table_record_count(self, table_id):
        """获取表记录数（通过+record-list分页计数）"""
        total = 0
        offset = 0
        limit = 200
        while True:
            cmd = [LARK_CLI, 'base', '+record-list',
                   '--base-token', self.base_token, '--table-id', table_id,
                   '--as', 'user', '--limit', str(limit), '--offset', str(offset),
                   '--format', 'json']
            ok, stdout, _ = self._run_cmd(cmd, timeout=30)
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

    def get_table_fields(self, table_id):
        """获取表字段列表"""
        cmd = [LARK_CLI, 'base', '+field-list',
               '--base-token', self.base_token, '--table-id', table_id,
               '--as', 'user', '--format', 'json']
        ok, stdout, _ = self._run_cmd(cmd, timeout=30)
        if not ok:
            return []
        try:
            data = json.loads(stdout)
            return data.get('data', {}).get('fields', [])
        except:
            return []

    def get_all_records(self, table_id, max_records=2000):
        """获取表所有记录（分页获取，最多2000条）"""
        all_records = []
        all_fields = []
        offset = 0
        limit = 200
        while len(all_records) < max_records:
            cmd = [LARK_CLI, 'base', '+record-list',
                   '--base-token', self.base_token, '--table-id', table_id,
                   '--as', 'user', '--limit', str(limit), '--offset', str(offset),
                   '--format', 'json']
            ok, stdout, _ = self._run_cmd(cmd, timeout=60)
            if not ok:
                break
            try:
                data = json.loads(stdout)
                fields = data.get('data', {}).get('fields', [])
                records_raw = data.get('data', {}).get('data', [])
                record_ids = data.get('data', {}).get('record_id_list', [])
                if not all_fields:
                    all_fields = fields
                # 转换为字典列表
                for i, row in enumerate(records_raw):
                    rec = {}
                    for j, field in enumerate(fields):
                        if j < len(row):
                            val = row[j]
                            # 处理select类型的数组格式：["test"] -> "test"
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

    # ========== 不变量1：流水表记录数不变 ==========
    def assert_flow_count_unchanged(self, before_count, context=""):
        """断言流水表记录数不变（防 derive 违规写流水）"""
        after_count = self.get_table_record_count(FLOW_TABLE_ID)
        if after_count != before_count:
            msg = f"流水表记录数变更: 前={before_count}, 后={after_count}, 差值={after_count - before_count}"
            if context:
                msg += f" (上下文: {context})"
            raise InvariantViolation("FLOW_COUNT_UNCHANGED", msg, {
                "before": before_count, "after": after_count, "context": context
            })
        return True

    def check_flow_count_snapshot(self):
        """获取流水表记录数快照（用于前后对比）"""
        return self.get_table_record_count(FLOW_TABLE_ID)

    # ========== 不变量2：事件溯源表枚举值白名单 ==========
    def assert_event_log_enum_whitelist(self):
        """断言事件溯源表无白名单外枚举值"""
        fields, records = self.get_all_records(EVENT_LOG_TABLE_ID)
        if not records:
            return True

        violations = []
        for rec in records:
            source = rec.get('source', '')
            log_type = rec.get('log_type', '')

            # source 白名单检查
            if source and source not in SOURCE_WHITELIST:
                violations.append({
                    "record_id": rec.get('_record_id', ''),
                    "field": "source",
                    "value": source,
                    "whitelist": list(SOURCE_WHITELIST),
                    "reason": f"source='{source}' 不在白名单中"
                })

            # log_type 白名单检查
            if log_type and log_type not in LOG_TYPE_WHITELIST:
                violations.append({
                    "record_id": rec.get('_record_id', ''),
                    "field": "log_type",
                    "value": log_type,
                    "whitelist": list(LOG_TYPE_WHITELIST),
                    "reason": f"log_type='{log_type}' 不在白名单中（应使用severity字段）"
                })

        if violations:
            msg = f"事件溯源表发现 {len(violations)} 条白名单外枚举值"
            raise InvariantViolation("EVENT_LOG_ENUM_WHITELIST", msg, {
                "violations": violations[:10],  # 最多显示10条
                "total_violations": len(violations)
            })
        return True

    # ========== 不变量3：学习卡表无 formula 字段 ==========
    def assert_no_formula_fields_in_cards(self):
        """断言学习卡表无 formula 类型字段"""
        fields = self.get_table_fields(CARD_TABLE_ID)
        formula_fields = [f for f in fields if f.get('type') == 'formula']

        if formula_fields:
            msg = f"学习卡表发现 {len(formula_fields)} 个 formula 类型字段"
            raise InvariantViolation("NO_FORMULA_FIELDS", msg, {
                "formula_fields": [f.get('name') for f in formula_fields]
            })
        return True

    # ========== 综合检查 ==========
    def check_all(self, raise_on_failure=False):
        """运行全部不变量检查"""
        self.violations = []
        results = {}

        # 不变量1：流水表记录数（只做快照，不对比）
        try:
            flow_count = self.check_flow_count_snapshot()
            results['FLOW_COUNT_SNAPSHOT'] = {'pass': True, 'count': flow_count}
        except Exception as e:
            results['FLOW_COUNT_SNAPSHOT'] = {'pass': False, 'error': str(e)}
            self.violations.append(('FLOW_COUNT_SNAPSHOT', str(e)))

        # 不变量2：事件溯源表枚举白名单
        try:
            self.assert_event_log_enum_whitelist()
            results['EVENT_LOG_ENUM_WHITELIST'] = {'pass': True}
        except InvariantViolation as e:
            results['EVENT_LOG_ENUM_WHITELIST'] = {'pass': False, 'error': str(e), 'details': e.details}
            self.violations.append(('EVENT_LOG_ENUM_WHITELIST', str(e)))
        except Exception as e:
            results['EVENT_LOG_ENUM_WHITELIST'] = {'pass': False, 'error': str(e)}
            self.violations.append(('EVENT_LOG_ENUM_WHITELIST', str(e)))

        # 不变量3：学习卡表无 formula 字段
        try:
            self.assert_no_formula_fields_in_cards()
            results['NO_FORMULA_FIELDS'] = {'pass': True}
        except InvariantViolation as e:
            results['NO_FORMULA_FIELDS'] = {'pass': False, 'error': str(e), 'details': e.details}
            self.violations.append(('NO_FORMULA_FIELDS', str(e)))
        except Exception as e:
            results['NO_FORMULA_FIELDS'] = {'pass': False, 'error': str(e)}
            self.violations.append(('NO_FORMULA_FIELDS', str(e)))

        # 汇总
        all_pass = all(r.get('pass', False) for r in results.values())
        results['_summary'] = {
            'total': len(results) - 1,  # 减去_summary
            'passed': sum(1 for k, v in results.items() if k != '_summary' and v.get('pass')),
            'failed': sum(1 for k, v in results.items() if k != '_summary' and not v.get('pass')),
            'all_pass': all_pass
        }

        if raise_on_failure and not all_pass:
            raise InvariantViolation("ALL_INVARIANTS", "存在不变量违规", results)

        return results


def main():
    """命令行入口：运行全部不变量检查"""
    print('=' * 60)
    print('H1-01 核心不变量断言检查')
    print('=' * 60)

    checker = InvariantAssertion()
    results = checker.check_all()

    print('\n【检查结果】')
    for key, value in results.items():
        if key == '_summary':
            continue
        status = '✅ PASS' if value.get('pass') else '❌ FAIL'
        print(f'  {key}: {status}')
        if not value.get('pass') and value.get('error'):
            print(f'    错误: {value["error"][:100]}')

    summary = results['_summary']
    print(f'\n【汇总】 通过: {summary["passed"]}/{summary["total"]}, 失败: {summary["failed"]}')
    print(f'【总体】 {"✅ 全部通过" if summary["all_pass"] else "❌ 存在违规"}')

    return 0 if summary['all_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
