# -*- coding: utf-8 -*-
"""五开阵容配置生成器 (攻略 §10/§12 落地)。

基于已有账号(如方寸山)设计完整五开阵容, 输出可用的系统配置。

用法:
    python -m strategies.lineup --lead 方寸山 --budget low
    python -m strategies.lineup --lead 方寸山 --budget balance
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List

# 门派定位
SECTOR_ROLE = {
    "方寸山": "封印/控场", "女儿村": "封印/固伤", "盘丝洞": "封印/固伤",
    "无底洞": "治疗/固伤", "普陀山": "治疗/固伤", "化生寺": "治疗/辅助",
    "阴曹地府": "固伤/辅助", "地府": "固伤/辅助",
    "魔王寨": "法系输出", "龙宫": "法系输出", "神木林": "法系输出",
    "大唐官府": "物理输出", "狮驼岭": "物理输出", "凌波城": "物理输出", "天宫": "物理/封",
}

# 不同预算阵容模板
LINEUPS = {
    "low": {  # 低投入: 纯固伤+控制
        "name": "低投入纯固伤控制流",
        "desc": "装备成本最低, 成型最快, 五开最稳",
        "need_lead_sector": ["封印", "辅助"],
        "main": ["无底洞", "普陀山", "女儿村", "阴曹地府"],
    },
    "balance": {  # 平衡: 固伤+法+物
        "name": "平衡固伤法物混搭流",
        "desc": "任务覆盖更广, 输出更快, 投入中等",
        "need_lead_sector": ["封印", "辅助", "输出"],
        "main": ["无底洞", "普陀山", "女儿村", "魔王寨"],
    },
    "high": {  # 高效: 封辅法
        "name": "高效封辅法混搭流",
        "desc": "效率最高, 平推多数副本, 投入大",
        "need_lead_sector": ["封印", "辅助", "输出"],
        "main": ["女儿村", "普陀山", "阴曹地府", "魔王寨"],
    },
}

# 推荐等级段
BREAKPOINTS = {69: "过渡停级", 109: "主搬砖停级", 129: "性价比之王", 175: "收益天花板"}


def role_for(sector: str) -> str:
    return SECTOR_ROLE.get(sector, "未知")


def build_lineup(lead_sector: str, budget: str = "low") -> Dict[str, Any]:
    """基于已有门派, 补齐完整五开阵容。"""
    plan = LINEUPS.get(budget, LINEUPS["low"])
    lead_role = role_for(lead_sector)

    # 检查已有门派是否兼容该阵容
    compatible = lead_role in plan["need_lead_sector"] or "封" in lead_role or "辅" in lead_role or "固" in lead_role
    others = plan["main"][:]

    lineup = [
        {"slot": "1(队长)", "sector": lead_sector, "role": lead_role, "src": "已有"},
    ]
    for i, s in enumerate(others, start=2):
        lineup.append({"slot": f"{i}(队员)", "sector": s, "role": role_for(s), "src": "推荐"})

    return {
        "budget": budget,
        "plan_name": plan["name"],
        "plan_desc": plan["desc"],
        "lead_sector": lead_sector,
        "lead_role": lead_role,
        "compatible": compatible,
        "lineup": lineup,
        "breakpoints": BREAKPOINTS,
        "note": "配置只是推荐, 装备/修炼/宝宝优先级见 01_五开配置与成长.md",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="五开阵容生成")
    ap.add_argument("--lead", default="方寸山", help="已有门派")
    ap.add_argument("--budget", default="low", choices=["low", "balance", "high"],
                    help="预算: low/balance/high")
    args = ap.parse_args()
    r = build_lineup(args.lead, args.budget)
    print(f"=== 五开阵容({r['plan_name']}) ===")
    print(f"说明: {r['plan_desc']}")
    print(f"已有门派: {r['lead_sector']}({r['lead_role']}) 兼容: {'是' if r['compatible'] else '需调整'}")
    print("阵容:")
    for u in r["lineup"]:
        print(f"  {u['slot']}: {u['sector']}({u['role']}) [{u['src']}]")
    print("停级点:")
    for lv, desc in r["breakpoints"].items():
        print(f"  {lv}级: {desc}")


if __name__ == "__main__":
    main()
