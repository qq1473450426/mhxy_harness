# -*- coding: utf-8 -*-
"""强化学习训练器 (规格书 §25, 自主游戏"优化"环节)。

用 ProxyGameEnvironment 桥接训练环境, 跑 Q-learning 验证接口真实可用。

训练环境(简单网格):
    状态: (x, y) 网格位置
    动作: 上/下/左/右/停
    目标: 到达终点格(奖励 +10), 每步 -0.1(步长惩罚), 撞墙 -1

Q-learning: 走几步后就能学会直接走向终点。
"""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .rl_env import GameEnvironment, ProxyGameEnvironment

logger = logging.getLogger(__name__)


class GridEnv(GameEnvironment):
    """简单网格环境: 从(0,0)走到(3,3)。"""

    ACTIONS = ["up", "down", "left", "right", "stop"]

    def __init__(self, size: int = 4, goal: Tuple[int, int] = (3, 3)) -> None:
        self.size = size
        self.goal = goal
        self.pos: Tuple[int, int] = (0, 0)
        self.steps = 0
        self.max_steps = 50

    def reset(self) -> Tuple[int, int]:
        self.pos = (0, 0)
        self.steps = 0
        return self.pos

    def observe(self) -> Tuple[int, int]:
        return self.pos

    def step(self, action: Any) -> Tuple[Tuple[int, int], float, bool]:
        """执行动作, 返回 (next_state, reward, done)。"""
        self.steps += 1
        x, y = self.pos
        # 约定: down=向下(row+1), up=向上(row-1), right=向右(col+1), left=向左(col-1)
        if action == "up":
            x = max(0, x - 1)
        elif action == "down":
            x = min(self.size - 1, x + 1)
        elif action == "left":
            y = max(0, y - 1)
        elif action == "right":
            y = min(self.size - 1, y + 1)
        # 撞墙(位置没变但想动) -> 惩罚
        moved = (x, y) != self.pos
        self.pos = (x, y)
        reward = 0.0
        if self.pos == self.goal:
            reward = 10.0
            return self.pos, reward, True
        reward = -0.1 if moved else -1.0   # 步长惩罚 / 撞墙惩罚
        if self.steps >= self.max_steps:
            return self.pos, reward, True
        return self.pos, reward, False

    def reward(self) -> float:
        return 0.0

    def render(self) -> Optional[str]:
        grid = [["."] * self.size for _ in range(self.size)]
        grid[self.goal[0]][self.goal[1]] = "G"
        grid[self.pos[0]][self.pos[1]] = "A"
        return "\n".join("".join(r) for r in grid)

    # 代理需要的接口
    @property
    def n_actions(self) -> int:
        return len(self.ACTIONS)

    @property
    def action_space(self) -> List[str]:
        return self.ACTIONS

    def encode_state(self, pos: Tuple[int, int]) -> int:
        return pos[0] * self.size + pos[1]

    def decode_action(self, idx: int) -> str:
        return self.ACTIONS[idx % len(self.ACTIONS)]


class QTrainer:
    """Q-learning 训练器: 在 GridEnv 上训练, 验证 RL 接口可用。"""

    def __init__(self, env: GridEnv, alpha: float = 0.2, gamma: float = 0.9,
                 epsilon: float = 0.2, episodes: int = 200) -> None:
        self.env = env
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.episodes = episodes
        self.Q: Dict[int, List[float]] = defaultdict(lambda: [0.0] * env.n_actions)

    def _select_action(self, state: int, explore: bool = True) -> str:
        if explore and random.random() < self.epsilon:
            return self.env.decode_action(random.randrange(self.env.n_actions))
        q = self.Q[state]
        return self.env.decode_action(q.index(max(q)))

    def train(self) -> Dict[str, Any]:
        """训练 n 个 episode, 返回统计。"""
        total_rewards = []
        success = 0
        for ep in range(self.episodes):
            state = self.env.encode_state(self.env.reset())
            total_r = 0.0
            done = False
            while not done:
                action = self._select_action(state)
                next_pos, reward, done = self.env.step(action)
                next_state = self.env.encode_state(next_pos)
                # Q 更新
                best_next = max(self.Q[next_state])
                self.Q[state][self.env.ACTIONS.index(action)] += self.alpha * (
                    reward + self.gamma * best_next - self.Q[state][self.env.ACTIONS.index(action)])
                state = next_state
                total_r += reward
            total_rewards.append(total_r)
            if self.env.pos == self.env.goal:
                success += 1
        return {
            "episodes": self.episodes,
            "avg_reward": round(sum(total_rewards) / len(total_rewards), 2),
            "last_reward": round(total_rewards[-1], 2),
            "success_rate": round(success / self.episodes, 3),
            "q_size": len(self.Q),
        }

    def evaluate(self) -> float:
        """用学到的最优策略(不探索)走一次, 返回步数。"""
        state = self.env.encode_state(self.env.reset())
        done = False
        steps = 0
        while not done and steps < 50:
            action = self._select_action(state, explore=False)
            next_pos, _, done = self.env.step(action)
            state = self.env.encode_state(next_pos)
            steps += 1
        return steps

    def policy_summary(self) -> Dict[str, str]:
        """打印每个状态的策略方向。"""
        result = {}
        for state, q in self.Q.items():
            best = self.env.decode_action(q.index(max(q)))
            x, y = state // self.env.size, state % self.env.size
            result[f"({x},{y})"] = best
        return result
