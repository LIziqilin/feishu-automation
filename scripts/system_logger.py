#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
system_logger.py - 统一系统日志工具模块

提供统一的日志格式和工具函数，供所有脚本使用。
日志格式：[时间戳] [级别] [模块] 消息

用法：
  from system_logger import log, log_error, log_start, log_complete
  log("INFO", "模块名", "消息内容")
  log_error("模块名", "错误消息", exception)
"""
import os
import sys
import traceback
from datetime import datetime

# 日志级别
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# 当前日志级别（可通过环境变量设置）
CURRENT_LEVEL = LOG_LEVELS.get(os.environ.get("LOG_LEVEL", "INFO"), 20)

# 日志文件路径（可选）
LOG_FILE = os.environ.get("LOG_FILE", "")


def log(level, module, message):
    """
    统一日志输出
    格式：[时间戳] [级别] [模块] 消息

    Args:
        level: 日志级别（DEBUG/INFO/WARN/ERROR/CRITICAL）
        module: 模块名称
        message: 日志消息
    """
    if LOG_LEVELS.get(level, 0) < CURRENT_LEVEL:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] [{module}] {message}"

    # 输出到控制台
    print(log_line)

    # 输出到日志文件（如果配置了）
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception:
            pass  # 日志文件写入失败不影响主流程


def log_error(module, message, exception=None):
    """
    错误日志，包含完整错误堆栈

    Args:
        module: 模块名称
        message: 错误消息
        exception: 异常对象（可选）
    """
    log("ERROR", module, message)
    if exception:
        log("ERROR", module, f"异常类型: {type(exception).__name__}")
        log("ERROR", module, f"异常信息: {str(exception)}")
        log("ERROR", module, f"错误堆栈:\n{traceback.format_exc()}")


def log_start(module, params=None):
    """
    记录开始执行日志

    Args:
        module: 模块名称
        params: 执行参数（可选）
    """
    log("INFO", module, "=" * 60)
    log("INFO", module, f"开始执行 - {module}")
    if params:
        log("INFO", module, f"执行参数: {params}")
    log("INFO", module, "=" * 60)


def log_complete(module, success_count=0, fail_count=0, duration_seconds=0):
    """
    记录执行完成日志

    Args:
        module: 模块名称
        success_count: 成功数量
        fail_count: 失败数量
        duration_seconds: 总耗时（秒）
    """
    log("INFO", module, "=" * 60)
    log("INFO", module, f"执行完成 - {module}")
    log("INFO", module, f"成功: {success_count}, 失败: {fail_count}")
    log("INFO", module, f"总耗时: {duration_seconds:.2f}秒")
    if fail_count > 0:
        log("WARN", module, f"存在{fail_count}个失败项，请关注")
    log("INFO", module, "=" * 60)


def log_step(module, step_num, step_name, status="开始"):
    """
    记录步骤执行日志

    Args:
        module: 模块名称
        step_num: 步骤编号
        step_name: 步骤名称
        status: 状态（开始/完成/失败）
    """
    log("INFO", module, f"步骤{step_num}: {step_name} - {status}")


def get_logger(module_name):
    """
    获取指定模块的日志器（闭包）

    Args:
        module_name: 模块名称

    Returns:
        dict: 包含log、log_error、log_start、log_complete、log_step的字典
    """
    return {
        "log": lambda level, msg: log(level, module_name, msg),
        "log_error": lambda msg, exc=None: log_error(module_name, msg, exc),
        "log_start": lambda params=None: log_start(module_name, params),
        "log_complete": lambda sc=0, fc=0, dur=0: log_complete(module_name, sc, fc, dur),
        "log_step": lambda num, name, status="开始": log_step(module_name, num, name, status),
    }


# 模块自检
if __name__ == "__main__":
    print("=== system_logger.py 自检 ===")
    print()

    # 测试基本日志
    log("INFO", "自检", "这是一条INFO日志")
    log("DEBUG", "自检", "这是一条DEBUG日志（默认级别下不显示）")
    log("WARN", "自检", "这是一条WARN日志")

    # 测试错误日志
    try:
        raise ValueError("测试异常")
    except ValueError as e:
        log_error("自检", "测试错误日志", e)

    # 测试开始/完成日志
    log_start("自检模块", {"param1": "value1", "param2": "value2"})
    log_complete("自检模块", success_count=5, fail_count=1, duration_seconds=1.23)

    # 测试步骤日志
    log_step("自检模块", 1, "初始化", "完成")
    log_step("自检模块", 2, "数据处理", "完成")
    log_step("自检模块", 3, "结果输出", "开始")

    print()
    print("=== 自检完成 ===")
