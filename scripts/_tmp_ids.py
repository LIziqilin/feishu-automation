# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
txt = open('_m.txt', 'rb').read().decode('utf-8-sig', errors='replace')
ids = {
 "2/3": "om_x100b6596b628c0a8b155faafbe2d52b",
 "3/3": "om_x100b6596b855fca8b15d80abbe18aa1",
 "三件事": "om_x100b6596b808d0a4b041e9505fbee5d",
 "待办": "om_x100b6596b81890a0b4b45f9508d1b81",
 "到期提醒": "om_x100b6596b83b04bcb1ba797174d3d86",
}
for k, mid in ids.items():
    i = txt.find(mid)
    if i < 0:
        print(k, mid[:30], "-> NOT in last-40 page")
        continue
    seg = txt[max(0, i - 600):i]
    m = re.findall(r'"create_time"\s*:\s*"([0-9\- :]+)"', seg)
    print(k, mid[:30], "->", m[-1] if m else "?")
