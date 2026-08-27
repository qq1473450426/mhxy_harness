# -*- coding: utf-8 -*-
"""Phase 7 测试: 任务生命周期/管理器/抓鬼/封妖。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base import Task, TaskStatus
from tasks.task_manager import TaskManager
from tasks.guigua import GuiguaTask, GuiguaPhase
from tasks.fengyao import FengyaoTask, FengyaoPhase
from tasks.shimen import ShimenTask
from core.game_state import GameState, GameStatus


def test_task_lifecycle():
    """§37: CREATED->PLANNING->RUNNING->COMPLETED。"""
    t = Task(name="测试")
    assert t.status == TaskStatus.CREATED
    t.plan()
    assert t.status == TaskStatus.PLANNING
    t.start()
    assert t.status == TaskStatus.RUNNING
    t.set_progress(5, 10)
    assert t.progress == 0.5
    t.complete()
    assert t.status == TaskStatus.COMPLETED
    assert t.progress == 1.0


def test_task_fail_recover():
    t = Task(name="测试")
    t.start()
    t.fail("出错了")
    assert t.status == TaskStatus.FAILED
    assert t.params.get("fail_reason") == "出错了"
    t.recover()
    assert t.status == TaskStatus.PLANNING


def test_task_timeout():
    t = Task(name="测试", max_runtime=1)
    t.start()
    import time
    time.sleep(1.1)
    assert t.timed_out


def test_task_manager_register_create():
    m = TaskManager()
    m.register("shimen", ShimenTask)
    m.register("guigua", GuiguaTask)
    assert m.available == ["guigua", "shimen"]
    t = m.create("shimen", max_rounds=20)
    assert t is not None
    assert t.status == TaskStatus.PLANNING
    # 未知任务
    assert m.create("不存在") is None


def test_task_manager_priority():
    m = TaskManager()
    m.register("a", ShimenTask)
    m.register("b", GuiguaTask)
    t1 = m.create("a")
    t2 = m.create("b")
    t1.priority = 5
    t2.priority = 1   # 更高优先级(小数字优先)
    assert m.next_task() == t2


def test_task_manager_run_next():
    m = TaskManager()
    m.register("shimen", ShimenTask)
    t = m.create("shimen", max_rounds=20)
    gs = GameState(account_id="t", status=GameStatus.CITY, map_name="长安城")
    action = m.run_next(gs)
    assert action is not None
    assert "action" in action


def test_guigua_flow():
    t = GuiguaTask(max_rounds=3)
    gs = GameState(account_id="t", status=GameStatus.CITY, map_name="长安城")
    # INIT -> TEAM
    a = t.step(gs)
    assert a["action"] == "JOIN_TEAM"
    # 队伍就绪 -> GET_TASK
    gs2 = GameState(account_id="t", status=GameStatus.TEAM, team_members=5)
    a = t.step(gs2)
    assert a["action"] == "NAVIGATE"
    assert a.get("target") == "钟馗"
    # 接任务 -> RUN
    gs3 = GameState(account_id="t", status=GameStatus.NPC_DIALOG,
                    dialog_text="钟馗：捉鬼除妖")
    a = t.step(gs3)
    assert a["action"] == "NAVIGATE"
    assert t.state.current_round == 1


def test_guigua_battle_and_complete():
    t = GuiguaTask(max_rounds=2)
    # 战斗 -> 结束 -> 提交 -> 验证
    gs_b = GameState(account_id="t", status=GameStatus.BATTLE, in_battle=True)
    a = t.step(gs_b)
    assert a["action"] == "BATTLE_AUTO"
    # 战斗结束
    gs_after = GameState(account_id="t", status=GameStatus.CITY, map_name="长安城")
    a = t.step(gs_after)
    assert a["action"] == "SUBMIT_TASK"


def test_fengyao_complete():
    t = FengyaoTask(target=2)
    gs = GameState(account_id="t", status=GameStatus.TEAM, team_members=5)
    t.step(gs)  # TEAM->RUN
    # 战斗两轮
    for _ in range(2):
        gs_b = GameState(account_id="t", status=GameStatus.BATTLE, in_battle=True)
        a = t.step(gs_b)
        assert a["action"] == "BATTLE_AUTO"
        gs_after = GameState(account_id="t", status=GameStatus.CITY)
        a = t.step(gs_after)
    assert t.state.cleared == 2
    # 再一步: VERIFY -> DONE + complete
    gs_final = GameState(account_id="t", status=GameStatus.CITY)
    a = t.step(gs_final)
    assert t.status == TaskStatus.COMPLETED
    assert a["action"] == "DONE"


def test_shimen_extends_task():
    t = ShimenTask(max_rounds=3)
    assert isinstance(t, Task)
    assert t.name == "师门"
    assert t.status == TaskStatus.CREATED
