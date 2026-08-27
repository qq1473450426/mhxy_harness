"""tasks 包: 任务系统 (Phase 7)。

任务框架(规格书 §36/§37):
- Task 基类: 生命周期 CREATED->PLANNING->RUNNING->WAITING->COMPLETED
- TaskManager: 注册/调度/生命周期管理
- 师门/抓鬼/封妖 任务状态机
"""
from .base import Task, TaskStatus  # noqa: F401
from .task_manager import TaskManager  # noqa: F401
from .shimen import ShimenTask  # noqa: F401
from .guigua import GuiguaTask  # noqa: F401
from .fengyao import FengyaoTask  # noqa: F401


def register_all(manager: TaskManager) -> None:
    """注册所有内置任务到管理器。"""
    manager.register("shimen", ShimenTask)
    manager.register("guigua", GuiguaTask)
    manager.register("fengyao", FengyaoTask)
