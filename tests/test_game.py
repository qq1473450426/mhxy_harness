# -*- coding: utf-8 -*-
"""技术部分B测试: 生命周期/强化学习接口/游戏运行器。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.lifecycle import GameClient, ClientState
from core.rl_env import ProxyGameEnvironment, GameEnvironment
from game_runner import GameRunner


def test_client_state_struct():
    cs = ClientState()
    d = cs.to_dict()
    assert d["phase"] == "idle"
    assert d["running"] is False
    cs.phase = "launching"
    assert cs.to_dict()["phase"] == "launching"


def test_gameclient_dir_exists():
    gc = GameClient()
    assert gc.client_dir == "D:/梦幻西游"
    # 不实际启动客户端, 只验证配置
    assert gc.launcher == "my.exe"


def test_rl_env_interface_abstract():
    # 抽象基类: 方法未实现应抛 NotImplementedError
    env = GameEnvironment()
    # unlock: step 需要 action 参数
    try:
        env.observe()
        assert False, "observe 未实现应抛异常"
    except NotImplementedError:
        pass
    try:
        env.step(None)
        assert False, "step 未实现应抛异常"
    except NotImplementedError:
        pass
    try:
        env.reward()
        assert False, "reward 未实现应抛异常"
    except NotImplementedError:
        pass
    try:
        env.reset()
        assert False, "reset 未实现应抛异常"
    except NotImplementedError:
        pass


def test_rl_env_proxy():
    obs = {"team": {"status": "TASKING"}, "accounts": {}}
    calls = []
    def observe_fn():
        return obs
    def act_fn(action):
        calls.append(action)
        return {"ok": True}
    def reward_fn(o):
        return 10.0
    env = ProxyGameEnvironment(observe_fn, act_fn, reward_fn)
    o1 = env.observe()
    assert o1 == obs
    # step
    nxt, r, done = env.step({"action": "OPEN_TASK"})
    assert len(calls) == 1
    assert r == 10.0
    assert done is False
    # 状态结束判定
    obs["team"]["status"] = "DONE"
    nxt, r, done = env.step({"action": "IDLE"})
    assert done is True


def test_rl_env_done_on_error():
    obs = {"state": {"status": "RECOVERY"}}
    env = ProxyGameEnvironment(lambda: obs, lambda a: {}, None)
    env.observe()
    _, _, done = env.step({})
    assert done is True


def test_game_runner_status_idle():
    runner = GameRunner({"accounts": {"list": []}})
    st = runner.status()
    assert st["phase"] == "idle"
    assert st["running"] is False
    assert "client" in st


def test_game_runner_stop_safe():
    runner = GameRunner({"accounts": {"list": []}})
    runner.stop()
    assert runner._running is False
    assert runner._stop.is_set()
