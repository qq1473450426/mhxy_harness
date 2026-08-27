# -*- coding: utf-8 -*-
"""强化学习接口 (规格书 §25)。

预留 RL Environment:
    observe() -> 观测(当前状态/截图特征)
    step(action) -> 执行动作返回 (next_state, reward, done)
    reward()    -> 奖励计算

当前阶段不训练 RL, 先提供可靠接口, 未来可训练:
    Movement Policy / Battle Policy / Task Policy
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class GameEnvironment:
    """强化学习环境接口(抽象基类)。"""

    def observe(self) -> Any:
        """返回当前观测(状态向量/截图特征)。"""
        raise NotImplementedError

    def step(self, action: Any) -> Tuple[Any, float, bool]:
        """执行动作, 返回 (next_obs, reward, done)。"""
        raise NotImplementedError

    def reward(self) -> float:
        """计算当前奖励。"""
        raise NotImplementedError

    def reset(self) -> Any:
        """重置环境, 返回初始观测。"""
        raise NotImplementedError

    def render(self) -> Optional[Any]:
        """渲染(可选)。"""
        return None


class ProxyGameEnvironment(GameEnvironment):
    """代理环境: 把真实 Agent 的观察/动作桥接成 RL 接口。

    通过回调桥接:
        - observe_fn() -> 当前 GameState dict
        - act_fn(action_dict) -> 执行结果
        - reward_fn(state, action, result) -> 奖励

    这样未来可以用同一个接口训练策略, 无需改动 Agent 核心。
    """

    def __init__(self, observe_fn, act_fn, reward_fn=None) -> None:
        self.observe_fn = observe_fn
        self.act_fn = act_fn
        self.reward_fn = reward_fn
        self._last_obs: Any = None
        self._last_reward = 0.0

    def observe(self) -> Any:
        self._last_obs = self.observe_fn()
        return self._last_obs

    def step(self, action: Any) -> Tuple[Any, float, bool]:
        result = self.act_fn(action)
        next_obs = self.observe_fn()
        r = self.reward() if self.reward_fn else 0.0
        done = self._is_done(next_obs)
        return next_obs, r, done

    def reward(self) -> float:
        if self.reward_fn and self._last_obs is not None:
            self._last_reward = float(self.reward_fn(self._last_obs))
        return self._last_reward

    def reset(self) -> Any:
        self._last_obs = None
        return self.observe()

    def _is_done(self, obs: Any) -> bool:
        """判断是否结束(任务完成/异常)。兼容多种观测结构。"""
        try:
            if not isinstance(obs, dict):
                return False
            # 结构1: {"state": {"status": ...}}
            state = obs.get("state", {})
            status = state.get("status") if isinstance(state, dict) else ""
            if not status:
                # 结构2: {"team": {"status": ...}} (GameRunner 观测)
                team = obs.get("team", {})
                status = team.get("status") if isinstance(team, dict) else ""
            if not status:
                # 结构3: 直接 status 字段
                status = obs.get("status", "")
            return status in ("DONE", "RECOVERY", "FAILED")
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {"last_reward": round(self._last_reward, 3),
                "last_obs": self._last_obs if not isinstance(self._last_obs, bytes) else "<bytes>"}
