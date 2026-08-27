# -*- coding: utf-8 -*-
"""五开协调器 (Phase 5, 规格书 §11/§14/§49/§50)。

架构:
    Global Planner (core/planner.py)
          |
    Coordinator (本模块)
          |
    Account Agent 1..5 (core/account.py + core/agent.py)

核心职责:
- 按配置创建/启停 5 个账号 Agent
- 绑定各账号窗口
- 维护 TeamState(队长/成员/同步)
- Leader Action -> Wait -> Follower Sync -> State Check -> Next Action
- 队长掉线自动切换备用队长(§13)
- 单个账号异常不影响其他账号继续(§47 人工接管)
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .account import Account
from .agent import GameAgent
from .team import TeamState, TeamStatus
from tasks import TaskManager, register_all

logger = logging.getLogger(__name__)


class Coordinator:
    """多账号协调器。"""

    def __init__(self, settings: Dict[str, Any],
                 ocr_backend: str = "rapidocr",
                 tick_seconds: float = 0.5) -> None:
        self.settings = settings
        self.ocr_backend = ocr_backend
        self.tick = tick_seconds
        self.accounts: Dict[str, Account] = {}
        self.agents: Dict[str, GameAgent] = {}
        self.team = TeamState()
        self.task_manager = TaskManager()
        register_all(self.task_manager)
        self._threads: Dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        # 单账号人工接管(§47): 暂停的账号集合(其他账号继续)
        self._paused: set = set()
        self._manual: set = set()
        self._resume_events: Dict[str, threading.Event] = {}

    # ---------------- 初始化 ----------------
    def build_from_config(self) -> int:
        """按 config.yaml 的 accounts 段创建账号。返回启用数。"""
        acc_cfg_list = self.settings.get("accounts", {}).get("list", [])
        leader_id = self.settings.get("accounts", {}).get("leader", "")
        enabled = [c for c in acc_cfg_list if c.get("enabled", False)]
        if not enabled:
            logger.warning("配置中没有启用账号")
            return 0
        # 按配置顺序建立账号 + 队伍
        for i, cfg in enumerate(enabled):
            acc = Account(cfg, self.settings)
            self.accounts[acc.account_id] = acc
            self.team.add_member(acc.account_id)
            if cfg.get("role") == "leader" or (i == 0 and not leader_id):
                self.team.set_leader(acc.account_id)
                acc.state.role = "leader"
        # 备用队长: 第二个成员
        if len(self.team.members) >= 2:
            self.team.backup_leader = self.team.members[1]
        self.team.task = self.settings.get("tasks", {}).get("default", "")
        logger.info("队伍组建: leader=%s members=%s backup=%s",
                    self.team.leader, self.team.members, self.team.backup_leader)
        return len(enabled)

    # ---------------- 窗口绑定 ----------------
    def bind_windows(self) -> Dict[str, bool]:
        """为所有账号绑定窗口。返回 {账号: 是否成功}。"""
        results = {}
        for acc_id, acc in self.accounts.items():
            results[acc_id] = acc.bind_window()
        # 组队就绪
        online = [i for i, ok in results.items() if ok]
        self.team.members = online or list(self.accounts.keys())
        if self.team.leader not in self.team.members and self.team.members:
            self.team.leader = self.team.members[0]
        self.team.status = TeamStatus.READY if online else TeamStatus.ERROR
        self.team.team_ready = len(online) > 0
        return results

    # ---------------- 任务绑定 ----------------
    def bind_task(self, task_name: str, **params) -> Any:
        """创建队伍任务并返回任务实例。"""
        task = self.task_manager.create(task_name, **params)
        if task is not None:
            self.team.task = task.name
            self.team.shared_goal = task.name + "任务"
        return task

    # ---------------- Agent 创建 ----------------
    def create_agents(self, brain: Optional[Any] = None,
                      tracker: Optional[Any] = None) -> None:
        """为窗口已绑定的账号创建 Agent。"""
        for acc_id, acc in self.accounts.items():
            if acc.win is None:
                continue
            agent = GameAgent(acc, brain=brain, tracker=tracker,
                              ocr_backend=self.ocr_backend,
                              tick_seconds=self.tick)
            self.agents[acc_id] = agent

    # ---------------- 任务绑定 ----------------
    def start(self, goal: str = "", max_steps: Optional[int] = None) -> None:
        """并发启动所有 Agent。"""
        self._stop.clear()
        for acc_id, agent in self.agents.items():
            t = threading.Thread(target=self._run_one,
                                 args=(acc_id, agent, goal, max_steps),
                                 daemon=True, name=f"agent-{acc_id}")
            self._threads[acc_id] = t
            t.start()
        self.team.status = TeamStatus.TASKING

    def _run_one(self, acc_id: str, agent: GameAgent, goal: str,
                 max_steps: Optional[int]) -> None:
        """单个账号的 Agent 循环(线程内)。"""
        try:
            steps = 0
            while not self._stop.is_set():
                if max_steps is not None and steps >= max_steps:
                    break
                # 单账号暂停(§47): 暂停该账号但其他账号继续
                if acc_id in self._paused:
                    ev = self._resume_events.setdefault(acc_id, threading.Event())
                    ev.wait(timeout=0.2)   # 每0.2s检查是否恢复
                    time.sleep(self.tick)
                    continue
                try:
                    result = agent.step(goal)
                    steps += 1
                    # 队长等待同步(§14)
                    if acc_id == self.team.leader:
                        self._sync_wait(agent)
                    else:
                        self.team.mark_synced(acc_id)
                except Exception as e:
                    logger.warning("账号 %s 异常: %s", acc_id, e)
                    agent.account.state.anomaly = True
                    # 队长异常 -> 切换备用队长
                    if acc_id == self.team.leader:
                        self.team.remove_member(acc_id)
                        logger.info("队长 %s 异常, 切换到 %s", acc_id, self.team.leader)
                    break
                time.sleep(self.tick)
        finally:
            agent.running = False

    def _sync_wait(self, agent: GameAgent) -> None:
        """队长动作后等待所有队员同步(§14)。"""
        self.team.mark_synced(self.team.leader)
        # 等待队员(有超时上限, 不无限等)
        deadline = time.time() + 5.0  # 5 秒同步窗口
        while time.time() < deadline:
            if self._stop.is_set() or self.team.all_synced():
                break
            time.sleep(0.1)
        self.team.reset_sync()

    # ---------------- 单账号人工接管(§47) ----------------
    def pause_account(self, account_id: str) -> bool:
        """暂停单个账号(人工接管), 其他账号继续运行。"""
        if account_id not in self.accounts:
            return False
        self._paused.add(account_id)
        self._manual.add(account_id)
        if account_id in self.agents:
            self.agents[account_id].account.state.anomaly = False
            self.agents[account_id].account.state.last_activity = "MANUAL(人工接管)"
        logger.info("账号 %s 切换到人工接管", account_id)
        return True

    def resume_account(self, account_id: str) -> bool:
        """恢复单个账号自动运行。"""
        if account_id not in self.accounts:
            return False
        self._paused.discard(account_id)
        self._manual.discard(account_id)
        ev = self._resume_events.get(account_id)
        if ev is not None:
            ev.set()
        if account_id in self.agents:
            self.agents[account_id].account.state.last_activity = "AUTO(自动)"
        logger.info("账号 %s 恢复自动运行", account_id)
        return True

    def paused_accounts(self) -> list:
        return sorted(self._paused)

    # ---------------- 控制 ----------------
    def stop(self) -> None:
        self._stop.set()
        for t in self._threads.values():
            t.join(timeout=3)
        for acc in self.accounts.values():
            acc.stop()
        self.team.status = TeamStatus.IDLE

    def status(self) -> Dict[str, Any]:
        return {
            "team": self.team.to_dict(),
            "accounts": {aid: acc.to_dict() for aid, acc in self.accounts.items()},
            "agents_running": {aid: ag.running for aid, ag in self.agents.items()},
        }
