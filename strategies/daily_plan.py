# -*- coding: utf-8 -*-
"""逐日五开计划生成器 (攻略落地: 第1天->第60天->成型)。

根据新区开荒天数, 生成可执行的每日流程(任务优先级/目标/五开状态)。
基于确定性模板, 不虚构收益数字; 收益列标注"需实测"。

用法:
    python -m strategies.daily_plan --day 7
    python -m strategies.daily_plan --day 30
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List


# 开荒阶段模板: 天数区间 -> 阶段信息
PHASES = [
    {"day": (1, 3), "goal": "建5号+主号到20", "level": "0-20", "five": "只练主号",
     "tasks": ["主线", "新手任务", "拜师"], "priority": ["主线>拜师>新手"],
     "money": "无(纯投入)", "note": "其余4号建好吃新区奖励"},
    {"day": (4, 7), "goal": "主号到40, 启动五开", "level": "20-40", "five": "5号齐练",
     "tasks": ["师门", "主线", "剧情"], "priority": ["师门>主线"],
     "money": "师门现金", "note": "等级尽量拉平"},
    {"day": (8, 14), "goal": "全队到60, 稳定抓鬼封妖", "level": "40-60", "five": "五开成型",
     "tasks": ["师门", "抓鬼", "封妖"], "priority": ["师门>封妖>抓鬼"],
     "money": "师门+抓鬼+封妖掉落", "note": "纯固伤阵容, 环装即可"},
    {"day": (15, 30), "goal": "69停级, 补技能修炼", "level": "60-69", "five": "五开停级",
     "tasks": ["师门", "封妖", "抓鬼", "活动"], "priority": ["师门>活动>封妖>抓鬼"],
     "money": "现金+物品", "note": "停级沉淀, 钱留修炼"},
    {"day": (31, 60), "goal": "69成型, 评估上109", "level": "69停级", "five": "五开成熟",
     "tasks": ["师门", "抓鬼", "副本", "周末活动"], "priority": ["周末>师门>抓鬼>副本"],
     "money": "现金+物品+储备", "note": "收益瓶颈时评估上109"},
    {"day": (61, 999), "goal": "109成型主搬砖", "level": "109停级", "five": "五开满配",
     "tasks": ["师门", "抓鬼", "封妖", "副本", "周末"], "priority": ["周末>师门>抓鬼>封妖>副本"],
     "money": "现金+物品+储备", "note": "收益最大化单小时"},
]


def _daily_order(tasks: List[str], priority: List[str]) -> List[str]:
    """把任务按优先级和耗时排出顺序(确定性)。"""
    # 简化: 优先级在前, 其余按固定顺序
    ordered = []
    for p in priority:
        for kw in p.split(">"):
            for t in tasks:
                if kw in t and t not in ordered:
                    ordered.append(t)
    for t in tasks:
        if t not in ordered:
            ordered.append(t)
    return ordered


def plan_for_day(day: int) -> Dict[str, Any]:
    """根据天数返回当天可执行计划。"""
    for ph in PHASES:
        if ph["day"][0] <= day <= ph["day"][1]:
            daily = _daily_order(ph["tasks"], ph["priority"])
            return {
                "day": day,
                "phase": f"第{ph['day'][0]}-{ph['day'][1]}天",
                "goal": ph["goal"],
                "level_range": ph["level"],
                "five_status": ph["five"],
                "daily_flow": daily,
                "money_note": ph["money"],
                "note": ph["note"],
                "progression": f"第{day}天 目标: {ph['goal']} | 等级: {ph['level']} | 五开: {ph['five']}",
            }
    return {"day": day, "phase": "超出规划", "progression": "长期搬砖期", "daily_flow": ["师门", "抓鬼", "副本", "周末活动"]}


def milestone_roadmap() -> List[Dict[str, Any]]:
    """返回完整里程碑路线(第1/3/7/14/30/60/成型)。"""
    return [
        {"day": 1, "goal": "建5号+主号20", "level": "0-20"},
        {"day": 3, "goal": "主号40启动五开", "level": "20-40"},
        {"day": 7, "goal": "全队60稳定刷", "level": "40-60"},
        {"day": 14, "goal": "69停级沉淀", "level": "60-69"},
        {"day": 30, "goal": "69成型评估上109", "level": "69"},
        {"day": 60, "goal": "109成型主搬砖", "level": "109"},
        {"day": 90, "goal": "五开成型日常", "level": "109+", "note": "收益最大化"},
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="逐日五开计划")
    ap.add_argument("--day", type=int, default=7, help="开荒第几天")
    ap.add_argument("--roadmap", action="store_true", help="显示里程碑路线")
    args = ap.parse_args()
    if args.roadmap:
        print("=== 五开里程碑路线 ===")
        for m in milestone_roadmap():
            print(f"  第{m['day']:>3}天: {m['goal']} (等级{m['level']})")
        return
    p = plan_for_day(args.day)
    print(f"=== 第{args.day}天 五开计划 ===")
    print(f"阶段: {p['phase']}")
    print(f"目标: {p['goal']}")
    print(f"等级: {p['level_range']} | 五开: {p['five_status']}")
    print(f"今日流程: {' -> '.join(p['daily_flow'])}")
    print(f"收益: {p['money_note']}(需实测)")
    print(f"备注: {p['note']}")


if __name__ == "__main__":
    main()
