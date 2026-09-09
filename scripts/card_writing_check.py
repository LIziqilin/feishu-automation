# -*- coding: utf-8 -*-
"""
card_writing_check.py — V13 波次2 卡片写作五规校验器（纯函数）
五规（教育专家定稿）：
  1. 一卡一问：问题正面以 ? / ？结尾或含"是什么/为什么/如何/区别"
  2. 答案可判：标准答案非空且长度>=10字
  3. 问"为什么/区别"（高阶问题）——软性提示，不强制
  4. 超 3 行拆卡：答案换行<=3 行（硬性）
  5. "卡面差"累计 2 次强制重写：由错因字段聚合判断（IO 层做，本模块给判定函数）
用法: python card_writing_check.py --check 正面 背面
"""
import sys, io, argparse
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)


def check_card(question, answer):
    """返回 (violations:list[str], warnings:list[str])"""
    v, w = [], []
    q = (question or '').strip()
    a = (answer or '').strip()
    # 一卡一问
    if not q:
        v.append('问题正面为空')
    elif not (q.endswith('?') or q.endswith('？') or
              any(k in q for k in ('是什么', '为什么', '如何', '区别'))):
        w.append('问题不像一问（建议以?结尾或含"为什么/区别"）')
    # 答案可判
    if not a:
        v.append('标准答案为空')
    elif len(a) < 10:
        v.append('答案过短(<10字)，无法形成可判答案')
    # 问为什么/区别
    if q and not any(k in q for k in ('为什么', '区别', '对比')):
        w.append('高阶提示：尝试问"为什么/区别"以加深加工')
    # 超3行拆卡
    if a:
        n_lines = len([l for l in a.splitlines() if l.strip()])
        if n_lines > 3:
            v.append('答案%d行，超3行应拆卡' % n_lines)
    return v, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', nargs=2, metavar=('Q', 'A'), default=None)
    a = ap.parse_args()
    if not a.check:
        print('用法: python card_writing_check.py --check "问题" "答案"')
        return 2
    q, ans = a.check
    v, w = check_card(q, ans)
    print('=== 卡片五规校验 ===')
    if v:
        print('违规(需改):')
        for x in v:
            print('  ✗ %s' % x)
    else:
        print('✓ 硬性规则通过')
    if w:
        print('提示(可选):')
        for x in w:
            print('  · %s' % x)
    print('PASS' if not v else 'VIOLATIONS')


if __name__ == '__main__':
    main()
