# -*- coding: utf-8 -*-
"""RL 训练器测试: 验证 Q-learning 收敛及接口。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rl_trainer import GridEnv, QTrainer
from core.rl_env import GameEnvironment, ProxyGameEnvironment


def test_grid_env_step():
    env = GridEnv(size=4, goal=(3, 3))
    s = env.reset()
    assert s == (0, 0)
    ns, r, done = env.step("down")
    assert ns == (1, 0)
    assert done is False


def test_grid_env_goal():
    env = GridEnv(size=4, goal=(3, 3))
    env.pos = (2, 3)
    ns, r, done = env.step("down")
    assert done is True
    assert r == 10.0


def test_grid_env_wall():
    env = GridEnv(size=4, goal=(3, 3))
    env.pos = (0, 0)
    ns, r, done = env.step("up")
    assert ns == (0, 0)
    assert r == -1.0


def test_qtrainer_converges():
    env = GridEnv(size=4, goal=(3, 3))
    trainer = QTrainer(env, episodes=300, epsilon=0.2)
    stats = trainer.train()
    assert stats["success_rate"] > 0.9
    assert stats["q_size"] >= 16


def test_qtrainer_eval_path():
    env = GridEnv(size=4, goal=(3, 3))
    trainer = QTrainer(env, episodes=200, epsilon=0.1)
    trainer.train()
    steps = trainer.evaluate()
    assert steps > 0
    assert steps <= 20


def test_proxy_env_bridge_real_agent():
    obs = {"team": {"status": "TASKING"}, "accounts": {"acc1": {"state": "CITY"}}}
    def observe_fn():
        return obs
    def act_fn(action):
        return {"ok": True, "action": action}
    def reward_fn(o):
        return 1.0 if o.get("team", {}).get("status") == "TASKING" else 0.0
    env = ProxyGameEnvironment(observe_fn, act_fn, reward_fn)
    o = env.observe()
    assert o == obs
    nxt, r, done = env.step({"action": "OPEN_TASK"})
    assert r == 1.0
    assert done is False


def test_grid_env_extends_interface():
    env = GridEnv()
    assert isinstance(env, GameEnvironment)
    assert env.observe() is not None
    assert env.reset() is not None
    assert callable(env.step)
    assert callable(env.reward)
