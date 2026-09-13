#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
weekly_review.py - 周日复盘功能（P1-2）
统计本周答题数、正确率、升级卡片数、ROI等数据，生成复盘报告并推送到群
"""
from v19_integration import BASE_TOKEN

import subprocess, json, sys, re, os
from datetime import datetime, timedelta
from collections import defaultdict


CARD_TABLE = "tblpLvxyYpDJgF92"
FLOW_TABLE = "tblbznzCSpPhSz93"
CHAT_ID = "oc_1fe154e172ab04622b7ffa810ac172bc"

def run_cmd(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=False)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except Exception as e:
        return False, "", str(e)

def send_message(text):
    """发送消息到群"""
    cmd = ["lark-cli", "im", "+messages-send",
           "--chat-id", CHAT_ID, "--as", "user", "--text", text]
    return run_cmd(cmd)

def get_all_flows():
    """获取所有流水记录"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", FLOW_TABLE, "--as", "user", "--limit", "200", "--format", "json"]
    ok, stdout, stderr = run_cmd(cmd)
    if not ok:
        return []
    try:
        data = json.loads(stdout)
        records = data.get("data", {}).get("data", [])
        record_ids = data.get("data", {}).get("record_id_list", [])
        fields = data.get("data", {}).get("fields", [])
        result = []
        for i, rec in enumerate(records):
            if isinstance(rec, list):
                rec_dict = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, field in enumerate(fields):
                    if j < len(rec):
                        rec_dict[field] = rec[j]
                result.append(rec_dict)
        return result
    except:
        return []

def get_all_cards():
    """获取所有学习卡片"""
    cmd = ["lark-cli", "base", "+record-list", "--base-token", BASE_TOKEN,
           "--table-id", CARD_TABLE, "--as", "user", "--limit", "100", "--format", "json"]
    ok, stdout, stderr = run_cmd(cmd)
    if not ok:
        return []
    try:
        data = json.loads(stdout)
        records = data.get("data", {}).get("data", [])
        record_ids = data.get("data", {}).get("record_id_list", [])
        fields = data.get("data", {}).get("fields", [])
        result = []
        for i, rec in enumerate(records):
            if isinstance(rec, list):
                rec_dict = {"_record_id": record_ids[i] if i < len(record_ids) else ""}
                for j, field in enumerate(fields):
                    if j < len(rec):
                        rec_dict[field] = rec[j]
                result.append(rec_dict)
        return result
    except:
        return []

def generate_speech_cards(cards, count=3):
    """生成脱稿讲3张卡片内容
    
    Args:
        cards: 学习卡片列表
        count: 选取卡片数量
        
    Returns:
        str: 脱稿讲卡片内容
    """
    # 优先选LEARNING状态、连续正确次数高、复习次数多的卡片
    learning_cards = [c for c in cards if "LEARNING" in str(c.get("卡片状态", ""))]
    if not learning_cards:
        learning_cards = cards[:count]
    
    # 按连续正确次数+复习次数排序，取前count张
    def card_score(c):
        correct = c.get("连续正确次数", 0) or 0
        review = c.get("复习次数", 0) or 0
        return correct * 2 + review
    
    sorted_cards = sorted(learning_cards, key=card_score, reverse=True)[:count]
    
    speech = "🎤 脱稿讲3张（闭眼回忆，不看答案）\n\n"
    for i, card in enumerate(sorted_cards, 1):
        question = str(card.get("卡片问题正面", "未知问题"))[:60]
        answer = str(card.get("标准答案背面", card.get("标准答案_AI", "暂无答案")))[:100]
        tags = card.get("标签", [])
        if isinstance(tags, list):
            tags_str = "、".join([str(t) for t in tags[:3]])
        else:
            tags_str = str(tags)[:30]
        
        # 记忆技巧：基于标签和错因生成
        error_reason = str(card.get("错因", ""))
        if error_reason and error_reason != "None":
            memory_tip = f"注意错因：{error_reason}，重点复习"
        else:
            memory_tip = "联想记忆：结合实际工作场景回忆"
        
        speech += f"【第{i}张】{question}\n"
        speech += f"  答案要点：{answer}\n"
        speech += f"  关键点：{tags_str} | 记忆等级{card.get('记忆等级', '?')}\n"
        speech += f"  记忆技巧：{memory_tip}\n"
        speech += f"  （请闭眼复述上述要点，复述不出来的标记为重点复习）\n\n"
    
    return speech


def generate_application_scenario(cards, week_answers):
    """生成1个应用场景
    
    Args:
        cards: 学习卡片列表
        week_answers: 本周答题记录
        
    Returns:
        str: 应用场景内容
    """
    # 优先从有真实应用场景（非【未知】占位）的卡片中选取
    cards_with_scenario = [c for c in cards if c.get("应用场景") 
                           and not str(c.get("应用场景", "")).startswith("【未知】")]
    if not cards_with_scenario:
        # 次选：有应用场景字段但包含占位符的，清理后使用
        cards_with_scenario = [c for c in cards if c.get("应用场景")]
    
    if cards_with_scenario:
        card = cards_with_scenario[0]
        scenario_raw = str(card.get("应用场景", ""))
        # 清理【未知】占位符前缀
        if scenario_raw.startswith("【未知】应用场景："):
            scenario = scenario_raw[len("【未知】应用场景："):].strip()
        elif scenario_raw.startswith("【未知】"):
            scenario = scenario_raw[len("【未知】"):].strip()
        else:
            scenario = scenario_raw
        scenario = scenario[:200]
        question = str(card.get("卡片问题正面", "未知"))[:50]
    else:
        # 基于本周学习最多的科目生成通用应用场景
        subjects = defaultdict(int)
        for c in cards:
            subj = c.get("知识点分类_AI", c.get("科目", ""))
            if subj:
                if isinstance(subj, list):
                    for s in subj:
                        subjects[str(s)] += 1
                else:
                    subjects[str(subj)] += 1
        
        if subjects:
            top_subject = max(subjects.items(), key=lambda x: x[1])[0]
        else:
            top_subject = "日常工作"
        
        question = f"本周学习重点：{top_subject}"
        scenario = (f"在日常{top_subject}工作中，遇到相关问题时，回忆本周学习的核心知识点，"
                   f"应用到实际场景中。建议在工作中主动寻找1-2个应用机会，"
                   f"并记录应用效果到卡片的实战留痕字段。")
    
    result = "💡 本周应用场景（1个）\n\n"
    result += f"关联卡片：{question}\n"
    result += f"场景描述：{scenario}\n"
    result += f"行动要求：本周内至少在1个实际场景中应用此知识点，并记录效果\n\n"
    
    return result


def generate_roi_data(week_answers, cards, total_answers):
    """生成ROI数据
    
    Args:
        week_answers: 本周答题记录
        cards: 学习卡片列表
        total_answers: 总答题数
        
    Returns:
        str: ROI数据内容
    """
    correct = len([f for f in week_answers if f.get("结果", "") == "会"])
    wrong = len([f for f in week_answers if f.get("结果", "") == "不会"])
    fuzzy = len([f for f in week_answers if f.get("结果", "") == "模糊"])
    accuracy = (correct / total_answers * 100) if total_answers > 0 else 0
    
    # 统计卡片状态
    mastered = len([c for c in cards if "MASTERED" in str(c.get("卡片状态", ""))])
    learning = len([c for c in cards if "LEARNING" in str(c.get("卡片状态", ""))])
    not_started = len([c for c in cards if "NOT_STARTED" in str(c.get("卡片状态", ""))])
    total_cards = len(cards)
    
    # 计算平均复习次数
    review_counts = [c.get("复习次数", 0) for c in cards if c.get("复习次数", 0)]
    avg_review = sum(review_counts) / len(review_counts) if review_counts else 0
    
    # 计算掌握率
    mastery_rate = (mastered / total_cards * 100) if total_cards > 0 else 0
    
    # 学习效率评分（综合正确率、掌握率、复习效率）
    efficiency_score = (accuracy * 0.4 + mastery_rate * 0.3 + min(avg_review * 10, 100) * 0.3) if total_answers > 0 else 0
    
    roi = "📊 本周ROI数据（投入产出分析）\n\n"
    roi += "【投入】\n"
    roi += f"  • 本周答题：{total_answers} 题（会{correct}/不会{wrong}/模糊{fuzzy}）\n"
    roi += f"  • 平均复习次数：{avg_review:.1f} 次/张\n"
    roi += f"  • 学习中卡片：{learning} 张\n\n"
    
    roi += "【产出】\n"
    roi += f"  • 已掌握卡片：{mastered} 张（掌握率 {mastery_rate:.1f}%）\n"
    roi += f"  • 本周正确率：{accuracy:.1f}%\n"
    roi += f"  • 未开始卡片：{not_started} 张（待学习）\n\n"
    
    roi += "【效率评估】\n"
    roi += f"  • 学习效率评分：{efficiency_score:.1f}/100\n"
    if efficiency_score >= 70:
        roi += "  • 评级：高效（投入产出比良好，继续保持）\n"
    elif efficiency_score >= 50:
        roi += "  • 评级：中等（建议优化复习策略，提升正确率）\n"
    else:
        roi += "  • 评级：待提升（建议减少新卡片，重点巩固已学内容）\n"
    
    roi += "\n  💡 ROI提升建议：聚焦高频错题，减少重复复习已掌握内容\n\n"
    
    return roi


def generate_weekly_report():
    """生成周复盘报告"""
    now = datetime.now()
    # 本周一到周日
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    week_start = monday.strftime("%Y-%m-%d")
    week_end = sunday.strftime("%Y-%m-%d")

    flows = get_all_flows()
    cards = get_all_cards()

    # 统计本周答题
    week_answers = [f for f in flows if f.get("结果", "") in ["会", "不会", "模糊"]
                     and week_start <= str(f.get("客户端时间戳", ""))[:10] <= week_end]

    total_answers = len(week_answers)
    correct = len([f for f in week_answers if f.get("结果", "") == "会"])
    wrong = len([f for f in week_answers if f.get("结果", "") == "不会"])
    fuzzy = len([f for f in week_answers if f.get("结果", "") == "模糊"])
    accuracy = (correct / total_answers * 100) if total_answers > 0 else 0

    # 统计升级卡片（MASTERED状态）
    mastered_cards = [c for c in cards if "MASTERED" in str(c.get("卡片状态", ""))]
    # 统计学习中卡片
    learning_cards = [c for c in cards if "LEARNING" in str(c.get("卡片状态", ""))]
    # 统计未开始卡片
    not_started = [c for c in cards if "NOT_STARTED" in str(c.get("卡片状态", ""))]

    # 生成报告
    report = f"""📊 本周复盘报告（{week_start} ~ {week_end}）

📈 学习统计
• 本周答题总数：{total_answers} 题
• 正确（会）：{correct} 题
• 错误（不会）：{wrong} 题
• 模糊：{fuzzy} 题
• 正确率：{accuracy:.1f}%

📚 卡片状态
• 已掌握（MASTERED）：{len(mastered_cards)} 张
• 学习中（LEARNING）：{len(learning_cards)} 张
• 未开始（NOT_STARTED）：{len(not_started)} 张
• 总计：{len(cards)} 张

💡 学习建议
"""
    if accuracy >= 80:
        report += "• 本周正确率较高，建议适当增加新卡片学习量\n"
    elif accuracy >= 60:
        report += "• 本周正确率中等，建议重点复习错题\n"
    else:
        report += "• 本周正确率偏低，建议减少新卡片，重点巩固已学内容\n"

    if total_answers < 20:
        report += "• 本周答题量偏少，建议每天保持至少5题的练习量\n"

    report += "\n继续加油，坚持就是胜利！💪\n\n"
    
    # V33修复：添加脱稿讲3张、应用场景、ROI数据三部分
    report += "=" * 40 + "\n\n"
    report += generate_speech_cards(cards, count=3)
    report += generate_application_scenario(cards, week_answers)
    report += generate_roi_data(week_answers, cards, total_answers)
    
    return report

def main():
    print("[周复盘模式] 生成本周复盘报告...")
    report = generate_weekly_report()
    print(report)
    print()

    # 推送到群
    print("推送复盘报告到群...")
    ok, stdout, stderr = send_message(report)
    if ok:
        print("✓ 复盘报告已推送")
    else:
        print(f"✗ 推送失败: {stderr}")

    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
