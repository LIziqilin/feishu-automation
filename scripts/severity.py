# -*- coding: utf-8 -*-
"""
severity.py — 故障分级器（V13 纯逻辑，无 IO）
V13 关键修订（相对 V11/V12）：
  1) 无法分类的异常【兜底 B 级】（V11 兜底 A 导致告警风暴），不再凌晨乱叫醒
  2) 未知异常 24h 滑窗内同指纹 >=3 次自动升 A
  3) 配额/限流拒绝【只计数不写死信】（限流不是故障），由日汇总呈现
  4) A 级才走双通道（飞书+本机弹窗/alerts.log）；B 级攒到 22:07 批量窗口；C 级进周报
"""
from collections import deque, defaultdict
from datetime import datetime, timedelta

A_LEVEL, B_LEVEL, C_LEVEL = 'A', 'B', 'C'
COUNT_ONLY = 'COUNT_ONLY'   # 限流/配额：仅计数器，不进死信

# A 级：直接影响主链路、需立即介入
A_KINDS = {
    'token_failed',           # token 连续失败
    'gateway_down',           # Hermes gateway 不可用
    'push_channel_down',      # 推送通道断
    'credential_invalid',     # 凭据失效/被轮换
    'sdk_sign_failed',        # 公共库签名失败（唯一通道级）
}
# B 级：单点、可延后批量自愈/处理
B_KINDS = {
    'record_write_failed', 'field_missing', 'parse_error',
    'readback_mismatch', 'single_record_skip', 'backup_partial',
}
# C 级：优化/清理类
C_KINDS = {'cleanup', 'optimization', 'ttl_archive'}

# 限流/配额类错误码（与 feishu_sdk.RATE_LIMIT_CODES 对齐）
RATE_CODES = {429, 1254290, 11232, 99991400}
RATE_KEYWORDS = ('too many request', 'rate limit', '频率', '限流', '配额', 'quota', 'frequency')


def fingerprint(err):
    """错误指纹：模块+种类+code，用于未知异常聚合。"""
    return '%s|%s|%s' % (err.get('module', '?'), err.get('kind', 'unknown'), err.get('code', '-'))


def is_rate_limit(err):
    if err.get('kind') == 'rate_limit':
        return True
    if err.get('code') in RATE_CODES:
        return True
    msg = str(err.get('msg', '')).lower()
    return any(k in msg for k in RATE_KEYWORDS)


def classify(err):
    """返回 (level, reason)。level 可能为 COUNT_ONLY。
    err: {'kind':..,'code':..,'msg':..,'module':..}"""
    if is_rate_limit(err):
        return COUNT_ONLY, '限流/配额拒绝，只计数不写死信'
    kind = err.get('kind', 'unknown')
    if kind in A_KINDS:
        return A_LEVEL, 'A类主链路故障:%s' % kind
    if kind in B_KINDS:
        return B_LEVEL, 'B类单点可延后:%s' % kind
    if kind in C_KINDS:
        return C_LEVEL, 'C类优化项:%s' % kind
    # 未知异常兜底 B（不再兜底 A）
    return B_LEVEL, '未知异常兜底B级，进入24h升级观察'


class EscalationWindow:
    """未知/兜底B异常 24h 滑窗聚合：同指纹 >=threshold 升 A。"""
    def __init__(self, window_hours=24, threshold=3, now_func=None):
        self.window = timedelta(hours=window_hours)
        self.threshold = threshold
        self._hits = defaultdict(deque)
        self._now = now_func or datetime.now

    KNOWN = A_KINDS | B_KINDS | C_KINDS

    def observe(self, err):
        """登记一次异常，返回当前应判级别。仅【未知/兜底B】进滑窗，达阈值升A；已知级别不升级。"""
        lvl, reason = classify(err)
        if lvl == COUNT_ONLY:
            return lvl, reason
        kind = err.get('kind', 'unknown')
        if kind in self.KNOWN:
            return lvl, reason                      # 明确归类，按原级别
        fp = fingerprint(err)
        now = self._now()
        dq = self._hits[fp]
        dq.append(now)
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= self.threshold:
            return A_LEVEL, '未知异常24h内%d次，自动升A' % len(dq)
        return B_LEVEL, reason

    def count(self, fp):
        return len(self._hits.get(fp, ()))


class RateCounter:
    """限流计数器（替代写死信）：按 日期|模块 计数，供日汇总。"""
    def __init__(self):
        self.buckets = defaultdict(int)

    def add(self, err, day=None):
        day = day or datetime.now().strftime('%Y-%m-%d')
        key = '%s|%s' % (day, err.get('module', 'unknown'))
        self.buckets[key] += 1
        return self.buckets[key]

    def daily_summary(self, day=None):
        day = day or datetime.now().strftime('%Y-%m-%d')
        return {k.split('|', 1)[1]: v for k, v in self.buckets.items() if k.startswith(day + '|')}
