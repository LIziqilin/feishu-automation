#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为所有关键任务计划配置"错过启动后尽快启动"（StartWhenAvailable）
解决：电脑休眠/关机时定时任务不补跑的问题
"""
import subprocess
import os
import tempfile

tasks = [
    "V16_MorningReport",
    "V16_NoonReport",
    "V16_EveningReport",
    "V16_LearningPoll",
    "V16_DailyMaintenance",
    "FeishuAssistant-Heartbeat-Morning",
    "FeishuAssistant-Heartbeat-Noon",
    "FeishuAssistant-Heartbeat-Night",
]

def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")

print("=" * 60)
print("配置任务计划'错过启动后尽快启动'")
print("=" * 60)

for task_name in tasks:
    print(f"\n--- {task_name} ---")

    # 1. 导出任务XML
    xml_file = os.path.join(tempfile.gettempdir(), f"{task_name}.xml")
    code, stdout, stderr = run(["schtasks", "/query", "/tn", f"\\{task_name}", "/xml"])
    if code != 0:
        print(f"  ✗ 导出失败: {stderr[:200]}")
        continue

    xml_content = stdout
    # 去掉开头的非XML内容（schtasks输出可能有BOM或其他前缀）
    xml_start = xml_content.find("<?xml")
    if xml_start > 0:
        xml_content = xml_content[xml_start:]

    # 2. 检查是否已有StartWhenAvailable
    if "StartWhenAvailable" in xml_content:
        # 替换为true
        xml_content = xml_content.replace(
            "<StartWhenAvailable>false</StartWhenAvailable>",
            "<StartWhenAvailable>true</StartWhenAvailable>"
        )
        print("  已有配置，已更新为true")
    else:
        # 在<Settings>标签内添加StartWhenAvailable
        if "<Settings>" in xml_content:
            xml_content = xml_content.replace(
                "<Settings>",
                "<Settings>\n    <StartWhenAvailable>true</StartWhenAvailable>"
            )
            print("  已添加StartWhenAvailable=true")
        else:
            print("  ✗ 未找到<Settings>标签")
            continue

    # 3. 写入XML文件
    with open(xml_file, "w", encoding="utf-8") as f:
        f.write(xml_content)

    # 4. 重新导入任务（删除旧的，创建新的）
    code, stdout, stderr = run(["schtasks", "/delete", "/tn", f"\\{task_name}", "/f"])
    if code != 0:
        print(f"  ✗ 删除旧任务失败: {stderr[:200]}")
        continue

    code, stdout, stderr = run(["schtasks", "/create", "/tn", f"\\{task_name}", "/xml", xml_file, "/f"])
    if code != 0:
        print(f"  ✗ 导入新任务失败: {stderr[:200]}")
        continue

    print(f"  ✓ 已配置'错过启动后尽快启动'")

    # 5. 验证
    code, stdout, stderr = run(["schtasks", "/query", "/tn", f"\\{task_name}", "/xml"])
    if "StartWhenAvailable>true" in stdout:
        print(f"  ✓ 验证通过：StartWhenAvailable=true")
    else:
        print(f"  ⚠ 验证未确认")

    # 清理临时文件
    try:
        os.remove(xml_file)
    except:
        pass

print("\n" + "=" * 60)
print("所有任务配置完成")
print("=" * 60)
