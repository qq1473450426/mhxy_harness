# -*- coding: utf-8 -*-
"""Phase 4 测试: 坐标解析器 + 师门任务状态机 + 执行器。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resolver import CoordinateResolver, ResolveError
from core.executor import Executor
from core.brain import Decision
from core.game_state import GameState, GameStatus
from automation.input_driver import ActionResult
from tasks.shimen import ShimenTask, ShimenPhase


def test_resolver_from_ocr():
    r = CoordinateResolver()
    r.update_context([("师门师父", 300, 200), ("长安城", 10, 10)])
    pos = r.resolve("师门师父")
    assert pos[0] > 300  # 文本中心在起始位置右侧
    assert pos[1] == 208


def test_resolver_from_elements():
    r = CoordinateResolver()
    r.update_context([], {"task_btn": {"x": 100, "y": 200, "w": 40, "h": 20, "label": "task_btn"}})
    pos = r.resolve("task_btn")
    assert pos == (120, 210)


def test_resolver_alias_and_fixed():
    r = CoordinateResolver(fixed_ui={"钟馗": (400, 300)})
    assert r.resolve("钟馗") == (400, 300)
    assert r.resolve("任务") == (600, 200)


def test_resolver_unknown_raises():
    r = CoordinateResolver()
    try:
        r.resolve("不存在的东西")
        assert False, "应抛出 ResolveError"
    except ResolveError:
        pass


def test_executor_press_key():
    class FakeDriver:
        def __init__(self):
            self.calls = []
        def exec(self, action):
            self.calls.append((action.type, action.key))
            return ActionResult(True, "ok")
    d = FakeDriver()
    ex = Executor(driver=d, max_retry=1)
    r = ex.execute(Decision("OPEN_TASK", reason="打开"))
    assert r.ok
    assert ("PRESS", "alt+q") in d.calls


def test_executor_click_with_resolver():
    class FakeDriver:
        def __init__(self):
            self.calls = []
        def exec(self, action):
            self.calls.append((action.type, action.x, action.y))
            return ActionResult(True, "ok")
    d = FakeDriver()
    ex = Executor(driver=d, max_retry=1)
    ex.resolver.update_context([("钟馗", 400, 300)])
    r = ex.execute(Decision("CLICK_NPC", target="钟馗"))
    assert r.ok
    assert d.calls[0][0] == "CLICK"
    assert d.calls[0][1] > 400


def test_shimen_flow_to_submit():
    t = ShimenTask(max_rounds=20)
    calls = {"get": 0, "run": 0, "interact": 0, "submit": 0, "verify": 0}
    def hook(name):
        def fn(*a, **k):
            calls[name] += 1
            return True
        return fn
    t.bind(get_task=hook("get"), run=hook("run"), interact=hook("interact"),
           submit=hook("submit"), verify=hook("verify"))

    # INIT -> GET_TASK(打开面板)
    gs = GameState(account_id="t", status=GameStatus.CITY, map_name="长安城")
    a = t.step(gs)
    assert a["action"] == "OPEN_TASK"

    # 面板出现任务 -> RUN
    gs2 = GameState(account_id="t", status=GameStatus.TASK_DIALOG, task_name="师门任务")
    a = t.step(gs2)
    assert a["action"] == "NAVIGATE"

    # 对话框 -> INTERACT
    gs3 = GameState(account_id="t", status=GameStatus.NPC_DIALOG, dialogue_open=True)
    a = t.step(gs3)
    assert a["action"] == "DIALOG_CHOICE"

    # 任务完成 -> SUBMIT
    gs4 = GameState(account_id="t", status=GameStatus.TASK_DIALOG,
                    dialog_text="任务完成，找师父交报告去")
    a = t.step(gs4)
    assert a["action"] == "SUBMIT_TASK"
    assert t.state.current_round == 1


def test_shimen_stuck_detection():
    t = ShimenTask()
    gs = GameState(account_id="t", status=GameStatus.CITY)
    for _ in range(8):
        a = t.step(gs)
        if a["action"] == "RECOVERY":
            break
    assert t.state.phase == ShimenPhase.RECOVERY
    assert a["action"] == "RECOVERY"
