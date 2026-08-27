# -*- coding: utf-8 -*-
"""任务收益数据库 + 按等级筛选工具 (攻略 §17)。

用法:
    python -m strategies.task_db --level 109
    python -m strategies.task_db --level 69 --sort cash
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TaskEntry:
    name: str
    min_level: int
    best_level: str
    wukai: str
    exp: str
    cash: str
    item: str
    reserve: str
    time: str
    tier: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "min_level": self.min_level,
                "best_level": self.best_level, "wukai": self.wukai,
                "exp": self.exp, "cash": self.cash, "item": self.item,
                "reserve": self.reserve, "time": self.time, "tier": self.tier,
                "reason": self.reason}


TASK_DB: List[TaskEntry] = [
    TaskEntry("师门任务", 20, "69-175", "高", "稳", "稳", "低", "有", "中", "S", "每天必做, 现金+储备稳定"),
    TaskEntry("抓鬼", 40, "69-129", "中", "高", "中", "中", "低", "长", "A", "经验+现金主力"),
    TaskEntry("封妖", 40, "69-109", "中", "中", "中", "高", "低", "中", "A", "掉落环装宝石"),
    TaskEntry("侠士副本", 80, "109-175", "高", "中", "中", "高", "低", "长", "A", "109开放, 物品收益高"),
    TaskEntry("周末活动", 30, "49-175", "高", "高", "高", "高", "有", "中", "S", "收益最高必做"),
    TaskEntry("挖宝图", 40, "69-129", "中", "中", "中", "中", "低", "中", "B", "产出类, 有时间再做"),
    TaskEntry("跑商", 40, "69-129", "低", "中", "中", "低", "低", "长", "B", "单号效率低"),
    TaskEntry("剧情任务", 0, "0-69", "中", "高", "低", "中", "低", "中", "A", "练号期主力经验"),
    TaskEntry("主线任务", 0, "0-69", "中", "高", "低", "低", "无", "中", "A", "练号必做"),
    TaskEntry("高难度神器", 120, "129-175", "低", "低", "中", "高", "无", "长", "C", "高投入特定做"),
    TaskEntry("多开副本", 90, "109-175", "高", "中", "中", "高", "无", "长", "A", "五开收益高"),
    TaskEntry("摆摊出售", 1, "全部", "中", "无", "中", "无", "无", "短", "A", "变现必做"),
    TaskEntry("清理仓库", 1, "全部", "中", "无", "低", "无", "无", "短", "B", "整理资源"),
    TaskEntry("帮派任务", 30, "69-175", "中", "中", "中", "中", "无", "中", "B", "帮贡收益"),
]


def filter_by_level(level: int, sort: str = "tier") -> List[TaskEntry]:
    usable = [t for t in TASK_DB if level >= t.min_level]
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    sort_map = {"tier": (lambda t: order.get(t.tier, 9)),
                "cash": (lambda t: order.get(t.cash, 9)),
                "item": (lambda t: order.get(t.item, 9))}
    key = sort_map.get(sort, sort_map["tier"])
    usable.sort(key=key)
    return usable


def main() -> None:
    ap = argparse.ArgumentParser(description="任务收益筛选")
    ap.add_argument("--level", type=int, default=109, help="当前等级")
    ap.add_argument("--sort", default="tier", help="排序: tier|cash|item")
    args = ap.parse_args()
    print(f"等级 {args.level} 可做任务(按推荐程度):")
    for t in filter_by_level(args.level, args.sort):
        print(f"  [{t.tier}] {t.name:10s} 满级{t.min_level:3d} 五开{t.wukai} "
              f"经验{t.exp:2s} 现金{t.cash:2s} 物品{t.item:2s} 时{t.time:3s}  {t.reason}")


if __name__ == "__main__":
    main()
