#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM三顺位降级模块
第一顺位：ALLM本地模型（可选）
第二顺位：DeepSeek API（可选，需要API密钥）
第三顺位：Coze（DEGRADED: 预留实现，需用户提供API密钥和bot_id后启用）

默认使用飞书表格知识索引检索作为基础检索层。
"""

import json
import os
import sys
import time
from pathlib import Path

# 配置文件路径
CONFIG_PATH = Path(__file__).parent / "llm_config.json"

# 默认配置
DEFAULT_CONFIG = {
    "enabled": False,  # 默认禁用LLM降级，使用纯飞书表格检索
    "primary": {
        "name": "ALLM本地模型",
        "type": "local",
        "endpoint": "http://localhost:8080/v1/chat/completions",
        "api_key": "",
        "model": "qwen",
        "timeout": 30,
        "enabled": False
    },
    "secondary": {
        "name": "DeepSeek API",
        "type": "api",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "api_key": "",
        "model": "deepseek-chat",
        "timeout": 30,
        "enabled": False
    },
    "tertiary": {
        "name": "Coze",
        "type": "coze",
        "endpoint": "",
        "api_key": "",
        "bot_id": "",
        "timeout": 30,
        "enabled": False,  # DEGRADED: 预留实现，需用户提供API密钥和bot_id后启用
        "note": "DEGRADED: Coze API未配置，预留实现，需用户提供API密钥和bot_id后启用"
    },
    "fallback": {
        "name": "飞书表格知识索引检索",
        "type": "local_search",
        "enabled": True
    }
}


def load_config():
    """加载LLM配置"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"[LLM] 配置文件加载失败，使用默认配置: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        # 创建默认配置文件
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """保存LLM配置"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[LLM] 配置已保存到: {CONFIG_PATH}")
    except Exception as e:
        print(f"[LLM] 配置保存失败: {e}")


def query_llm(prompt, context="", max_retries=1):
    """
    三顺位降级查询
    
    Args:
        prompt: 用户问题
        context: 上下文信息（从飞书表格检索到的知识）
        max_retries: 最大重试次数
    
    Returns:
        dict: {
            "success": bool,
            "answer": str,
            "source": str,  # 使用的LLM来源
            "error": str  # 错误信息（如果失败）
        }
    """
    config = load_config()
    
    if not config.get("enabled", False):
        return {
            "success": True,
            "answer": context if context else "（知识索引中未找到相关内容，LLM降级已禁用）",
            "source": "飞书表格知识索引检索",
            "error": ""
        }
    
    # 构建完整提示词
    full_prompt = f"请基于以下上下文回答用户问题。\n\n上下文：\n{context}\n\n用户问题：{prompt}\n\n回答："
    
    # 第一顺位：AnythingLLM（本地知识库）或 ALLM本地模型
    if config["primary"].get("enabled", False):
        primary_type = config["primary"].get("type", "api")
        if primary_type == "anythingllm":
            # AnythingLLM API调用
            result = _call_anythingllm(
                endpoint=config["primary"]["endpoint"],
                api_key=config["primary"]["api_key"],
                workspace_slug=config["primary"].get("workspace_slug", ""),
                prompt=prompt,
                context=context,
                mode=config["primary"].get("mode", "chat"),
                timeout=config["primary"].get("timeout", 60)
            )
        else:
            # 普通API调用（ALLM本地模型）
            result = _call_api(
                endpoint=config["primary"]["endpoint"],
                api_key=config["primary"]["api_key"],
                model=config["primary"].get("model", ""),
                prompt=full_prompt,
                timeout=config["primary"].get("timeout", 30),
                max_retries=max_retries
            )
        if result["success"]:
            result["source"] = config["primary"]["name"]
            return result
    
    # 第二顺位：DeepSeek API
    if config["secondary"].get("enabled", False):
        result = _call_api(
            endpoint=config["secondary"]["endpoint"],
            api_key=config["secondary"]["api_key"],
            model=config["secondary"]["model"],
            prompt=full_prompt,
            timeout=config["secondary"].get("timeout", 30),
            max_retries=max_retries
        )
        if result["success"]:
            result["source"] = config["secondary"]["name"]
            return result
    
    # 第三顺位：Coze（DEGRADED: 预留实现，需用户提供API密钥和bot_id后启用）
    if config["tertiary"].get("enabled", False):
        # 检查Coze是否真实配置
        tertiary = config["tertiary"]
        if not tertiary.get("api_key") or not tertiary.get("bot_id"):
            # 未真实配置，跳过Coze，进入最终兜底
            pass
        else:
            # Coze已配置，调用Coze API
            from v19_integration import CozeIntegration
            coze_result = CozeIntegration.chat(prompt, user_id="llm_fallback")
            if coze_result.get("success"):
                return {
                    "success": True,
                    "answer": coze_result.get("reply", ""),
                    "source": config["tertiary"]["name"],
                    "error": ""
                }
    
    # 最终兜底：飞书表格知识索引检索
    return {
        "success": True,
        "answer": context if context else "（知识索引中未找到相关内容）",
        "source": config["fallback"]["name"],
        "error": ""
    }


def _call_anythingllm(endpoint, api_key, workspace_slug, prompt, context="", mode="chat", timeout=60):
    """
    调用AnythingLLM API
    
    Args:
        endpoint: API端点（如 http://localhost:3001/api/v1/workspace/{slug}/chat）
        api_key: AnythingLLM API密钥
        workspace_slug: 工作区slug
        prompt: 用户问题
        context: 上下文信息
        mode: 聊天模式（chat/query）
        timeout: 超时时间
    
    Returns:
        dict: {success, answer, source, error}
    """
    try:
        import requests
    except ImportError:
        return {
            "success": False,
            "answer": "",
            "source": "",
            "error": "requests库未安装"
        }
    
    # 构建提示词（包含上下文）
    if context:
        full_prompt = f"请基于以下上下文回答用户问题。\n\n上下文：\n{context}\n\n用户问题：{prompt}\n\n回答："
    else:
        full_prompt = prompt
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "message": full_prompt,
        "mode": mode,
        "userId": "v16-learning-system"
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=data, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        
        # AnythingLLM返回格式：{ "id": "...", "textResponse": "...", "sources": [...] }
        answer = result.get("textResponse", "")
        if answer:
            return {
                "success": True,
                "answer": answer,
                "source": "AnythingLLM（本地知识库）",
                "error": ""
            }
        else:
            return {
                "success": False,
                "answer": "",
                "source": "",
                "error": "AnythingLLM返回空回答（可能未配置LLM提供商）"
            }
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP错误: {e.response.status_code}"
        if e.response.status_code == 500:
            error_msg += "（AnythingLLM可能未配置LLM提供商，请在设置中配置DeepSeek/OpenAI/Ollama等）"
        return {
            "success": False,
            "answer": "",
            "source": "",
            "error": error_msg
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "answer": "",
            "source": "",
            "error": "无法连接到AnythingLLM（服务未启动？）"
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "answer": "",
            "source": "",
            "error": "AnythingLLM调用超时"
        }
    except Exception as e:
        return {
            "success": False,
            "answer": "",
            "source": "",
            "error": f"AnythingLLM调用失败: {str(e)}"
        }


def _call_api(endpoint, api_key, model, prompt, timeout=30, max_retries=1):
    """调用LLM API"""
    try:
        import requests
    except ImportError:
        return {
            "success": False,
            "answer": "",
            "error": "requests库未安装，请运行: pip install requests"
        }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                answer = result["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "answer": answer,
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "answer": "",
                    "error": f"API返回格式异常: {result}"
                }
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            return {
                "success": False,
                "answer": "",
                "error": str(e)
            }
    
    return {
        "success": False,
        "answer": "",
        "error": "未知错误"
    }


def get_status():
    """获取LLM配置状态"""
    config = load_config()
    
    status = {
        "enabled": config.get("enabled", False),
        "primary": {
            "name": config["primary"]["name"],
            "enabled": config["primary"].get("enabled", False),
            "configured": bool(config["primary"].get("api_key", ""))
        },
        "secondary": {
            "name": config["secondary"]["name"],
            "enabled": config["secondary"].get("enabled", False),
            "configured": bool(config["secondary"].get("api_key", ""))
        },
        "tertiary": {
            "name": config["tertiary"]["name"],
            "enabled": config["tertiary"].get("enabled", False),
            "note": config["tertiary"].get("note", "")
        },
        "fallback": {
            "name": config["fallback"]["name"],
            "enabled": config["fallback"].get("enabled", True)
        }
    }
    
    return status


def print_status():
    """打印LLM配置状态"""
    status = get_status()
    
    print("=" * 60)
    print("LLM三顺位降级配置状态")
    print("=" * 60)
    print(f"总开关: {'✅ 启用' if status['enabled'] else '❌ 禁用'}")
    print()
    
    print(f"第一顺位: {status['primary']['name']}")
    print(f"  状态: {'✅ 启用' if status['primary']['enabled'] else '❌ 禁用'}")
    print(f"  配置: {'✅ 已配置API密钥' if status['primary']['configured'] else '❌ 未配置API密钥'}")
    print()
    
    print(f"第二顺位: {status['secondary']['name']}")
    print(f"  状态: {'✅ 启用' if status['secondary']['enabled'] else '❌ 禁用'}")
    print(f"  配置: {'✅ 已配置API密钥' if status['secondary']['configured'] else '❌ 未配置API密钥'}")
    print()
    
    print(f"第三顺位: {status['tertiary']['name']}")
    print(f"  状态: {'✅ 启用' if status['tertiary']['enabled'] else '❌ 禁用'}")
    if status['tertiary']['note']:
        print(f"  说明: {status['tertiary']['note']}")
    print()
    
    print(f"最终兜底: {status['fallback']['name']}")
    print(f"  状态: {'✅ 启用' if status['fallback']['enabled'] else '❌ 禁用'}")
    print()
    
    if not status['enabled']:
        print("⚠️  LLM降级已禁用，当前使用纯飞书表格知识索引检索")
        print("   如需启用LLM降级，请编辑配置文件: llm_config.json")
    else:
        print("✅ LLM降级已启用，将按顺位尝试调用")
    
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "init":
        config = load_config()
        print("✅ LLM配置已初始化")
        print(f"配置文件: {CONFIG_PATH}")
        print_status()
    else:
        print("用法:")
        print("  python llm_fallback.py status  # 查看配置状态")
        print("  python llm_fallback.py init    # 初始化配置")
        print()
        print("配置文件: llm_config.json")
        print("如需启用LLM降级，请编辑配置文件并设置enabled=true")
