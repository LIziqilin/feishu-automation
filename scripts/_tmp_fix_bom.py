# -*- coding: utf-8 -*-
import io, sys, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".push_records.json")
# 用 utf-8-sig 读，utf-8 无 BOM 写
with open(p, "r", encoding="utf-8-sig") as f:
    data = json.load(f)
with open(p, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 校验：无 BOM 且可被 utf-8 正常解析
raw = open(p, "rb").read()
print("BOM present:", raw[:3] == b"\xef\xbb\xbf")
with open(p, "r", encoding="utf-8") as f:
    json.load(f)
print("plain utf-8 load OK")
print(raw.decode("utf-8")[:80])
