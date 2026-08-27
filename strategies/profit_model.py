# -*- coding: utf-8 -*-
"""五开搬砖收益测算工具 (攻略 §19, 不虚构数据)。

用户填实测数据(现金/物品/消耗), 工具自动计算日/周/月收益与回本周期。

用法:
    python -m strategies.profit_model --cash 200000 --item 150000 --cost 30000
    python -m strategies.profit_model --mode 交互
"""
from __future__ import annotations

import argparse

# 点卡成本(元/小时, 5开)【需验证】按实际点卡价格填
POINT_CARD_PER_HOUR = 0.5  # 单位: 元, 需按实际点卡换算


def hour_profit(cash: float, item_sell: float, other: float, cost: float) -> float:
    """小时收益 = 现金 + 物品出售 + 其他可变现 - 消耗成本(游戏币)。"""
    return cash + item_sell + other - cost


def daily_profit(hour_rate, hours):
    return hour_rate * hours


def weekly_profit(hour_rate, daily_hours, weekend_boost=1.3):
    """周末(2天)收益加成。"""
    weekday = 5 * daily_hours * hour_rate
    weekend = 2 * daily_hours * hour_rate * weekend_boost
    return weekday + weekend


def monthly_profit(hour_rate, daily_hours):
    return weekly_profit(hour_rate, daily_hours) * 4.3


def calc(per_hour_cash=200000, per_hour_item=150000, per_hour_cost=30000,
         other=0.0):
    """按每小时收益计算 2/4/6/8 小时。"""
    rate = hour_profit(per_hour_cash, per_hour_item, other, per_hour_cost)
    print(f"小时收益 = 现金{per_hour_cash} + 物品{per_hour_item} + 其他{other} - 消耗{per_hour_cost}")
    print(f"         = {rate:,} 游戏币/小时")
    print()
    print("时段 | 日收益(游戏币) | 点卡成本(元) | 净收益(元/时)【需验证按实际点卡】")
    for h in (2, 4, 6, 8):
        d = daily_profit(rate, h)
        elec = h * POINT_CARD_PER_HOUR * 5
        print(f"{h}h  | {d:>12,} | {elec:>6.1f} | {-elec:>8.2f}")
    print()
    # 周/月(假设每天4小时)
    daily = daily_profit(rate, 4)
    wk = weekly_profit(rate, 4)
    mo = monthly_profit(rate, 4)
    print("假设每天4小时: 日收益", f"{daily:,}", "| 周收益", f"{wk:,}", "| 月收益", f"{mo:,}")
    print()
    print("⚠️ 以上数值来自你填的实测输入, 未虚构; 点卡成本/周末加成需按当前¥服务器物价重新测算。")
    return rate


def main() -> None:
    ap = argparse.ArgumentParser(description="五开收益测算")
    ap.add_argument("--cash", type=float, default=200000, help="每小时现金收益(游戏币)")
    ap.add_argument("--item", type=float, default=150000, help="每小时物品出售收益")
    ap.add_argument("--other", type=float, default=0.0, help="其他可变现")
    ap.add_argument("--cost", type=float, default=30000, help="每小时消耗(药/装备折旧)")
    args = ap.parse_args()
    calc(args.cash, args.item, args.cost, args.other)


if __name__ == "__main__":
    main()
