# -*- coding: utf-8 -*-
"""webapi.py — 对外 OpenAPI + Webhook 事件接收（V49，标准库零依赖）
==============================================================
端点：
  GET  /health          健康检查（系统/桥接/LLM 摘要）
  GET  /tasks           当前活跃任务数（只读）
  POST /ask             自然语言问答（走 llm_router，Coze→DeepSeek）
  POST /webhook         外部事件触发：收事件→转发飞书总控群+企微（双通道）

安全：
  - X-API-KEY 头校验（取 env WEBAPI_TOKEN，未设则拒绝写端点）
  - 只读端点 /health /tasks 不需要 token
启动：python webapi.py [--port 8765]
"""
import json, os, sys, time, argparse, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

API_TOKEN = os.environ.get("WEBAPI_TOKEN", "")


def _send_group(text):
    """双通道：飞书+企微。失败不抛。"""
    out = {}
    try:
        from v15_features import send_chat
        out["feishu"] = bool(send_chat(text))
    except Exception as e:
        out["feishu"] = f"err:{e}"
    try:
        from wecom_push import send_markdown
        ok, msg = send_markdown(text[:800], title="事件通知")
        out["wecom"] = "ok" if ok else f"err:{msg}"
    except Exception as e:
        out["wecom"] = f"err:{e}"
    return out


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        return self.headers.get("X-API-KEY", "") == API_TOKEN if API_TOKEN else False

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                              "service": "feishu-automation webapi"})
        elif self.path == "/tasks":
            try:
                import config_local as cfg
                self._json(200, {"base": cfg.BASE_TOKEN, "chat_id": cfg.TARGET_CHAT_ID,
                                  "note": "只读接口；任务明细请用 /ask 或多维表格"})
            except Exception as e:
                self._json(200, {"base": "unavailable", "err": str(e)[:120]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        # /card-callback 飞书卡片回调无需X-API-KEY（飞书不会带这个头）
        if self.path != "/card-callback" and not self._auth_ok():
            self._json(401, {"error": "unauthorized", "hint": "请带 X-API-KEY 头"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "bad json"}); return

        if self.path == "/ask":
            q = (data.get("q") or data.get("question") or "").strip()
            if not q:
                self._json(400, {"error": "缺 q/question"}); return
            try:
                import subprocess
                r = subprocess.run([sys.executable, "-X", "utf-8", "llm_router.py", q],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=90)
                ans = (r.stdout or "").strip()
                self._json(200, {"q": q, "answer": ans[-1500:]})
            except Exception as e:
                self._json(500, {"error": str(e)[:200]})

        elif self.path == "/card-callback":
            # 飞书交互式卡片回调（无需X-API-KEY，飞书签名验证在后续完善）
            try:
                callback = json.loads(raw.decode("utf-8"))
            except Exception:
                self._json(400, {"error": "bad json"}); return

            # 1. URL验证（飞书配置回调URL时首次验证）
            if callback.get("type") == "url_verification":
                challenge = callback.get("challenge", "")
                print(f"[card-callback] URL验证: challenge={challenge[:20]}...")
                self._json(200, {"challenge": challenge})
                return

            # 2. 按钮事件处理
            action = callback.get("action", {})
            value = action.get("value", {})
            tag = action.get("tag", "")
            open_id = callback.get("open_id", "")
            open_message_id = callback.get("open_message_id", "")

            print(f"[card-callback] 按钮点击: tag={tag}, value={value}, open_id={open_id[:20]}...")

            # 根据按钮value执行动作
            action_type = value.get("action", "")
            task_name = value.get("task_name", "")
            record_id = value.get("record_id", "")

            if action_type == "complete_task":
                # 完成任务：调用learning_system的完成逻辑
                try:
                    import subprocess
                    # 直接在多维表格中更新任务状态
                    cmd = ["lark-cli", "base", "+record-upsert",
                           "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
                           "--table-id", "tblz3H4lV7PCrBrX",
                           "--as", "user",
                           "--json", json.dumps({"records": [{"record_id": record_id, "fields": {"状态": "已完成"}}]}, ensure_ascii=False)]
                    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
                    if r.returncode == 0:
                        reply = f"✅ 任务已完成：{task_name}"
                        # 发送更新到群
                        _send_group(reply)
                        self._json(200, {"toast": {"type": "success", "content": "任务已完成"}, "card": {"type": "raw", "content": {"header": {"title": {"tag": "plain_text", "content": "✅ 已完成"}}, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**{task_name}**\n已标记为完成"}}]}}})
                    else:
                        self._json(200, {"toast": {"type": "error", "content": f"完成失败: {r.stderr[:100]}"}})
                except Exception as e:
                    self._json(200, {"toast": {"type": "error", "content": f"异常: {str(e)[:100]}"}})
            elif action_type == "archive_task":
                try:
                    import subprocess
                    cmd = ["lark-cli", "base", "+record-upsert",
                           "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
                           "--table-id", "tblz3H4lV7PCrBrX",
                           "--as", "user",
                           "--json", json.dumps({"records": [{"record_id": record_id, "fields": {"状态": "已归档"}}]}, ensure_ascii=False)]
                    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
                    if r.returncode == 0:
                        _send_group(f"📦 任务已归档：{task_name}")
                        self._json(200, {"toast": {"type": "success", "content": "任务已归档"}})
                    else:
                        self._json(200, {"toast": {"type": "error", "content": "归档失败"}})
                except Exception as e:
                    self._json(200, {"toast": {"type": "error", "content": f"异常: {str(e)[:100]}"}})
            else:
                self._json(200, {"toast": {"type": "info", "content": f"收到: {action_type}"}})

        elif self.path == "/webhook":
            title = data.get("title") or "外部事件"
            text = data.get("text") or data.get("message") or ""
            out = _send_group(f"🔔 {title}\n{text}\n[webapi webhook 接收]")
            self._json(200, {"delivered": out, "title": title})
        else:
            self._json(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("WEBAPI_PORT", 8765)))
    a = ap.parse_args()
    bind = os.environ.get("BIND_HOST", "127.0.0.1")  # 云服务器部署时设 0.0.0.0
    if not API_TOKEN:
        print("[警告] 未设 WEBAPI_TOKEN 环境变量，/ask 与 /webhook 将返回401")
    srv = ThreadingHTTPServer((bind, a.port), Handler)
    print(f"webapi 监听 http://{bind}:{a.port}  (health/tasks/ask/webhook)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
