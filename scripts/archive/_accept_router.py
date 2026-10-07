# -*- coding: utf-8 -*-
"""验收：逐条指令路由识别测试（不真正执行LLM/子进程）"""
import sys, os, io
sys.path.insert(0, r"D:\AI-Tools\feishu\V13方案增强\scripts")
os.chdir(r"D:\AI-Tools\feishu\V13方案增强\scripts")

import v15_command_router as rtr

# mock 掉重型子命令执行，避免真跑 LLM / subprocess
def fake_run(script, timeout=180):
    return True, "[mock] 已执行:" + script
rtr._run_sub = fake_run

# mock 重模块
class FakeMod:
    def start(self, kw=None): return None, "[mock]费曼抽题"
    def grade(self, t): return None, "[mock]讲解打分"
sys.modules['feynman_verify'] = FakeMod()

class Pom:
    @staticmethod
    def log_pomodoro(*a): pass
    @staticmethod
    def build_board(): pass
    @staticmethod
    def today_summary(): return (0, 0, {})
sys.modules['pomodoro'] = Pom

class PR:
    @staticmethod
    def recommend(n): return [], {"fatigue": False}
    @staticmethod
    def build_note(*a): pass
sys.modules['personalized_recommender'] = PR

class SR:
    @staticmethod
    def answer(q): return "[mock]RAG回答:" + q[:20]
sys.modules['system_rag'] = SR

class CG:
    @staticmethod
    def run(q): return True, "[mock]Coze回答:" + q[:20]
sys.modules['coze_gateway'] = CG

class IK:
    @staticmethod
    def sink_text(t, c, tag=None): return "recMOCK123"
sys.modules['import_knowledge'] = IK

# 待验收指令（来自手册）
cases = [
    # 学习类
    "错题本", "记录错题：复利公式我记成(1+r)^n",
    "费曼", "费曼 复利", "讲解：复利就是利滚利",
    "番茄", "番茄25 写报告",
    # 分析/AI类
    "今日推荐", "个性化推荐", "知识演进", "演进图", "知识缺口", "盲点",
    "画像更新", "越用越懂", "三察", "今日洞察", "沉淀洞察",
    "问系统：什么是复利效应", "智能：帮我写周报", "导知识：一段文字",
    "记忆分层", "时间块", "生成学习周报", "更新用户画像", "系统健康诊断",
]

print("="*60)
print("V15路由识别验收（%d条）" % len(cases))
print("="*60)
fail = 0
for c in cases:
    try:
        handled, reply = rtr.handle_v15_command(c)
        flag = "OK " if handled else "MISS"
        if not handled: fail += 1
        print(f"[{flag}] {c[:30]:32s} -> {str(reply)[:40]}")
    except Exception as e:
        fail += 1
        print(f"[ERR] {c[:30]:32s} -> {e}")
print("-"*60)
print(f"识别通过: {len(cases)-fail}/{len(cases)}")
