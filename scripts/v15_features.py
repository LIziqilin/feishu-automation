#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V15 体验层功能共享基础模块
================================
统一封装：飞书多维表格读写、硅基流动LLM调用、飞书群消息、Obsidian产出路径。
供：错题本 / 费曼验证 / 知识演进 / 番茄钟 / 时间块 / 个性化推荐 等脚本复用。

设计原则：
- 不依赖第三方库（仅标准库 urllib/json/subprocess），16G老机器零额外安装
- 所有飞书读写带分页、重试、字段值容错
- LLM 走硅基流动云端（DeepSeek/Qwen），不占本地资源，失败优雅降级
"""
import os, sys, json, time, subprocess, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# ============ 常量 ============
ENV_PATH = r'C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env'
LARK_CLI = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"

BASE_TOKEN = "X8N1bvN3na99dFsyu0gcU8zTnHf"
CHAT_ID    = "oc_1fe154e172ab04622b7ffa810ac172bc"
T_CARD     = "tblpLvxyYpDJgF92"   # 学习卡表
T_FLOW     = "tblbznzCSpPhSz93"   # 复习流水表
T_PROFILE  = "tbldjGffbuPKCe21"   # 用户画像表
T_INSIGHT  = "tblaqKBl87V9C0q1"   # 洞察笔记表
T_TASK     = "tblz3H4lV7PCrBrX"   # 任务总表
T_EVENTLOG = "tblPreh1ipB9LQpf"   # 系统事件日志表

VAULT = Path(r"D:\AI\finished Brain")
SCRIPTS_DIR = Path(__file__).parent

# ============ 密钥外部化（P0-4：禁止硬编码生产凭证）============
# 优先顺序：环境变量 > scripts/llm_secrets.env（已 gitignore）> hermes env 文件
# 轮换：在硅基流动控制台吊销旧 Key，新 Key 只写入 llm_secrets.env，勿回填源码。
def _load_llm_key():
    for name in ("LLM_KEY", "SILICONFLOW_API_KEY", "SF_API_KEY"):
        v = os.environ.get(name)
        if v and v.strip():
            return v.strip()
    for p in (SCRIPTS_DIR / "llm_secrets.env", Path(ENV_PATH)):
        try:
            with open(p, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("LLM_KEY=") or line.startswith("SILICONFLOW_API_KEY="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return ""

# 硅基流动（云端，主用 Qwen2.5-7B，复杂任务可升 DeepSeek）
LLM_KEY = _load_llm_key()
LLM_URL = "https://api.siliconflow.cn/v1/chat/completions"
LLM_MODEL_FAST = "Qwen/Qwen2.5-7B-Instruct"
LLM_MODEL_BEST = "deepseek-ai/DeepSeek-V3.2"  # 原 DeepSeek-V2.5 已被平台下线(Model disabled 30003)，改用在售 V3.2
# 本地 Ollama 离线兜底（qwen2.5:1.5b 已落地，断网可用）
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:1.5b"

_token_cache = {"token": None, "exp": 0}

# ============ 飞书 Token ============
def get_token():
    if _token_cache["token"] and time.time() < _token_cache["exp"]:
        return _token_cache["token"]
    app_id = app_secret = ""
    with open(ENV_PATH, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith("FEISHU_APP_ID="): app_id = line.split("=",1)[1]
            elif line.startswith("FEISHU_APP_SECRET="): app_secret = line.split("=",1)[1]
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    _token_cache["token"] = d["tenant_access_token"]
    _token_cache["exp"] = time.time() + 6000
    return _token_cache["token"]

def _headers():
    return {"Authorization": "Bearer " + get_token(), "Content-Type": "application/json"}

# ============ 字段值容错提取 ============
def cell_text(v):
    """飞书文本字段 -> Python字符串（兼容 list[{text}] / str / None）"""
    if v is None: return ""
    if isinstance(v, str): return v
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, dict): out.append(x.get("text", x.get("name", "")))
            else: out.append(str(x))
        return "".join(out)
    if isinstance(v, dict): return v.get("text", v.get("name", str(v)))
    return str(v)

def cell_select(v):
    """单选字段 -> 字符串"""
    if isinstance(v, list):
        return cell_text(v)
    return cell_text(v)

def cell_num(v, default=0):
    try:
        if v is None or v == "": return default
        return float(v)
    except: return default

def ts_to_date(v):
    """飞书毫秒时间戳 -> 'YYYY-MM-DD'（容错）"""
    if not v: return ""
    try:
        return datetime.fromtimestamp(int(v)/1000).strftime("%Y-%m-%d")
    except: return ""

def date_ms(s=None):
    """'YYYY-MM-DD' 或 now -> 毫秒时间戳"""
    if s is None:
        return int(datetime.now().timestamp()*1000)
    dt = datetime.strptime(s, "%Y-%m-%d")
    return int(dt.timestamp()*1000)

# ============ 记录读写（全量分页） ============
def list_records(table_id, page_size=100, max_pages=50):
    """全量读取一张表，返回 items 列表"""
    items, pt = [], None
    for _ in range(max_pages):
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/records?page_size={page_size}"
        if pt: url += "&page_token=" + urllib.parse.quote(pt, safe="")
        req = urllib.request.Request(url, headers={"Authorization":"Bearer "+get_token()})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            # 偶发400/限流：退避重试一次
            body = e.read().decode()[:200]
            if e.code in (400, 429, 500, 502, 503):
                time.sleep(1.2); continue
            raise
        data = d.get("data", {})
        items.extend(data.get("items", []))
        pt = data.get("page_token")
        if not data.get("has_more") or not pt: break
    return items

class BitableError(RuntimeError):
    """飞书多维表业务层错误（HTTP 200 但 code != 0）"""
    def __init__(self, code, msg, payload=None):
        super().__init__(f"bitable code={code} msg={msg}")
        self.code = code; self.msg = msg; self.payload = payload


def _biz_check(resp, ctx=""):
    """业务码校验：HTTP 200 但 code!=0 必须抛错，禁止把失败当成功"""
    if not isinstance(resp, dict):
        raise BitableError(-1, f"非预期响应类型: {type(resp).__name__}", resp)
    code = resp.get("code")
    if code not in (0, None):
        raise BitableError(code, resp.get("msg", ""), resp)
    return resp


MAX_TASK_NAME_LEN = 100


def validate_task_name(name):
    """R1 输入校验：禁止空名称/纯空白/超长/控制字符。返回 (ok, cleaned_or_reason)"""
    if name is None:
        return False, "任务名称为空"
    n = str(name).strip()
    if not n:
        return False, "任务名称不能为空或纯空白"
    if len(n) > MAX_TASK_NAME_LEN:
        return False, f"任务名称过长({len(n)}>{MAX_TASK_NAME_LEN})"
    if any(ord(ch) < 32 for ch in n):
        return False, "任务名称含控制字符"
    return True, n

def create_record(table_id, fields):
    # R1 输入校验（关闭 GT-01 负路径「空名称被接受」缺陷）
    if isinstance(fields, dict) and "任务名称" in fields:
        _ok, _v = validate_task_name(fields.get("任务名称"))
        if not _ok:
            raise ValueError(f"[输入校验] {_v}")
        fields = dict(fields); fields["任务名称"] = _v
    body = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/records",
        data=body, headers=_headers(), method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return _biz_check(json.load(r), "create_record")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(1.5*(attempt+1)); continue
            raise

def update_record(table_id, record_id, fields):
    body = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{table_id}/records/{record_id}",
        data=body, headers=_headers(), method="PUT")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return _biz_check(json.load(r), "update_record")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(1.5*(attempt+1)); continue
            raise

# ============ LLM（硅基流动，带降级） ============
def _ollama_chat(prompt, system=None, timeout=60, max_tokens=900, temperature=0.3):
    """本地 Ollama 离线兜底（顺位③）：断网时仍可推理"""
    msgs = []
    if system: msgs.append({"role":"system","content":system})
    msgs.append({"role":"user","content":prompt})
    body = json.dumps({"model":OLLAMA_MODEL,"messages":msgs,
                       "max_tokens":max_tokens,"temperature":temperature,
                       "stream":False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return d["message"]["content"].strip()

def llm_chat(prompt, system=None, model=None, timeout=60, max_tokens=900, temperature=0.3):
    """四顺位降级 LLM 调用，返回文本；全失败返回 None（调用方用飞书表格知识索引兜底）。
    顺位：①硅基流动 Qwen2.5-7B → ②硅基流动 DeepSeek-V2.5 → ③本地 Ollama qwen2.5:1.5b → ④None"""
    msgs = []
    if system: msgs.append({"role":"system","content":system})
    msgs.append({"role":"user","content":prompt})
    # 顺位①+②：云端硅基流动（双模型去重）
    for m in dict.fromkeys([model or LLM_MODEL_FAST, LLM_MODEL_BEST]):
        if not m: continue
        try:
            body = json.dumps({"model":m,"messages":msgs,
                               "max_tokens":max_tokens,"temperature":temperature}).encode()
            req = urllib.request.Request(LLM_URL, data=body,
                headers={"Authorization":"Bearer "+LLM_KEY,"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            return d["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"  [LLM][云端 {m}] 失败: {e}")
            continue
    # 顺位③：本地 Ollama 离线兜底
    try:
        return _ollama_chat(prompt, system, timeout, max_tokens, temperature)
    except Exception as e:
        print(f"  [LLM][本地 Ollama {OLLAMA_MODEL}] 失败: {e}")
    # 顺位④：全失败
    return None

# ============ 飞书群消息 ============
def _send_once(text, identity):
    cmd = [LARK_CLI, "im", "+messages-send", "--chat-id", CHAT_ID,
           "--msg-type", "text", "--text", text, "--format", "json", "--as", identity]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=40)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

def _mirror_wecom(text):
    """互为备用：飞书群消息镜像一份到企业微信群。失败静默、不影响主流程。"""
    try:
        import os as _o
        _sd = _o.path.dirname(_o.path.abspath(__file__))
        if _sd not in sys.path:
            sys.path.insert(0, _sd)
        import wecom_push
        wecom_push.send_text(str(text)[:1800])
    except Exception:
        pass


def send_chat(text, as_user=True):
    """通过 lark-cli 发群消息。优先 user 身份，失败自动回退 bot 身份（P0 修复：
    原实现 user 身份缺失时直接返回 False，导致所有群消息静默失败）。"""
    if as_user:
        try:
            ok, out = _send_once(text, "user")
            if ok:
                _mirror_wecom(text)
                return True
            print("  [send_chat] user 身份失败，尝试 bot 回退")
        except Exception as e:
            print(f"  [send_chat] user 抛出: {e}")
    try:
        ok, out = _send_once(text, "bot")
        if not ok:
            print(f"  [send_chat] bot 亦失败: {out[-200:]}")
        _mirror_wecom(text)
        return ok
    except Exception as e:
        print(f"  [send_chat] 发送失败: {e}")
        _mirror_wecom(text)
        return False

# ============ Obsidian 笔记写入 ============
def write_note(rel_path, content):
    """写入 vault 内笔记（相对路径），自动建目录"""
    p = VAULT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

if __name__ == "__main__":
    # 自检
    tok = get_token()
    print("✅ Token获取:", tok[:12]+"...")
    cards = list_records(T_CARD)
    print(f"✅ 学习卡表读取: {len(cards)}张")
    r = llm_chat("回复'OK'两个字", max_tokens=10)
    print("✅ LLM自检:", r)
