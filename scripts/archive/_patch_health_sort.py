# -*- coding: utf-8 -*-
import io
p = r'D:\AI-Tools\feishu\V13方案增强\scripts\system_health_check.py'
s = io.open(p, encoding='utf-8').read()

old1 = '     "--table-id", "tblJmm0ZIgqlYmyt", "--as", "user", "--limit", "50", "--format", "json"],'
new1 = ('     "--table-id", "tblJmm0ZIgqlYmyt", "--as", "user", "--limit", "50",\n'
        '     "--sort-json", json.dumps([{"field": "\u5fc3\u8df3\u65f6\u95f4", "desc": True}], ensure_ascii=False),\n'
        '     "--format", "json"],')

old2 = '     "--table-id", "tblxJMndPNtZ7XyG", "--as", "user", "--limit", "100", "--format", "json"],'
new2 = ('     "--table-id", "tblxJMndPNtZ7XyG", "--as", "user", "--limit", "100",\n'
        '     "--sort-json", json.dumps([{"field": "\u6700\u8fd1\u68c0\u67e5\u65f6\u95f4", "desc": True}], ensure_ascii=False),\n'
        '     "--format", "json"],')

n1 = s.count(old1)
n2 = s.count(old2)
s = s.replace(old1, new1).replace(old2, new2)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('heartbeat replacements:', n1, ' health replacements:', n2)
