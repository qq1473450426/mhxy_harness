# -*- coding: utf-8 -*-
"""自主游戏编排器: 启动->登录监控->任务执行->结束->优化。

完整闭环:
    GameClient.launch()
    -> monitor()(等待窗口/登录)
    -> Coordinator(五开) 执行任务
    -> RL env 记录(优化用)
    -> GameClient.shutdown()

运行在后台线程, 由 WebUI 的 /api/control 控制启停。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from automation.lifecycle import GameClient
from core.coordinator import Coordinator
from core.rl_env import ProxyGameEnvironment

logger = logging.getLogger(__name__)


class GameRunner:
    """自主游戏运行器。"""

    def __init__(self, settings: Dict[str, Any], dry_run: bool = False) -> None:
        self.settings = settings
        self.dry_run = dry_run
        self.client = GameClient()
        self.coordinator: Optional[Coordinator] = None
        self.rl_env: Optional[ProxyGameEnvironment] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False
        self._phase = "idle"
        self._last_status: Dict[str, Any] = {}
        self._last_optimize: Dict[str, Any] = {}
        self._battle_monitor = None
        self._battle_stats: Dict[str, Any] = {}

    # ---------------- 控制 ----------------
    def start(self, task: str = "shimen", goal: str = "", auto: bool = True) -> bool:
        """启动自主游戏闭环(后台线程)。"""
        if self._running:
            logger.warning("已在运行")
            return False
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run,
                                       args=(task, goal, auto), daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """停止运行(安全结束)。"""
        self._stop.set()
        self._running = False

    # ---------------- 主循环 ----------------
    def _run(self, task: str, goal: str, auto: bool) -> None:
        try:
            # dry_run: 不启动真实客户端(测试/演示用)
            if self.dry_run:
                self._phase = "running"
                logger.info("[runner] dry_run 模式: 跳过客户端启动, 仅演示编排")
                self._last_status["client"] = {"phase": "dry_run", "running": False}
                # 仍组装五开协调器演示
                self.coordinator = Coordinator(self.settings)
                self.coordinator.build_from_config()
                self.rl_env = self._build_rl_env()
            else:
                self._phase = "launching"
                logger.info("[runner] 启动客户端...")
                ok = self.client.launch()
                if not ok:
                    self._phase = "error"
                    return
                # 监控登录(等待窗口)
                self._phase = "login"
                logger.info("[runner] 等待游戏窗口/登录...")
                st = self.client.monitor(timeout=120)
                self._last_status["client"] = st
                if st["phase"] not in ("in_game", "login"):
                    self._phase = "error:" + st.get("phase", "?")
                    return
            # 五开协调器
            self._phase = "team"
            logger.info("[runner] 组建五开队伍...")
            self.coordinator = Coordinator(self.settings)
            self.coordinator.build_from_config()
            self.coordinator.bind_windows()
            self.coordinator.create_agents()
            task_obj = self.coordinator.bind_task(task)
            if task_obj is not None:
                logger.info("[runner] 任务: %s", task_obj.name)
            # RL 环境桥接
            self.rl_env = self._build_rl_env()
            self._phase = "running"
            logger.info("[runner] 开始执行任务: %s (auto=%s)", task, auto)
            if auto:
                goal = goal or task
                self.coordinator.start(goal=goal, max_steps=0)
            # 等待停止
            while not self._stop.is_set():
                st = self.coordinator.status()
                self._last_status["team"] = st["team"]
                self._last_status["accounts"] = st["accounts"]
                time.sleep(1.0)
        except Exception as e:
            logger.error("[runner] 运行异常: %s", e)
            self._phase = "error:" + str(e)[:80]
        finally:
            self._phase = "stopping"
            if self.coordinator is not None:
                self.coordinator.stop()
            # 记录结束(可选关闭客户端)
            if self._stop.is_set() and auto:
                self._phase = "stopped"
            else:
                self._phase = "idle"
            self._running = False

    def _build_rl_env(self) -> ProxyGameEnvironment:
        """把协调器/Agent 桥接成 RL 环境。"""
        coord = self.coordinator
        def observe_fn():
            return {"team": coord.team.to_dict(),
                    "accounts": {aid: a.to_dict() for aid, a in coord.accounts.items()}}
        def act_fn(action):
            """首账号执行一次动作(只执行一次, 避免副作用)。"""
            acc_id = coord.team.leader
            agent = coord.agents.get(acc_id)
            if agent is None:
                return {"ok": False}
            from core.brain import Decision
            if isinstance(action, dict):
                d = Decision(action=action.get("action", "IDLE"),
                             target=action.get("target", ""),
                             confidence=float(action.get("confidence", 0.9)))
                try:
                    gs = agent.observe()
                    ar = agent.act(d, gs)
                    return {"ok": bool(ar.ok), "desc": ar.desc, "error": ar.error}
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            return {"ok": False}
        def reward_fn(obs):
            # 基础奖励: 任务进度或存活
            try:
                team = obs.get("team", {})
                return 1.0 if team.get("status") == "TASKING" else 0.0
            except Exception:
                return 0.0
        return ProxyGameEnvironment(observe_fn, act_fn, reward_fn)

    # ---------------- 战斗监控(遇怪自动打) ----------------
    def init_battle_monitor(self) -> bool:
        """初始化战斗监控器(真实模式绑定窗口后调用)。"""
        try:
            from core.battle_monitor import BattleMonitor
            self._battle_monitor = BattleMonitor(self.client.state.window_hwnd) if False else None
            # 用协调器首账号的窗口
            for acc_id, agent in self.coordinator.agents.items():
                if agent.account.win is not None:
                    self._battle_monitor = BattleMonitor(agent.account.win)
                    break
            return self._battle_monitor is not None
        except Exception as e:
            logger.warning("战斗监控初始化失败: %s", e)
            return False

    def handle_battle(self) -> Dict[str, Any]:
        """遇怪自动战斗: 若当前战斗, 用 BattleMonitor 处理到结束。"""
        if self._battle_monitor is None:
            return {"battled": False, "reason": "未初始化"}
        r = self._battle_monitor.monitor_once(max_wait=150.0)
        self._battle_stats = r
        return r

    # ---------------- 单账号人工接管(§47) ----------------
    def pause_account(self, account_id: str) -> bool:
        """暂停单账号(人工接管), 转发到 coordinator。"""
        if self.coordinator is not None:
            return self.coordinator.pause_account(account_id)
        return False

    def resume_account(self, account_id: str) -> bool:
        """恢复单账号, 转发到 coordinator。"""
        if self.coordinator is not None:
            return self.coordinator.resume_account(account_id)
        return False

    def paused_accounts(self) -> list:
        if self.coordinator is not None:
            return self.coordinator.paused_accounts()
        return []

    # ---------------- 强化学习优化(§25 "优化"环节) ----------------
    def optimize(self, episodes: int = 300) -> Dict[str, Any]:
        """在模拟环境上训练一个策略作为演示, 返回训练统计。

        真实场景: 将历史 Replay/决策记录喂给 RL, 训练移动/战斗/任务策略。
        """
        try:
            from core.rl_trainer import GridEnv, QTrainer
            env = GridEnv(size=4, goal=(3, 3))
            trainer = QTrainer(env, episodes=episodes, epsilon=0.2)
            stats = trainer.train()
            steps = trainer.evaluate()
            stats["opt_steps"] = steps
            self._last_optimize = stats
            logger.info("[runner] RL 优化完成: %s", stats)
            return stats
        except Exception as e:
            logger.warning("[runner] RL 优化失败: %s", e)
            return {"error": str(e)}

    # ---------------- 状态 ----------------
    def status(self) -> Dict[str, Any]:
        client_state = self.client.to_dict()
        if self.dry_run:
            client_state["phase"] = "dry_run"
        return {
            "phase": self._phase,
            "running": self._running,
            "dry_run": self.dry_run,
            "client": client_state,
            **self._last_status,
            "rl": self.rl_env.to_dict() if self.rl_env else {},
            "optimize": self._last_optimize,
            "paused": self.paused_accounts(),
            "battle": self._battle_stats,
        }
