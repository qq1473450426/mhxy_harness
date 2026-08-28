# -*- coding: utf-8 -*-
"""自主游戏编排器：支持真实窗口附着、自动执行和人类示范学习。"""
from __future__ import annotations
import logging, os, threading, time
from typing import Any, Dict, Optional
from automation.lifecycle import GameClient
from automation.window import WindowInfo
from core.coordinator import Coordinator
from core.rl_env import ProxyGameEnvironment
from core.human_learning import HumanDemoRecorder, VisualDemoPolicy, LearningScore
logger = logging.getLogger(__name__)


class GameRunner:
    def __init__(self, settings: Dict[str, Any], dry_run: bool = False) -> None:
        self.settings=settings; self.dry_run=dry_run; self.client=GameClient()
        self.coordinator: Optional[Coordinator]=None; self.rl_env=None
        self._thread=None; self._stop=threading.Event(); self._running=False; self._phase="idle"
        self._last_status={}; self._last_optimize={}; self._battle_monitor=None; self._battle_stats={}
        self.learning_recorder: Optional[HumanDemoRecorder] = None
        self.learning_policy = VisualDemoPolicy.load("learning/policy.json")
        self._learning_result: Dict[str, Any] = {}
        self._learning_run_result: Dict[str, Any] = {}

    def start(self, task="shimen", goal="", auto=True):
        if self._running: return False
        self._stop.clear(); self._running=True
        self._thread=threading.Thread(target=self._run,args=(task,goal,auto),daemon=True); self._thread.start(); return True

    def start_attached(self, win: WindowInfo, task="shimen", goal="", auto=True):
        if self._running or win is None or not win.is_valid(): return False
        try:
            self._stop.clear(); self._phase="attaching"
            self.client.state.window_hwnd=win.hwnd; self.client.state.window_title=win.title
            self.client.state.running=True; self.client.state.phase="in_game"
            self.coordinator=self._prepare_coordinator(win,task)
            leader=self.coordinator.team.leader
            if not leader or leader not in self.coordinator.agents:
                self.coordinator=None; self._phase="error:no_leader_agent"; return False
            self._last_status=self.coordinator.status(); self._running=True
            self._thread=threading.Thread(target=self._run_attached,args=(win,task,goal,auto),daemon=True)
            self._thread.start(); return True
        except Exception as exc:
            logger.exception("attached initialization failed"); self._phase="error:"+str(exc)[:120]; self._running=False; return False

    def step_attached(self, win: WindowInfo, task="shimen", goal=""):
        if win is None or not win.is_valid(): return {"ok": False, "error": "窗口无效"}
        try:
            if self._running: return {"ok": False, "error": "自动任务正在运行，请先停止后再执行单步"}
            if self.coordinator is None:
                self.coordinator=self._prepare_coordinator(win, task); self._phase="attached_step"
            agent=self.coordinator.agents.get(self.coordinator.team.leader)
            if agent is None: return {"ok": False, "error": "没有可执行的队长 Agent，请重新绑定窗口"}
            result=agent.step(goal or task); self._last_status=self.coordinator.status()
            return {"ok": True, "result": result}
        except Exception as exc:
            logger.exception("single step failed"); return {"ok": False, "error": str(exc)}

    def stop(self):
        self._stop.set()
        if self.learning_recorder and self.learning_recorder.running:
            try: self.learning_recorder.stop()
            except Exception: pass
        if self.coordinator is not None: self.coordinator.stop()
        self._running=False

    def _prepare_coordinator(self, win=None, task_name: str = ""):
        c=Coordinator(self.settings,ocr_backend=self.settings.get("vision",{}).get("ocr_backend","rapidocr"),tick_seconds=float(self.settings.get("automation",{}).get("tick_seconds",0.5)))
        c.build_from_config()
        if win is None: c.bind_windows()
        else:
            leader=c.team.leader
            if not leader and c.accounts:
                leader=next(iter(c.accounts)); c.team.set_leader(leader)
            if leader and leader in c.accounts:
                acc=c.accounts[leader]; acc.win=win; acc.state.hwnd=win.hwnd; acc.state.win_rect=win.rect
                from automation.input_driver import InputDriver
                inp=self.settings.get("input",{})
                acc.driver=InputDriver(win,backend=inp.get("backend","win32"),failsafe=bool(inp.get("failsafe",True)),move_duration=float(inp.get("move_duration",0.08)))
            c.team.members=[leader] if leader else []; c.team.team_ready=bool(c.team.members)
        if task_name:
            bound=c.bind_task(task_name)
            if bound is None: raise RuntimeError(f"无法绑定任务: {task_name}")
        c.create_agents(); return c

    def _run_attached(self,win,task,goal,auto):
        try:
            self._phase="attached"; self.client.state.window_hwnd=win.hwnd; self.client.state.window_title=win.title; self.client.state.running=True; self.client.state.phase="in_game"
            if self.coordinator is None: self.coordinator=self._prepare_coordinator(win,task)
            self._phase="team"; self.rl_env=self._build_rl_env(); self._phase="running"
            if auto: self.coordinator.start(goal=goal or task,max_steps=None)
            while not self._stop.is_set(): self._last_status=self.coordinator.status(); time.sleep(0.5)
        except Exception as exc: logger.exception("attached runner error"); self._phase="error:"+str(exc)[:120]
        finally:
            if self.coordinator is not None: self.coordinator.stop()
            self._phase="stopped" if self._stop.is_set() else "idle"; self._running=False

    def _run(self,task,goal,auto):
        try:
            if self.dry_run: self.coordinator=self._prepare_coordinator(task_name=task); self._phase="running"
            else:
                self._phase="launching"; self.client.launch(); self._phase="login"; st=self.client.monitor(timeout=120); self._last_status["client"]=st
                if st["phase"] not in ("in_game","login"): self._phase="error:"+st.get("phase","?"); return
                self.coordinator=self._prepare_coordinator(task_name=task)
            self._phase="team"; self.rl_env=self._build_rl_env(); self._phase="running"
            if auto: self.coordinator.start(goal=goal or task,max_steps=None)
            while not self._stop.is_set(): self._last_status=self.coordinator.status(); time.sleep(1.0)
        except Exception as exc: logger.exception("runner error"); self._phase="error:"+str(exc)[:120]
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

    # ---------------- 人类示范学习 ----------------
    def start_learning(self, win: WindowInfo) -> Dict[str, Any]:
        if self._running: return {"ok": False, "error": "请先停止自动任务"}
        if win is None or not win.is_valid(): return {"ok": False, "error": "窗口无效"}
        if self.learning_recorder and self.learning_recorder.running: return {"ok": False, "error": "已经在学习监听中"}
        try:
            self.learning_recorder=HumanDemoRecorder(win, root="learning/demos", sample_hz=4.0)
            path=self.learning_recorder.start()
            self._phase="human_learning"; self._learning_result={"ok":True,"status":"recording","path":path,"actions":0}
            return self._learning_result
        except Exception as exc:
            logger.exception("human learning start failed"); return {"ok":False,"error":str(exc)}

    def stop_learning(self, success: bool = True) -> Dict[str, Any]:
        if not self.learning_recorder or not self.learning_recorder.running:
            return {"ok":False,"error":"当前没有正在监听的示范"}
        try:
            path=self.learning_recorder.stop(); count=len(self.learning_recorder.actions)
            self._learning_result={"ok":True,"status":"completed","success":bool(success),"path":path,"actions":count}
            self._phase="idle"; return self._learning_result
        except Exception as exc: return {"ok":False,"error":str(exc)}

    def train_learning(self, passes: int = 8) -> Dict[str, Any]:
        """读取所有历史示范，成功示范获得更高终止回报，多次示范累积 replay buffer。"""
        policy=VisualDemoPolicy()
        demo_root="learning/demos"
        if not os.path.isdir(demo_root): return {"ok":False,"error":"没有 learning/demos 示范数据"}
        loaded=0; demos=0
        for name in sorted(os.listdir(demo_root)):
            d=os.path.join(demo_root,name)
            actions_path=os.path.join(d,"actions.jsonl")
            if not os.path.isfile(actions_path): continue
            demos += 1
            success=True
            meta_path=os.path.join(d,"meta.json")
            try:
                with open(meta_path,"r",encoding="utf-8") as f: success=bool(json.load(f).get("success",True))
            except Exception: pass
            try:
                import json
                with open(actions_path,"r",encoding="utf-8") as f: rows=[json.loads(x) for x in f if x.strip()]
                for row in rows:
                    sf=row.get("state_file",""); sp=os.path.join(d,sf)
                    if not sf or not os.path.isfile(sp): continue
                    from PIL import Image
                    with Image.open(sp) as im:
                        rgb=im.convert("RGB"); w,h=rgb.size; data=rgb.tobytes()
                    reward=(1.0 if success else 0.2)
                    policy.add_demo(data,w,h,type("A",(),row)(),reward)
                    loaded += 1
            except Exception as exc:
                logger.warning("示范读取失败 %s: %s",d,exc)
        stats=policy.train(passes=max(1,int(passes)))
        if not stats.get("ok"): return stats
        policy.save("learning/policy.json"); self.learning_policy=policy
        stats.update({"demos":demos,"policy":"learning/policy.json"}); self._learning_result=stats
        return stats

    def run_learned_once(self, win: WindowInfo, max_steps: int = 120, max_seconds: float = 180.0) -> Dict[str, Any]:
        """用已训练策略在真实窗口运行一次；不启动原任务线程，避免与学习策略抢输入。"""
        if self.learning_recorder and self.learning_recorder.running: return {"ok":False,"error":"请先停止示范监听"}
        if win is None or not win.is_valid(): return {"ok":False,"error":"窗口无效"}
        if not self.learning_policy.samples: return {"ok":False,"error":"还没有训练策略，请先完成示范并训练"}
        try:
            from automation.input_driver import InputDriver
            from core.action_verifier import ActionVerifier
            driver=InputDriver(win,backend="win32",move_duration=float(self.settings.get("input",{}).get("move_duration",0.12)))
            verifier=ActionVerifier(threshold=0.012,settle_ms=250)
            started=time.perf_counter(); steps=0; ok_count=0; fail_count=0; completed=False
            while steps < max_steps and time.perf_counter()-started < max_seconds:
                from vision.capture import capture_window
                frame,(w,h)=capture_window(win)
                pred=self.learning_policy.predict(frame,w,h,min_similarity=0.78)
                if not pred:
                    break
                kind=pred.get("kind")
                if kind=="CLICK":
                    before=(frame,(w,h)); ar=driver.click(int(pred.get("x",0)),int(pred.get("y",0)),"RL示范策略")
                    if ar.ok:
                        ok_count+=1; verifier.verify(win,before,settle_ms=250)
                    else: fail_count+=1
                elif kind=="PRESS":
                    ar=driver.press(str(pred.get("key","")),"RL示范策略")
                    if ar.ok: ok_count+=1
                    else: fail_count+=1
                else:
                    break
                steps += 1
                time.sleep(0.18)
                # 用现有任务状态机做“完成”探针，不执行它的动作。
                try:
                    if self.coordinator and self.coordinator.agents.get(self.coordinator.team.leader):
                        agent=self.coordinator.agents[self.coordinator.team.leader]; gs=agent.observe()
                        if agent.task is not None:
                            agent.task.step(gs)
                            status=getattr(agent.task.status,"value",str(agent.task.status))
                            completed=status=="COMPLETED"
                except Exception:
                    pass
                if completed: break
            duration=time.perf_counter()-started
            result=LearningScore.calculate(steps,ok_count,fail_count,completed,duration)
            result.update({"ok":True,"policy_states":len(self.learning_policy.q),"stop_reason":"completed" if completed else "policy_or_limit"})
            self._learning_run_result=result; self._learning_result=result
            return result
        except Exception as exc:
            logger.exception("learned run failed"); return {"ok":False,"error":str(exc)}

    def learning_status(self) -> Dict[str, Any]:
        recorder=self.learning_recorder
        return {"recording":bool(recorder and recorder.running),"path":recorder.session_dir if recorder else "","actions":len(recorder.actions) if recorder else 0,"policy_samples":len(self.learning_policy.samples),"policy_states":len(self.learning_policy.q),"last_train":self._learning_result,"last_run":self._learning_run_result}

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
        return {"phase":self._phase,"running":self._running,"dry_run":self.dry_run,"client":self.client.to_dict(),**self._last_status,"rl":self.rl_env.to_dict() if self.rl_env else {},"optimize":self._last_optimize,"paused":self.paused_accounts(),"battle":self._battle_stats,"learning":self.learning_status()}
