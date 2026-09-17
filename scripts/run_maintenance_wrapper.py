#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日常维护任务包装脚本V2：
- 7轮滚动备份
- 重建消费索引（learning_system.py --reindex）
- DLQ死信重试（dlq_consumer.py）
- 测试数据清理（cleanup_test_data.py）
- 消费索引健康检查（V21修正版静态方法）
- 系统状态更新
修复：移除不存在的review_derive.py/phase5_daily_check.py依赖，修复ConsumeIndexHealthChecker调用
"""

import os
import sys
import subprocess
import json
from datetime import datetime

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_maintenance_debug.log")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {msg}\n")
    print(f"[{timestamp}] {msg}")

# 清空日志
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

log("=== 维护任务开始（V2修复版） ===")

# 设置PATH包含hermes lark-cli路径
hermes_path = r"C:\Users\Administrator\AppData\Local\hermes\node"
os.environ["PATH"] = hermes_path + ";" + os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置工作目录
work_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(work_dir)
log(f"工作目录: {os.getcwd()}")

exit_code = 0

def run_script(script_name, timeout=300, description=""):
    """运行子脚本，返回是否成功。script_name 可含空格分隔的参数，否则为纯文件名。"""
    parts = script_name.split()
    script_file = parts[0]
    script_args = parts[1:]
    script_path = os.path.join(work_dir, script_file)
    if not os.path.exists(script_path):
        log(f"[跳过] {description or script_name}: 文件不存在 {script_path}")
        return True  # 不存在不算失败，跳过
    log(f"[执行] {description or script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, script_file] + script_args,
            capture_output=True,
            timeout=timeout,
            cwd=work_dir
        )
        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        log(f"  退出码: {result.returncode}")
        if stdout:
            log(f"  stdout(最后300字): {stdout[-300:]}")
        if stderr:
            log(f"  stderr(最后300字): {stderr[-300:]}")
        if result.returncode != 0:
            log(f"  [警告] {description or script_name} 退出码非0")
            return False
        return True
    except subprocess.TimeoutExpired:
        log(f"  [超时] {description or script_name} 超过{timeout}秒")
        return False
    except Exception as e:
        log(f"  [异常] {description or script_name}: {e}")
        return False

# 0. 服务守护（前置）：关键服务探活+自愈，避免下游步骤跑在宕机服务上
log("--- 步骤0: 服务守护 ---")
if not run_script("service_watchdog.py", timeout=240, description="服务守护"):
    log("[警告] 有服务未恢复，后续步骤可能降级")

# 0.5 计划任务自愈（M4连续性保障，2026-09-16 新增）
# 背景：计划任务的**注册状态**会损坏（XML 文本不变但每轮 rc=2/-1073741510 且无输出），
# 导致连续运行窗口静默断档。每日开机维护时自动检测并重注册（白名单内、先备份 XML）。
log("--- 步骤0.5: 计划任务自愈 ---")
run_script("task_selfheal.py --apply --wait 20", timeout=600, description="计划任务自愈(M4)")

# 1. 7轮滚动备份
log("--- 步骤1: 7轮滚动备份 ---")
if not run_script("backup_with_rotation.py", timeout=120, description="7轮滚动备份"):
    log("[警告] 备份失败，但继续后续步骤")

# 2. 重建消费索引
log("--- 步骤2: 重建消费索引 ---")
try:
    result = subprocess.run(
        [sys.executable, "learning_system.py", "--reindex"],
        capture_output=True,
        timeout=120,
        cwd=work_dir
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    log(f"  退出码: {result.returncode}")
    if stdout:
        log(f"  stdout(最后300字): {stdout[-300:]}")
    if result.returncode != 0:
        log(f"  [警告] 重建消费索引失败")
except Exception as e:
    log(f"  [异常] 重建消费索引: {e}")

# 3. DLQ死信重试
log("--- 步骤3: DLQ死信重试 ---")
run_script("dlq_consumer.py", timeout=120, description="DLQ死信重试")

# 4. 测试数据清理
log("--- 步骤4: 测试数据清理 ---")
run_script("cleanup_test_data.py", timeout=60, description="测试数据清理")

# 5. 消费索引健康检查（V21修正版，静态方法调用）
log("--- 步骤5: 消费索引健康检查 ---")
try:
    sys.path.insert(0, work_dir)
    from v19_integration import ConsumeIndexHealthChecker, AlertManager
    # 修复：ConsumeIndexHealthChecker.check是静态方法，不需要实例化
    check_result = ConsumeIndexHealthChecker.check(stale_threshold_minutes=60, check_unconsumed_messages=True)
    log(f"  检查结果: healthy={check_result.get('healthy')}, reason={check_result.get('reason')}, index_age={check_result.get('index_age')}, pending={check_result.get('pending_messages')}")

    if not check_result.get('healthy') and check_result.get('pending_messages', 0) > 0:
        # 仅在索引过期且有未消费消息时才告警（消除永久误报）
        alert = AlertManager()
        alert_result = alert.send_alert(
            level='WARN',
            title='消费索引健康检查异常',
            message=f"索引过期: {check_result.get('reason')}, 年龄: {check_result.get('index_age')}s, 未消费消息: {check_result.get('pending_messages')}",
            channel='both'
        )
        log(f"  告警已发送: feishu={alert_result.get('feishu')}, local={alert_result.get('local')}")
    else:
        log("  消费索引健康检查通过")
except Exception as e:
    log(f"  [异常] 消费索引健康检查: {e}")

# 6. 系统状态更新
log("--- 步骤6: 系统状态更新 ---")
try:
    state_file = os.path.join(work_dir, ".system_state.json")
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    state["last_success_time"] = datetime.now().isoformat()
    state["last_check"] = datetime.now().isoformat()
    state["last_maintenance"] = datetime.now().isoformat()
    state["maintenance_version"] = "V2_fixed"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    log("  系统状态文件已更新")
except Exception as e:
    log(f"  [异常] 系统状态更新: {e}")
    exit_code = 1

# 7. 到期提醒（V39增强：每日检查未来3天到期任务并推送）
log("--- 步骤7: 到期提醒检查 ---")
try:
    sys.path.insert(0, work_dir)
    from task_insight_extension import send_due_reminder
    success, result = send_due_reminder(days_ahead=3)
    log(f"  到期提醒: success={success}, result={result}")
except Exception as e:
    log(f"  [异常] 到期提醒: {e}")

# 8. 全链路健康监控（V15新增）
log("--- 步骤8: 全链路健康监控 ---")
run_script("health_monitor.py", timeout=60, description="全链路健康监控")

# 9. 数据一致性校验（V15新增）
log("--- 步骤9: 数据一致性校验 ---")
run_script("data_consistency_check.py", timeout=60, description="数据一致性校验")

# 9.5 掌握度M重算（修复D1：复习/费曼信号翻译为掌握度M，避免长期冻结0/1）
log("--- 步骤9.5: 掌握度M重算 ---")
run_script("mastery_recalc.py", timeout=120, description="掌握度M重算")

# 10. 服务自动重启检查（V15新增）
log("--- 步骤10: 服务自动重启检查 ---")
run_script("auto_restart.py", timeout=60, description="服务自动重启检查")

# 11. V15学习功能每日刷新：错题本
log("--- 步骤11: 错题本每日刷新 ---")
run_script("wrong_book.py", timeout=180, description="错题本刷新")

# 12. V15个性化学习推荐每日生成
log("--- 步骤12: 个性化学习推荐 ---")
run_script("personalized_recommender.py", timeout=240, description="个性化推荐")

# 12.5 V43画像自动演化（系统越用越懂我：从流水/错题/洞察自动更新画像表）
log("--- 步骤12.5: 画像自动演化 ---")
run_script("profile_evolve.py", timeout=240, description="画像自动演化(V43)")

# 12.6 V43外部数据抓取（行情/RSS/天气，本地每日一次，云端 Actions 为备援）
log("--- 步骤12.6: 外部数据抓取 ---")
run_script("fetch_external_data.py --push", timeout=120, description="外部数据抓取(V43)")

# 13. V15今日时间块重排（按最新任务）
log("--- 步骤13: 今日时间块重排 ---")
run_script("time_block_plan.py", timeout=240, description="时间块重排")

# 14. V15知识体系演进图（仅每月1号生成，避免每日重复）
log("--- 步骤14: 知识体系演进图(每月1号) ---")
if datetime.now().day == 1:
    run_script("knowledge_evolution.py", timeout=240, description="知识演进图(月度)")
else:
    log("  非每月1号，跳过知识演进图")

# 15. D5反向归档：飞书终态任务 -> Obsidian 已完成目录（只移动不删除）
log("--- 步骤15: Obsidian反向归档 ---")
run_script("obsidian_reverse_archive.py --apply", timeout=120, description="Obsidian反向归档")

# 16. 每月1号恢复演练（只读校验备份，不写生产）
log("--- 步骤16: 恢复演练(每月1号) ---")
if datetime.now().day == 1:
    run_script("recovery_drill.py", timeout=300, description="恢复演练-只读校验(月度)")
    run_script("restore_drill.py", timeout=300, description="恢复演练-隔离还原RPO/RTO(月度)")
else:
    log("  非每月1号，跳过恢复演练")

# 17. 每周日学习周报（P2-5：脚本原无任何调度引用，此处补挂）
log("--- 步骤17: 学习周报(每周日) ---")
if datetime.now().weekday() == 6:  # 0=周一 ... 6=周日
    run_script("weekly_learning_report.py", timeout=240, description="学习周报(周日)")
else:
    log("  非周日，跳过学习周报")

# 18. 安全审计（M1）：密钥/敏感文件/最小权限，每日
log("--- 步骤18: 安全审计 ---")
run_script("security_audit.py", timeout=120, description="安全审计(M1)")

# 19. 可观测性埋点汇总 + SLO 评分卡（M2）
log("--- 步骤19: SLO评分卡 ---")
run_script("slo_monitor.py", timeout=120, description="SLO评分卡(M2)")

# 20. 混沌演练（M3，每月1号，紧随恢复演练）
log("--- 步骤20: 混沌演练(每月1号) ---")
if datetime.now().day == 1:
    run_script("chaos_drill.py", timeout=300, description="混沌演练(M3)")
else:
    log("  非每月1号，跳过混沌演练")

# 21. 红队对抗（M3）：直连真实护栏，每日
log("--- 步骤21: 红队对抗(M3) ---")
run_script("redteam_suite.py", timeout=120, description="红队对抗(M3)")

# 22. 独立复核（M3/M4）：第三方视角复跑 + 交叉校验，每日
log("--- 步骤22: 独立复核 ---")
run_script("independent_verify.py", timeout=420, description="独立复核(M3)")

# 23. 回滚能力自检（R-12）：锚点+计划 dry-run，每日
log("--- 步骤23: 回滚自检 ---")
run_script("rollback.py --self-test", timeout=120, description="回滚自检(R-12)")

# 24. 效率客观计数（M3）：真实埋点/生产数据计数（人工A/B基线仍待录入），每日
log("--- 步骤24: 效率客观计数 ---")
run_script("efficiency_objective.py", timeout=120, description="效率客观计数(M3)")

# 25. 异地/隔离副本复制（M2）：把 backups 复制到独立物理卷并校验，每日
log("--- 步骤25: 异地副本复制 ---")
run_script("offsite_replicate.py", timeout=300, description="异地副本复制(M2)")

# 26. 连续运行监视（M4门槛#3）：每日追加连续性记录，每日
log("--- 步骤26: 连续运行监视 ---")
run_script("uptime_monitor.py", timeout=120, description="连续运行监视(M4)")

# 27. 登录/开机自愈（M4连续性加固）：服务自愈 + 断档留痕，每日兜底
log("--- 步骤27: 登录/开机自愈(断档留痕) ---")
run_script("boot_recover.py --no-watchdog", timeout=180, description="登录/开机自愈(M4)")

# 28. 独立抽样复现（M4门槛#4）：随机抽 10 条独立复跑，每日
log("--- 步骤28: 独立抽样复现 ---")
run_script("independent_sample.py --n 10 --seed 20260916", timeout=300, description="独立抽样复现(M4)")

# 28.5 计划任务自愈（M4连续性保障，2026-09-16 新增）：
# 实测发现计划任务注册状态会损坏（XML 一致但每轮 rc=2 且无输出），
# 连续运行窗口因此断档而监视器看不到。每日自动检测并重注册。
log("--- 步骤28.5: 计划任务自愈 ---")
run_script("task_selfheal.py --apply --wait 20", timeout=600, description="计划任务自愈(M4)")

log(f"=== 维护任务结束，退出码: {exit_code} ===")
sys.exit(exit_code)
