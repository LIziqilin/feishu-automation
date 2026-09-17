# -*- coding: utf-8 -*-
import io, sys, os, json, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from v19_integration import DailyPusher

print("FILE =", DailyPusher.PUSH_RECORD_FILE)
print("EXISTS =", os.path.exists(DailyPusher.PUSH_RECORD_FILE))

# 复刻 _mark_pushed 内部逻辑，暴露真实异常
try:
    data = {}
    if os.path.exists(DailyPusher.PUSH_RECORD_FILE):
        with open(DailyPusher.PUSH_RECORD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    print("LOADED keys =", list(data.keys()))
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in data:
        data[today] = {}
    data[today]["morning"] = datetime.now().isoformat()
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    data = {k: v for k, v in data.items() if k >= cutoff}
    with open(DailyPusher.PUSH_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("WRITE OK")
except Exception:
    traceback.print_exc()

# 直接调用类方法
DailyPusher._mark_pushed("morning")
print("after _mark_pushed:", DailyPusher._already_pushed("morning"))
print(open(DailyPusher.PUSH_RECORD_FILE, encoding="utf-8").read())
