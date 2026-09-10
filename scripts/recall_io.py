# -*- coding: utf-8 -*-
"""
recall_io.py — 知识召回埋点写入端（V13 D5，为阶段二"真实召回分池"采集数据）
每次 RAG/检索命中知识索引时调用 log_recall()：
  1) 知识索引表：last_recalled_at=本次时间，召回次数+1
  2) 检索日志表：只追加一条检索/命中记录
阶段一所有知识默认温存池，4周后用本表真实数据精确分层，杜绝凭假设分池。
"""
import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r'D:\AI-Tools\shared')
from feishu_sdk import FeishuClient, TABLES

CST = timezone(timedelta(hours=8))
KI, LOG = TABLES['知识索引表'], TABLES['检索日志表']


def _plain(v):
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return v[0].get('value') if 'value' in v[0] else v[0].get('text')
    return v


class RecallService:
    def __init__(self, client=None):
        self.c = client or FeishuClient()

    def log_recall(self, query, hit_record_id=None, hit_title='', source='AnythingLLM',
                   workspace='', when=None):
        when = when or datetime.now(CST)
        ms = int(when.timestamp() * 1000)
        # 检索日志只追加
        rec = self.c.create_record(LOG, {
            '检索词': str(query)[:200],
            '命中知识ID': hit_record_id or '',
            '命中标题': str(hit_title)[:100],
            '来源': source,
            '工作区': workspace,
            '时间戳': ms,
        })
        # 命中条目更新召回时间与计数（读-改-写，同表串行保证不丢更新）
        if hit_record_id:
            try:
                cur = self.c.get_record(KI, hit_record_id)
                n = _plain(cur['fields'].get('召回次数')) or 0
                try:
                    n = int(float(n))
                except Exception:
                    n = 0
                self.c.update_record(TABLES['知识索引表'], hit_record_id,
                                     {'last_recalled_at': ms, '召回次数': n + 1})
            except Exception:
                pass  # 埋点失败不阻断主检索链路
        return rec['record_id']
