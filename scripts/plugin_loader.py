# -*- coding: utf-8 -*-
"""plugin_loader.py — 插件/第三方扩展机制（V49）
=============================================
约定：scripts/plugins/ 下每个 .py 为一个插件，暴露
  NAME = "..."
  def handle(event: dict) -> str      # 处理事件，返回结果摘要
  def info() -> dict                 # 返回插件元信息（可选）
本加载器自动发现、import、列出并派发事件，主系统只需：
  from plugin_loader import dispatch
  dispatch({"type": "xxx", "payload": {...}})
"""
import importlib.util, traceback
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent / "plugins"
_plugins = {}


def discover():
    PLUGIN_DIR.mkdir(exist_ok=True)
    _plugins.clear()
    for f in sorted(PLUGIN_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "handle") and hasattr(mod, "NAME"):
                _plugins[mod.NAME] = mod
        except Exception as e:
            print(f"[plugin] 加载失败 {f.name}: {e}")
    return list_plugins()


def list_plugins():
    out = []
    for name, mod in _plugins.items():
        meta = {}
        try:
            meta = mod.info() if hasattr(mod, "info") else {}
        except Exception:
            pass
        out.append({"name": name, "file": getattr(mod, "__file__", ""), "meta": meta})
    return out


def dispatch(event: dict):
    """把事件派发给所有插件，返回每个插件处理结果。"""
    if not _plugins:
        discover()
    results = {}
    etype = event.get("type", "generic")
    for name, mod in _plugins.items():
        try:
            results[name] = {"ok": True, "result": mod.handle(event)}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)[:200]}
    return {"event_type": etype, "count": len(_plugins), "results": results}


if __name__ == "__main__":
    import json
    plug = discover()
    print(f"已发现 {len(plug)} 个插件：")
    print(json.dumps(plug, ensure_ascii=False, indent=2))
    # 自测：派发一个 hello 事件
    r = dispatch({"type": "selfcheck", "payload": {"msg": "ping"}})
    print("自测派发结果：")
    print(json.dumps(r, ensure_ascii=False, indent=2))
