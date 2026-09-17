# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import learning_system as L

# 桩1：模拟授权缺失导致发送失败
L.run_cmd = lambda cmd, timeout=60: (False, "", "need_user_authorization")
s = L.ReceiptSender()
r1 = s._send_message("测试失败路径")
print("失败路径返回:", r1, "| failed计数:", len(getattr(s, "failed", [])))

# 桩2：模拟发送成功
L.run_cmd = lambda cmd, timeout=60: (True, '{"code":0}', "")
s2 = L.ReceiptSender()
r2 = s2._send_message("测试成功路径")
print("成功路径返回:", r2, "| failed计数:", len(getattr(s2, "failed", [])))

# 验证告警落盘
import os
p = os.path.join(os.path.dirname(os.path.abspath(L.__file__)), "learning_alerts.log")
print("告警文件存在:", os.path.exists(p))
if os.path.exists(p):
    print("最后一行:", open(p, encoding="utf-8").read().strip().splitlines()[-1][:120])
