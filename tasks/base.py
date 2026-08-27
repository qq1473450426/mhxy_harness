# -*- coding: utf-8 -*-
"""任务抽象基类 (规格书 §36/§37)。

Task 生命周期:
    CREATED -> PLANNING -> RUNNING -> WAITING -> COMPLETED
异常: RUNNING -> FAILED -> RECOVERY -> PLANNING

任务子类实现 step(gs) 返回动作描述, 由外部 Agent 执行。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERY = "RECOVERY"


@dataclass
class Task:
    """通用任务抽象(所有任务继承)。"""

    name: str
    priority: int = 10
    max_runtime: int = 3600
    status: TaskStatus = TaskStatus.CREATED
    params: Dict[str, Any] = field(default_factory=dict)
    _started_at: float = field(default_factory=time.time, repr=False)
    _progress: int = 0
    _total: int = 0
    _errors: List[str] = field(default_factory=list)

    def plan(self) -> None:
        self.status = TaskStatus.PLANNING

    def start(self) -> None:
        self._started_at = time.time()
        self.status = TaskStatus.RUNNING

    def wait(self) -> None:
        self.status = TaskStatus.WAITING

    def complete(self) -> None:
        self._progress = self._total
        self.status = TaskStatus.COMPLETED

    def fail(self, reason: str = "") -> None:
        self.status = TaskStatus.FAILED
        if reason:
            self._errors.append(reason)
        self.params["fail_reason"] = reason

    def recover(self) -> None:
        self.status = TaskStatus.PLANNING

    @property
    def progress(self) -> float:
        if self._total <= 0:
            return 0.0
        return min(1.0, self._progress / self._total)

    @property
    def elapsed(self) -> float:
        return time.time() - self._started_at

    @property
    def timed_out(self) -> bool:
        return self.elapsed > self.max_runtime

    def set_progress(self, done: int, total: int) -> None:
        self._progress = done
        self._total = total

    def step(self, gs: Any) -> Dict[str, Any]:
        """子类实现: 根据游戏状态推进任务。返回动作描述。"""
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority,
            "status": self.status.value,
            "progress": round(self.progress, 2),
            "done": self._progress, "total": self._total,
            "elapsed": round(self.elapsed, 1),
            "errors": list(self._errors[-3:]),
            "params": dict(self.params),
        }
