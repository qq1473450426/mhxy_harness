# -*- coding: utf-8 -*-
"""自主游戏编排器：支持真实窗口附着、自动执行和单步执行。"""
from __future__ import annotations
import logging, threading, time
from typing import Any, Dict, Optional
from automation.lifecycle import GameClient
from automation.window import WindowInfo
from core.coordinator import Coordinator
from core.rl_env import ProxyGameEnvironment
logger = logging.getLogger(__name__)

class GameRunner:
    def __init__(self, settings: Dict[str, Any], dry_run: bool = False) -> None:
        self.settings=settings; self.dry_run=dry_run; self.client=GameClient()
        self.coordinator: Optional[Coordinator]=None; self.rl_env=None
        self._thread=None; self._stop=threading.Event(); self._running=False; self._phase="idle"
        self._last_status={}; self._last_optimize={}; self._battle_monitor=None; self._battle_stats={}
    def start(self, task="shimen", goal="", auto=True):
        if self._running: return False
        self._stop.clear(); self._running=True
        self._thread=threading.Thread(target=self._run,args=(task,goal,auto),daemon=True); self._thread.start(); return True
    def start_attached(self, win: WindowInfo, task="shimen", goal="", auto=True):
        """同步完成窗口附着和 Agent 初始化，再启动后台循环。

        旧实现把 _prepare_coordinator 放在线程里，UI 点击后立即执行“单步”时可能
        看到 coordinator 已创建但 agents 尚未创建，造成“没有可执行的队长 Agent”。
        """
        if self._running or win is None or not win.is_valid(): return False
        try:
            self._stop.clear()
            self._phase="attaching"
            self.client.state.window_hwnd=win.hwnd
            self.client.state.window_title=win.title
            self.client.state.running=True
            self.client.state.phase="in_game"
            self.coordinator=self._prepare_coordinator(win,task)
            leader=self.coordinator.team.leader
            if not leader or leader not in self.coordinator.agents:
                self.coordinator=None
                self._phase="error:no_leader_agent"
                return False
            self._last_status=self.coordinator.status()
            self._running=True
            self._thread=threading.Thread(target=self._run_attached,args=(win,task,goal,auto),daemon=True)
            self._thread.start()
            return True
        except Exception as exc:
            logger.exception("attached initialization failed")
            self._phase="error:"+str(exc)[:120]
            self._running=False
            return False
    def step_attached(self, win: WindowInfo, task="shimen", goal=""):
        """在已绑定真实窗口上只执行一个 Agent step，便于观察和调试。"""
        if win is None or not win.is_valid():
            return {"ok": False, "error": "窗口无效"}
        try:
            if self._running:
                return {"ok": False, "error": "自动任务正在运行，请先停止后再执行单步"}
            if self.coordinator is None:
                self.coordinator = self._prepare_coordinator(win, task)
                self._phase = "attached_step"
            agent = self.coordinator.agents.get(self.coordinator.team.leader)
            if agent is None:
                return {"ok": False, "error": "没有可执行的队长 Agent，请重新绑定窗口"}
            result = agent.step(goal or task)
            self._last_status = self.coordinator.status()
            return {"ok": True, "result": result}
        except Exception as exc:
            logger.exception("single step failed")
            return {"ok": False, "error": str(exc)}
    def stop(self):
        self._stop.set()
        if self.coordinator is not None: self.coordinator.stop()
        self._running=False
    def _prepare_coordinator(self, win=None, task_name: str = ""):
        c=Coordinator(self.settings,ocr_backend=self.settings.get("vision",{}).get("ocr_backend","rapidocr"),tick_seconds=float(self.settings.get("automation",{}).get("tick_seconds",0.5)))
        c.build_from_config()
        if win is None:
            c.bind_windows()
        else:
            leader=c.team.leader
            if not leader and c.accounts:
                leader=next(iter(c.accounts))
                c.team.set_leader(leader)
            if leader and leader in c.accounts:
                acc=c.accounts[leader]; acc.win=win; acc.state.hwnd=win.hwnd; acc.state.win_rect=win.rect
                from automation.input_driver import InputDriver
                inp=self.settings.get("input",{})
                acc.driver=InputDriver(win,backend=inp.get("backend","win32"),failsafe=bool(inp.get("failsafe",True)),move_duration=float(inp.get("move_duration",0.08)))
            c.team.members=[leader] if leader else []; c.team.team_ready=bool(c.team.members)
        if task_name:
            bound=c.bind_task(task_name)
            if bound is None: raise RuntimeError(f"无法绑定任务: {task_name}")
        c.create_agents()
        return c
    def _run_attached(self,win,task,goal,auto):
        try:
            self._phase="attached"; self.client.state.window_hwnd=win.hwnd; self.client.state.window_title=win.title; self.client.state.running=True; self.client.state.phase="in_game"
            if self.coordinator is None:
                self.coordinator=self._prepare_coordinator(win,task)
            self._phase="team"; self.rl_env=self._build_rl_env(); self._phase="running"
            if auto: self.coordinator.start(goal=goal or task,max_steps=None)
            while not self._stop.is_set(): self._last_status=self.coordinator.status(); time.sleep(0.5)
        except Exception as exc:
            logger.exception("attached runner error"); self._phase="error:"+str(exc)[:120]
        finally:
            if self.coordinator is not None: self.coordinator.stop()
            self._phase="stopped" if self._stop.is_set() else "idle"; self._running=False
    def _run(self,task,goal,auto):
        try:
            if self.dry_run:
                self.coordinator=self._prepare_coordinator(task_name=task); self._phase="running"
            else:
                self._phase="launching"; self.client.launch(); self._phase="login"; st=self.client.monitor(timeout=120); self._last_status["client"]=st
                if st["phase"] not in ("in_game","login"): self._phase="error:"+st.get("phase","?"); return
                self.coordinator=self._prepare_coordinator(task_name=task)
            self._phase="team"; self.rl_env=self._build_rl_env(); self._phase="running"
            if auto: self.coordinator.start(goal=goal or task,max_steps=None)
            while not self._stop.is_set(): self._last_status=self.coordinator.status(); time.sleep(1.0)
        except Exception as exc:
            logger.exception("runner error"); self._phase="error:"+str(exc)[:120]
        finally:
            if self.coordinator is not None: self.coordinator.stop()
            self._phase="stopped" if self._stop.is_set() else "idle"; self._running=False
    def _build_rl_env(self):
        coord=self.coordinator
        def observe_fn(): return {"team":coord.team.to_dict(),"accounts":{aid:a.to_dict() for aid,a in coord.accounts.items()}}
        def act_fn(action):
            agent=coord.agents.get(coord.team.leader)
            if agent is None or not isinstance(action,dict): return {"ok":False}
            from core.brain import Decision
            d=Decision(action=action.get("action","IDLE"),target=action.get("target",""),confidence=float(action.get("confidence",0.9)))
            try:
                ar=agent.act(d,agent.observe()); return {"ok":bool(ar.ok),"desc":ar.desc,"error":ar.error}
            except Exception as exc: return {"ok":False,"error":str(exc)}
        return ProxyGameEnvironment(observe_fn,act_fn,lambda obs:1.0 if obs.get("team",{}).get("status")=="TASKING" else 0.0)
    def init_battle_monitor(self):
        try:
            from core.battle_monitor import BattleMonitor
            for agent in (self.coordinator.agents.values() if self.coordinator else []):
                if agent.account.win is not None: self._battle_monitor=BattleMonitor(agent.account.win); return True
        except Exception as exc: logger.warning("战斗监控初始化失败: %s",exc)
        return False
    def handle_battle(self):
        if self._battle_monitor is None: return {"battled":False,"reason":"未初始化"}
        self._battle_stats=self._battle_monitor.monitor_once(max_wait=150.0); return self._battle_stats
    def pause_account(self,account_id): return bool(self.coordinator and self.coordinator.pause_account(account_id))
    def resume_account(self,account_id): return bool(self.coordinator and self.coordinator.resume_account(account_id))
    def paused_accounts(self): return self.coordinator.paused_accounts() if self.coordinator else []
    def optimize(self,episodes=300):
        try:
            from core.rl_trainer import GridEnv,QTrainer
            env=GridEnv(size=4,goal=(3,3)); trainer=QTrainer(env,episodes=episodes,epsilon=0.2); stats=trainer.train(); stats["opt_steps"]=trainer.evaluate(); self._last_optimize=stats; return stats
        except Exception as exc: return {"error":str(exc)}
    def status(self):
        return {"phase":self._phase,"running":self._running,"dry_run":self.dry_run,"client":self.client.to_dict(),**self._last_status,"rl":self.rl_env.to_dict() if self.rl_env else {},"optimize":self._last_optimize,"paused":self.paused_accounts(),"battle":self._battle_stats}
