# -*- coding: utf-8 -*-
"""P1-6 周复盘 · ActivityWatch 本周时间分布汇总
用法: python aw_weekly_summary.py [--days 7] [--format md|json]
依赖: ActivityWatch 已启动（http://localhost:5600）；纯标准库
输出: 按应用聚合的本周使用时长表（md 可直接粘贴进《每周笔记模板》时间分布节）
"""
import argparse, datetime, json, sys, urllib.request

AW = "http://localhost:5600/api/0"


def _get(path):
    # ActivityWatch API 路由差异：/buckets 需尾斜杠（否则 308）；/events 禁止尾斜杠（否则 400/404）
    if path == "/buckets":
        path = "/buckets/"
    with urllib.request.urlopen(AW + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="统计窗口天数（默认 7=本周）")
    ap.add_argument("--format", default="md", choices=["md", "json"])
    args = ap.parse_args()

    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=args.days)
    start_iso = start.isoformat(timespec="seconds")
    end_iso = end.isoformat(timespec="seconds")

    try:
        buckets = _get("/buckets")
    except Exception as exc:
        print("ActivityWatch 未响应（%s）。请确认 aw-qt/aw-server 已启动。" % exc, file=sys.stderr)
        return 1

    window_ids = [b for b in buckets if "aw-watcher-window" in b]
    if not window_ids:
        print("未找到 aw-watcher-window bucket，时间追踪未采集窗口数据。", file=sys.stderr)
        return 2

    app_seconds = {}
    total = 0.0
    for bid in window_ids:
        try:
            events = _get("/buckets/%s/events?start=%s&end=%s" % (bid, start_iso, end_iso))
        except Exception as exc:
            print("拉取 %s 失败: %s" % (bid, exc), file=sys.stderr)
            continue
        for ev in events:
            dur = (ev.get("timestamp") and ev.get("duration") or 0)
            app = (ev.get("data") or {}).get("app", "未知")
            app_seconds[app] = app_seconds.get(app, 0) + dur
            total += dur

    rows = sorted(app_seconds.items(), key=lambda kv: kv[1], reverse=True)
    if args.format == "json":
        print(json.dumps({"window_days": args.days, "total_seconds": total,
                          "apps": [{"app": a, "seconds": s} for a, s in rows]},
                         ensure_ascii=False, indent=2))
        return 0

    print("### ⏱ 本周时间分布（ActivityWatch · %s ~ %s）" % (start.date(), end.date()))
    print("")
    print("| 应用 | 时长(小时) | 占比 |")
    print("|------|-----------|------|")
    if total <= 0:
        print("| （无采集数据） | - | - |")
        return 0
    for app, sec in rows:
        hrs = sec / 3600.0
        print("| %s | %.1f | %.1f%% |" % (app, hrs, 100.0 * sec / total))
    print("")
    print("**总追踪时长：%.1f 小时**" % (total / 3600.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
