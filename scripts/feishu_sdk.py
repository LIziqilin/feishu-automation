# -*- coding: utf-8 -*-
"""
feishu_sdk.py — 个人运维系统唯一飞书公共库（V13 波次0 公共库一期+二期合并落地）
设计原则（V13 融合定稿）：
  1) 显式优于隐式：所有写操作走本库，禁止各脚本手写 token/sign/urllib
  2) sign 强制 quote_plus（终结 V11/V12 签名静默失败 bug），走 JSON body 亦统一编码
  3) 同一数据表写串行（飞书单表不支持并发写，防 1254290 TooManyRequest）
  4) 写后延迟读回 + 指数退避；3 次仍不一致【仅告警不阻断】（防最终一致性误报雪崩）
  5) 429 / 1254290 / 11232 指数退避（30/120/480s ±20% 抖动），可注入 sleeper 便于测试
  6) 配额/限频类拒绝识别为 RateLimit，不写死信（限流不是故障）
  7) 绝不打印/回显 token、app_secret、webhook secret
零三方依赖，仅标准库；Python 3.8+。
"""
import os, json, time, hmac, hashlib, base64, random, threading, urllib.request, urllib.error
from urllib.parse import quote_plus

OPEN = 'https://open.feishu.cn/open-apis'
DEFAULT_BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'

# 现网 11 张表权威映射（2026-09-09 探查确认）
TABLES = {
    '任务总表': 'tblz3H4lV7PCrBrX',
    '学习卡片表': 'tblpLvxyYpDJgF92',
    '知识索引表': 'tbl0NiUFeQzH2r3n',
    '决策日志表': 'tblEA13tWW56lu3K',
    '洞察笔记表': 'tblaqKBl87V9C0q1',
    '模板与SOP表': 'tblRGEeU9M3pPnjT',
    '系统健康表': 'tblxJMndPNtZ7XyG',
    '自动化队列表': 'tblOMd9Pfiju2tz0',
    '系统心跳': 'tblJmm0ZIgqlYmyt',
    '错误日志_本地': 'tblsa8CcqwAW0E4z',
    '错误日志_云端': 'tblGJlLTCpg6fWYW',
    '复习流水表': 'tblbznzCSpPhSz93',   # V13 事件溯源（只追加）
    '检索日志表': 'tblCwZyAhZbmJra2',   # V13 召回埋点
}

# 飞书 bitable 字段类型常量
FT_TEXT, FT_NUMBER, FT_SINGLE, FT_MULTI, FT_DATETIME, FT_CHECKBOX = 1, 2, 3, 4, 5, 7
FT_FORMULA, FT_BUTTON, FT_CREATEDTIME = 20, 3001, 1001

# 需要退避的限流码
RATE_LIMIT_CODES = {429, 1254290, 11232, 99991400}
# 写后读回退避（毫秒）
READBACK_DELAYS = (0.3, 0.5, 1.0, 2.0)
# 限流退避（秒）
RATE_BACKOFF = (30, 120, 480)

_CREDS_CANDIDATES = [
    r'D:\AI-Tools\feishu\飞书的高阶用法\优化实施\scripts\feishu_creds.json',
]

# webhook 配置候选（本地兜底；云端用环境变量 FEISHU_WEBHOOK / FEISHU_WEBHOOK_SECRET）
_BOT_CONFIG_CANDIDATES = [
    r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json',
]


def get_bot_config():
    """统一 webhook 配置：环境变量优先（云端），本地文件兜底（Windows）。
    环境变量不完整时合并本地文件配置。返回 dict；无配置返回空 dict。"""
    cfg = {}
    # 本地兜底先读（作为基础）
    for p in _BOT_CONFIG_CANDIDATES:
        try:
            with open(p, encoding='utf-8') as f:
                d = json.load(f)
            if d.get('webhook') or d.get('url'):
                cfg = dict(d)
                break
        except Exception:
            continue
    # 环境变量覆盖（云端 GitHub Secrets）
    env_webhook = os.environ.get('FEISHU_WEBHOOK', '')
    env_secret = os.environ.get('FEISHU_WEBHOOK_SECRET', '')
    if env_webhook:
        cfg['webhook'] = env_webhook
    if env_secret:
        cfg['secret'] = env_secret
    if env_webhook and not cfg.get('secret'):
        cfg['secret'] = ''
    return cfg


class FeishuError(RuntimeError):
    def __init__(self, code, msg, raw=None):
        super().__init__('feishu code=%s msg=%s' % (code, msg))
        self.code = code
        self.msg = msg
        self.raw = raw or {}


class RateLimitError(FeishuError):
    """配额/限频：只计数、不写死信（V13：限流不是故障）"""
    pass


def gen_sign(secret, timestamp=None):
    """自定义机器人签名：sign = Base64(HmacSHA256(key=ts+"\\n"+secret, b''))，再 quote_plus。
    强制 URL 编码——Base64 含 + / =，不编码在 query/表单传输时会签名失败（V11 静默失败根因）。"""
    ts = timestamp if timestamp is not None else str(int(time.time()))
    string_to_sign = ts + '\n' + secret
    digest = hmac.new(string_to_sign.encode('utf-8'), b'', hashlib.sha256).digest()
    sign = base64.b64encode(digest).decode('utf-8')
    return ts, quote_plus(sign)


def backoff_series(base=RATE_BACKOFF, jitter=0.2, rng=None):
    """生成 ±jitter 的退避秒序列（纯函数，便于测试）。"""
    r = rng or random.Random(0)
    out = []
    for b in base:
        out.append(round(b * (1 + r.uniform(-jitter, jitter)), 2))
    return out


class FeishuClient:
    def __init__(self, app_id=None, app_secret=None, base_token=None,
                 creds_path=None, sleeper=None, rng=None):
        # base_token：环境变量优先（云端），默认本地 app_token
        if base_token is None:
            base_token = os.environ.get('FEISHU_APP_TOKEN', DEFAULT_BASE)
        if not app_id or not app_secret:
            cid, csec = self._load_creds(creds_path)
            app_id = app_id or cid
            app_secret = app_secret or csec
        self.app_id = app_id
        self._app_secret = app_secret
        self.base_token = base_token
        self._token = None
        self._token_exp = 0.0
        self._token_lock = threading.Lock()
        self._table_locks = {}
        self._locks_guard = threading.Lock()
        self._sleeper = sleeper or time.sleep
        self._rng = rng or random.Random()

    @staticmethod
    def _load_creds(creds_path):
        # 云端优先：环境变量（GitHub Secrets 注入）
        env_id = os.environ.get('FEISHU_APP_ID', '')
        env_sec = os.environ.get('FEISHU_APP_SECRET', '')
        if env_id and env_sec:
            return env_id, env_sec
        # 本地兜底：凭据文件
        paths = [creds_path] if creds_path else []
        paths += _CREDS_CANDIDATES
        for p in paths:
            try:
                with open(p, encoding='utf-8') as f:
                    d = json.load(f)
                if d.get('APP_ID') and d.get('APP_SECRET'):
                    return d['APP_ID'], d['APP_SECRET']
            except Exception:
                continue
        return '', ''

    def _table_lock(self, table_id):
        with self._locks_guard:
            lk = self._table_locks.get(table_id)
            if lk is None:
                lk = threading.Lock()
                self._table_locks[table_id] = lk
            return lk

    # ---------- token ----------
    def get_token(self, force=False):
        """tenant_access_token，缓存至过期前 5 分钟；线程安全。"""
        with self._token_lock:
            if not force and self._token and time.time() < self._token_exp - 300:
                return self._token
            body = json.dumps({'app_id': self.app_id, 'app_secret': self._app_secret}).encode()
            d = self._raw_request(OPEN + '/auth/v3/tenant_access_token/internal', body, auth=False)
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            self._token = d['tenant_access_token']
            self._token_exp = time.time() + int(d.get('expire', 7200))
            return self._token

    # ---------- 底层 HTTP（含限流退避） ----------
    def _raw_request(self, url, body=None, auth=True, method=None, binary_ret=False):
        data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        attempt = 0
        while True:
            if auth:
                headers['Authorization'] = 'Bearer ' + self.get_token()
            req = urllib.request.Request(url, data=data, headers=headers,
                                         method=method or ('POST' if data is not None else 'GET'))
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                    if binary_ret:
                        return raw
                    d = json.loads(raw)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < len(RATE_BACKOFF):
                    self._sleep_backoff(attempt)
                    attempt += 1
                    continue
                raise
            code = d.get('code', 0)
            if code in RATE_LIMIT_CODES and attempt < len(RATE_BACKOFF):
                self._sleep_backoff(attempt)
                attempt += 1
                continue
            if code in RATE_LIMIT_CODES:
                raise RateLimitError(code, d.get('msg'), d)
            return d

    def _sleep_backoff(self, attempt):
        wait = RATE_BACKOFF[min(attempt, len(RATE_BACKOFF) - 1)]
        wait = wait * (1 + self._rng.uniform(-0.2, 0.2))
        self._sleeper(wait)

    # ---------- bitable 读 ----------
    def read_records(self, table_id, page_size=500, field_names=None, filter_str=None, max_pages=50):
        """分页读取（单页≤500，符合飞书上限）；field_names 投影减少 payload。
        max_pages 为翻页安全网，防止 page_size 过小或异常 has_more 导致海量请求。"""
        if page_size > 500:
            page_size = 500
        out, page_token, pages = [], None, 0
        while True:
            pages += 1
            if pages > max_pages:
                raise FeishuError('PAGING_LIMIT',
                                  '翻页超过%d（page_size=%d，已取%d条），请增大page_size或检查filter'
                                  % (max_pages, page_size, len(out)))
            url = '%s/bitable/v1/apps/%s/tables/%s/records?page_size=%d' % (
                OPEN, self.base_token, table_id, page_size)
            if field_names:
                url += '&field_names=' + quote_plus(json.dumps(field_names, ensure_ascii=False))
            if filter_str:
                url += '&filter=' + quote_plus(filter_str)
            if page_token:
                url += '&page_token=' + page_token
            d = self._raw_request(url)
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            data = d['data']
            out.extend(data.get('items') or [])
            if not data.get('has_more'):
                break
            page_token = data.get('page_token')
            if not page_token:
                break
        return out

    def get_record(self, table_id, record_id):
        d = self._raw_request('%s/bitable/v1/apps/%s/tables/%s/records/%s'
                              % (OPEN, self.base_token, table_id, record_id))
        if d.get('code') != 0:
            raise FeishuError(d.get('code'), d.get('msg'), d)
        return d['data']['record']

    # ---------- bitable 写（同表串行） ----------
    def create_record(self, table_id, fields, readback=False):
        return self._write_with_lock(table_id, 'POST', None, fields, readback)

    def update_record(self, table_id, record_id, fields, readback=False):
        return self._write_with_lock(table_id, 'PUT', record_id, fields, readback)

    def delete_record(self, table_id, record_id):
        """删除记录。【业务禁用】仅测试清理 / 管理员纠错；复习流水表业务路径只追加不删除。"""
        with self._table_lock(table_id):
            url = '%s/bitable/v1/apps/%s/tables/%s/records/%s' % (
                OPEN, self.base_token, table_id, record_id)
            d = self._raw_request(url, method='DELETE')
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            return d

    def batch_create(self, table_id, records, readback=False):
        """批量新增，单次≤500（飞书上限）。records: [{fields:{...}}, ...]"""
        if len(records) > 500:
            raise ValueError('batch_create 单次≤500，收到 %d' % len(records))
        with self._table_lock(table_id):
            url = '%s/bitable/v1/apps/%s/tables/%s/records/batch_create' % (
                OPEN, self.base_token, table_id)
            d = self._raw_request(url, {'records': records})
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            return d['data'].get('records', [])

    def batch_update(self, table_id, records, readback=False):
        """批量更新，单次≤500。records: [{'record_id':..,'fields':{..}}, ...]
        相比逐条 update 把 N 次写往返压成 1 次（V13 全链路 <10s 的关键）。"""
        if len(records) > 500:
            raise ValueError('batch_update 单次≤500，收到 %d' % len(records))
        with self._table_lock(table_id):
            url = '%s/bitable/v1/apps/%s/tables/%s/records/batch_update' % (
                OPEN, self.base_token, table_id)
            d = self._raw_request(url, {'records': records})
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            return d['data'].get('records', [])

    def _write_with_lock(self, table_id, method, record_id, fields, readback):
        with self._table_lock(table_id):
            if method == 'POST':
                url = '%s/bitable/v1/apps/%s/tables/%s/records' % (OPEN, self.base_token, table_id)
                body = {'fields': fields}
            else:
                url = '%s/bitable/v1/apps/%s/tables/%s/records/%s' % (
                    OPEN, self.base_token, table_id, record_id)
                body = {'fields': fields}
            d = self._raw_request(url, body, method=method)
            if d.get('code') != 0:
                raise FeishuError(d.get('code'), d.get('msg'), d)
            rec = d['data']['record']
            if readback:
                self._verify_readback(table_id, rec['record_id'], fields)
            return rec

    def _verify_readback(self, table_id, record_id, expect_fields):
        """延迟读回校验；最终一致性下按 0.3/0.5/1/2s 退避，3 次后仍不一致仅返回告警，不抛错（不阻断主流程）。"""
        for delay in READBACK_DELAYS:
            self._sleeper(delay)
            try:
                got = self.get_record(table_id, record_id).get('fields', {})
            except Exception:
                continue
            if self._fields_match(got, expect_fields):
                return {'ok': True, 'attempts': None}
        return {'ok': False, 'record_id': record_id,
                'warn': '写后读回 4 次未完全一致，仅告警不阻断（最终一致性）'}

    @staticmethod
    def _fields_match(got, expect):
        for k, v in expect.items():
            if k not in got:
                return False
            g = got[k]
            if isinstance(g, list) and g and isinstance(g[0], dict):
                g = g[0].get('value') if 'value' in g[0] else g[0].get('text')
            if isinstance(v, (int, float)) and isinstance(g, (int, float)):
                if float(v) != float(g):
                    return False
            elif str(g) != str(v):
                return False
        return True

    # ---------- 表 / 字段管理 ----------
    def list_tables(self):
        d = self._raw_request('%s/bitable/v1/apps/%s/tables?page_size=100' % (OPEN, self.base_token))
        return [(x['table_id'], x['name']) for x in d['data']['items']]

    def create_table(self, name, default_view_name='默认视图', fields=None):
        body = {'table': {'name': name, 'default_view_name': default_view_name}}
        if fields:
            body['table']['fields'] = fields
        d = self._raw_request('%s/bitable/v1/apps/%s/tables' % (OPEN, self.base_token), body)
        if d.get('code') != 0:
            raise FeishuError(d.get('code'), d.get('msg'), d)
        return d['data']['table_id']

    def list_fields(self, table_id):
        d = self._raw_request('%s/bitable/v1/apps/%s/tables/%s/fields?page_size=100'
                              % (OPEN, self.base_token, table_id))
        return d['data']['items']

    def create_field(self, table_id, field_name, field_type, property_=None, ui_type=None):
        body = {'field_name': field_name, 'type': field_type}
        if property_:
            body['property'] = property_
        if ui_type:
            body['ui_type'] = ui_type
        d = self._raw_request('%s/bitable/v1/apps/%s/tables/%s/fields'
                              % (OPEN, self.base_token, table_id), body)
        if d.get('code') != 0:
            raise FeishuError(d.get('code'), d.get('msg'), d)
        return d['data']['field']

    # ---------- 群机器人消息 ----------
    def send_text(self, webhook, secret, text):
        """自定义机器人发文本；sign 强制 quote_plus；返回含 message_id 用于送达对账。"""
        ts, sign = gen_sign(secret)
        body = {'timestamp': ts, 'sign': sign, 'msg_type': 'text', 'content': {'text': text}}
        d = self._raw_request(webhook, body, auth=False)
        if d.get('code', 0) != 0 and d.get('StatusCode', 0) != 0:
            raise FeishuError(d.get('code', d.get('StatusCode')), d.get('msg'), d)
        return d

    def send_message(self, webhook, secret, text, retries=2):
        """发送带重试；幂等：同一 (text,分钟) 重试由调用方保证不重复，这里只做网络重试。"""
        last = None
        for i in range(retries + 1):
            try:
                return self.send_text(webhook, secret, text)
            except RateLimitError:
                raise
            except Exception as e:
                last = e
                self._sleeper(1.5 * (i + 1))
        raise last


# ---------- 模块级便捷单例（脚本直接 import 使用） ----------
_default = None
_singleton_lock = threading.Lock()

def get_client(**kw):
    global _default
    with _singleton_lock:
        if _default is None or kw:
            return FeishuClient(**kw) if kw else (_default := FeishuClient())
        return _default
