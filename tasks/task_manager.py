# -*- coding: utf-8 -*-
"""任务管理器 (Phase 7, 规格书 §36/§37)。

- 任务注册表: 名称 -> 任务类
- 调度: 按优先级选择下一个任务
- 生命周期管理: CREATED->PLANNING->RUNNING->WAITING->COMPLETED
- 异常处理: FAILED->RECOVERY->PLANNING
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from .base import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器。"""

    def __init__(self) -> None:
        self._registry: Dict[str, Type[Task]] = {}
        self._tasks: Dict[str, Task] = {}
        self._order: List[str] = []

    # ---------------- 注册 ----------------
    def register(self, name: str, task_cls: Type[Task]) -> None:
        """注册任务类。"""
        self._registry[name] = task_cls
        logger.info("任务注册: %s", name)

    def unregister(self, name: str) -> None:
        self._registry.pop(name, None)

    @property
    def available(self) -> List[str]:
        return sorted(self._registry.keys())

    # ---------------- 创建 ----------------
    def create(self, name: str, **params) -> Optional[Task]:
        """创建任务实例(按注册表)。"""
        cls = self._registry.get(name)
        if cls is None:
            logger.warning("未知任务: %s (可用: %s)", name, self.available)
            return None
        task = cls(**params)
        tid = f"{name}-{len(self._tasks)+1}"
        self._tasks[tid] = task
        self._order.append(tid)
        task.plan()
        return task

    # ---------------- 调度 ----------------
    def next_task(self) -> Optional[Task]:
        """按优先级选下一个可运行任务。"""
        candidates = [t for t in self._tasks.values()
                      if t.status in (TaskStatus.PLANNING, TaskStatus.CREATED)]
        if not candidates:
            return None
        return min(candidates, key=lambda t: t.priority)

    def run_next(self, gs: Any) -> Optional[Dict[str, Any]]:
        """运行下一个待执行任务的一步。返回动作描述。"""
        task = self.next_task()
        if task is None:
            return None
        if task.status == TaskStatus.PLANNING:
            task.start()
        try:
            action = task.step(gs)
        except NotImplementedError:
            task.fail("step 未实现")
            return {"action": "RECOVERY", "reason": f"{task.name} 未实现"}
        except Exception as e:
            logger.warning("任务 %s 异常: %s", task.name, e)
            task.fail(str(e))
            task.recover()
            return {"action": "RECOVERY", "reason": f"{task.name}: {e}"}
        # 超时保护
        if task.timed_out:
            task.fail("超时")
            task.recover()
            return {"action": "RECOVERY", "reason": f"{task.name} 超时"}
        return action

    # ---------------- 状态 ----------------
    def status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
        }

    def get(self, name: str) -> Optional[Task]:
        for t in self._tasks.values():
            if t.name == name:
                return t
        return None
