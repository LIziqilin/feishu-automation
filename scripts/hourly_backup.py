#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每小时增量备份入口（RPO 提升）
================================
供计划任务 V16_HourlyBackup 调用：等价于
    python backup_with_rotation.py --tier hourly
只写 backups/hourly_*.json，保留最近 24 轮；不影响 daily 层（R3 不删历史）。
备份成功后顺带做一次异地副本复制（M2），拷到独立物理卷并校验。
"""
import sys, os, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backup_with_rotation as b

if __name__ == "__main__":
    sys.argv = ["backup_with_rotation.py", "--tier", "hourly"]
    rc = b.main()
    # 备份成功（未被 DEGRADED 短路）后再复制异地副本；失败不掩盖备份退出码
    if rc == 0:
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            subprocess.run([sys.executable, os.path.join(here, "offsite_replicate.py")],
                           cwd=here, timeout=300)
        except Exception as e:
            print("异地副本复制异常:", str(e)[:150])
    sys.exit(rc)
