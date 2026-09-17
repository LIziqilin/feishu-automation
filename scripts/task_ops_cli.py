#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务操作统一CLI（供 Hermes Skill / 群指令 / 命令行调用）
=========================================================
python task_ops_cli.py list [待办|进行中|已完成|已归档...]
python task_ops_cli.py find "关键词"
python task_ops_cli.py create "任务名" [--p 中] [--cat 工作]
python task_ops_cli.py complete "任务关键词"      # 销项：置已完成+填完成日期
python task_ops_cli.py archive "任务关键词"       # 归档：置已归档
输出：人类可读文本 + 最后一行 JSON 结果（便于Agent解析）
"""
import sys, io, json, argparse
from datetime import datetime
sys.path.insert(0, '.')
from v15_features import *

ACTIVE = {"待办","进行中","待开始"}

def _all_tasks():
    items = list_records(T_TASK)
    out=[]
    for it in items:
        f=it["fields"]
        out.append({"rid":it["record_id"],
                    "name":cell_text(f.get("任务名称")),
                    "status":cell_select(f.get("状态")) or "待办",
                    "p":cell_select(f.get("优先级")),
                    "cat":cell_select(f.get("类别")),
                    "due":ts_to_date(f.get("截止日期"))})
    return out

def _match(tasks, kw, only_active=False):
    """模糊匹配：标题含关键词。only_active时只匹配活跃任务"""
    cand=[t for t in tasks if kw in t["name"] and (not only_active or t["status"] in ACTIVE)]
    return cand

def cmd_list(args):
    tasks=_all_tasks()
    if args.status:
        want=set(args.status); tasks=[t for t in tasks if t["status"] in want]
    tasks.sort(key=lambda t:(t["status"],t["name"]))
    for t in tasks:
        print(f"[{t['status']}|{t['p'] or '-'}|{t['cat'] or '-'}] {t['name']} (截止{t['due'] or '无'})")
    print(json.dumps({"ok":True,"count":len(tasks)},ensure_ascii=False))

def cmd_find(args):
    tasks=_all_tasks(); cand=[t for t in tasks if args.kw in t["name"]]
    for t in cand:
        print(f"[{t['status']}] {t['name']} rid={t['rid']}")
    print(json.dumps({"ok":True,"count":len(cand)},ensure_ascii=False))

def cmd_create(args):
    fields={"任务名称":args.name,"状态":"待办","优先级":args.p or "中","类别":args.cat or "工作",
            "创建日期":date_ms()}
    r=create_record(T_TASK,fields)
    rid=r.get("data",{}).get("record",{}).get("record_id","")
    print(f"✅ 已创建任务：{args.name}（优先级{args.p or '中'}）rid={rid}")
    print(json.dumps({"ok":r.get("code")==0,"rid":rid,"name":args.name},ensure_ascii=False))

def _set_status(kw,status,fill_done=False):
    tasks=_all_tasks()
    cand=_match(tasks,kw,only_active=(status=="已完成"))
    if not cand:
        # 兜底：不限状态再找
        cand=_match(tasks,kw,only_active=False)
        cand=[t for t in cand if t["status"]!=status]
    if not cand:
        print(f"❌ 没找到含「{kw}」的任务")
        print(json.dumps({"ok":False,"reason":"not_found"},ensure_ascii=False)); return
    if len(cand)>1:
        print(f"⚠️ 匹配到{len(cand)}条，请用更精确的名称：")
        for t in cand: print(f"  - [{t['status']}] {t['name']}")
        print(json.dumps({"ok":False,"reason":"ambiguous","candidates":[t["name"] for t in cand]},ensure_ascii=False)); return
    t=cand[0]; fields={"状态":status}
    if fill_done: fields["实际完成日期"]=date_ms()
    update_record(T_TASK,t["rid"],fields)
    print(f"✅ 「{t['name']}」→ {status}")
    print(json.dumps({"ok":True,"rid":t["rid"],"name":t["name"],"status":status},ensure_ascii=False))

def cmd_complete(args): _set_status(args.kw,"已完成",fill_done=True)
def cmd_archive(args): _set_status(args.kw,"已归档")

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("list"); p.add_argument("status",nargs="*"); p.set_defaults(fn=cmd_list)
    p=sub.add_parser("find"); p.add_argument("kw"); p.set_defaults(fn=cmd_find)
    p=sub.add_parser("create"); p.add_argument("name"); p.add_argument("--p",default="中"); p.add_argument("--cat",default="工作"); p.set_defaults(fn=cmd_create)
    p=sub.add_parser("complete"); p.add_argument("kw"); p.set_defaults(fn=cmd_complete)
    p=sub.add_parser("archive"); p.add_argument("kw"); p.set_defaults(fn=cmd_archive)
    args=ap.parse_args(); args.fn(args)

if __name__=="__main__":
    main()
