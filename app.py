# -*- coding: utf-8 -*-
"""梦幻西游五开本地 AI 自动任务系统 - 入口。

用法:
    python app.py --mode sim --steps 5     # 模拟模式(无游戏)
    python app.py --mode real --account 1  # 真实模式(需游戏窗口)
    python app.py --list                    # 列出发现的游戏窗口
    python app.py --scan                    # 截图 + OCR 识别当前画面(只读)
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description="梦幻西游五开本地AI自动任务系统")
    ap.add_argument("--mode", choices=["sim", "real"], default=None,
                    help="运行模式: sim=模拟器 | real=真实游戏窗口")
    ap.add_argument("--account", type=str, default=None, help="账号 id(默认 leader)")
    ap.add_argument("--steps", type=int, default=5, help="Agent 运行步数(0=无限)")
    ap.add_argument("--goal", default="完成师门任务", help="任务目标")
    ap.add_argument("--list", action="store_true", help="列出发现的游戏窗口")
    ap.add_argument("--scan", action="store_true", help="截图+OCR识别当前画面(只读)")
    ap.add_argument("--rag-demo", action="store_true", help="RAG+LLM 决策演示(无需本地模型)")
    ap.add_argument("--task", default=None, help="任务模式: shimen(师门)")
    ap.add_argument("--dry-run", action="store_true", help="只观察+决策, 不执行动作(安全)")
    ap.add_argument("--team", action="store_true", help="五开协调模式(Phase 5)")
    ap.add_argument("--team-task", default="抓鬼", help="队伍任务: 抓鬼/师门/封妖")
    ap.add_argument("--memory", action="store_true", help="启用长期记忆(Phase 8)")
    ap.add_argument("--replay", action="store_true", help="启用 Replay 记录(Phase 8)")
    ap.add_argument("--llm", default=None, help="决策大脑: rule|mock|ollama(默认读配置)")
    ap.add_argument("--my-plan", action="store_true", help="基于当前账号生成个性化攻略计划")
    ap.add_argument("--lineup", default=None, help="生成五开阵容(传已有门派, 如 方寸山)")
    ap.add_argument("--budget", default="low", choices=["low", "balance", "high"], help="预算档位")
    ap.add_argument("--manual", action="store_true", help="一站式作战手册(状态+攻略+阵容+任务+计划)")
    ap.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = ap.parse_args()

    from core.config import load_config, load_env
    load_env()
    settings = load_config(args.config)

    if args.list:
        list_windows()
        return

    if args.scan:
        scan_screen(settings)
        return

    if args.rag_demo:
        run_rag_demo(settings)
        return

    if args.team:
        run_team(settings, args.team_task, args.steps, args.dry_run)
        return

    if args.my_plan:
        run_my_plan(settings)
        return

    if args.manual:
        # 一站式作战手册(状态+攻略+阵容+任务+里程碑), 复用 run_my_plan
        run_my_plan(settings)
        return

    if args.lineup:
        from strategies.lineup import build_lineup
        r = build_lineup(args.lineup, args.budget)
        print(f"=== 五开阵容({r['plan_name']}) ===")
        print(f"说明: {r['plan_desc']}")
        print(f"已有门派: {r['lead_sector']}({r['lead_role']}) 兼容: {'是' if r['compatible'] else '需调整'}")
        print("阵容:")
        for u in r["lineup"]:
            print(f"  {u['slot']}: {u['sector']}({u['role']}) [{u['src']}]")
        print("停级点:", ", ".join(f"{lv}级:{d}" for lv, d in r["breakpoints"].items()))
        return

    mode = args.mode or settings.get("mode", "sim")
    if mode == "sim":
        run_sim(settings, args.steps, args.goal, llm=args.llm, task=args.task,
                use_memory=args.memory, use_replay=args.replay)
    elif mode == "real":
        run_real(settings, args.account, args.steps, args.goal, llm=args.llm,
                 task=args.task, dry_run=args.dry_run,
                 use_memory=args.memory, use_replay=args.replay)
    else:
        ap.error(f"未知模式 {mode}")


def list_windows() -> None:
    from automation.window import WindowManager
    wm = WindowManager()
    if not wm.available:
        print("pywin32 不可用")
        return
    wins = wm.find_game_windows()
    if not wins:
        print("未发现梦幻西游游戏窗口")
        return
    print(f"发现 {len(wins)} 个游戏窗口:")
    for w in wins:
        print(f"  hwnd={w.hwnd} title={w.title!r} rect=({w.x},{w.y},{w.w}x{w.h})")


def scan_screen(settings) -> None:
    """只读巡检: 绑定 leader 窗口 -> 截图 -> OCR -> 状态机。"""
    from automation.window import WindowManager
    from vision.capture import capture_window
    from vision.ocr import OCREngine
    from core.state_machine import StateMachine

    wm = WindowManager()
    acc_cfg = next((a for a in settings["accounts"]["list"] if a.get("enabled")), None)
    if acc_cfg is None:
        print("配置中没有启用账号")
        return
    try:
        win = wm.bind_account(acc_cfg["window_title"])
    except Exception as e:
        print(f"窗口绑定失败: {e}")
        return
    print(f"绑定窗口: {win.title} rect={win.rect}")
    # 若窗口最小化则先恢复(只读巡检也要看到画面)
    if not win.is_visible() or win.w < 100:
        wm.restore(win)
        import time
        time.sleep(1.0)
        win = wm.bind_account(acc_cfg["window_title"])
        print(f"已恢复窗口: rect={win.rect}")
    img, size = capture_window(win)
    ocr = OCREngine(settings["vision"].get("ocr_backend", "rapidocr"))
    texts = ocr.text_only(img, size)
    print(f"OCR 识别 {len(texts)} 行:")
    for t in texts:
        print(f"  - {t}")
    gs = StateMachine(acc_cfg["id"]).update(texts, img, size)
    print(f"状态机判定: {gs.status.value} 地图={gs.map_name} 位置={gs.position} "
          f"任务={gs.task_name} {gs.task_progress}")
    # 模板检测(Phase 2)
    try:
        import yaml
        import numpy as np
        from vision.detector import TemplateMatcher
        tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "config", "templates.yaml")
        tpl_cfg = {}
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl_cfg = yaml.safe_load(f) or {}
        matcher = TemplateMatcher(tpl_cfg)
        if matcher.available:
            w, h = size
            bgr = np.frombuffer(img, dtype=np.uint8).reshape(h, w, 3)[:, :, ::-1].copy()
            elems = matcher.match_all(bgr)
            print(f"模板检测 {len(elems)}/{len(matcher.available)} 个元素:")
            for name, el in sorted(elems.items()):
                print(f"  {name}: center={el.center} conf={el.confidence:.3f}")
            gs.extra["elements"] = {k: v.to_dict() for k, v in elems.items()}
    except Exception as e:
        print(f"模板检测跳过: {e}")
    # 保存截图供查看
    from vision.capture import capture_to_png
    import time
    shot_path = os.path.join(settings["logging"]["dir"], "scan",
                             time.strftime("%Y%m%d_%H%M%S") + ".png")
    os.makedirs(os.path.dirname(shot_path), exist_ok=True)
    if capture_to_png(win, shot_path):
        print(f"截图已保存: {shot_path}")


def run_sim(settings, steps: int, goal: str, llm: str | None = None,
              task: str | None = None,
              use_memory: bool = False, use_replay: bool = False) -> None:
    from core.sim import MockGame
    from core.account import Account
    from core.agent import GameAgent
    from core.brain import LLMBrain, RuleBrain
    from core.llm import LLMClient
    from knowledge.retriever import Retriever
    from knowledge.loader import KnowledgeLoader

    # 决策大脑: rule | mock | ollama
    brain = None
    if llm == "rule":
        brain = RuleBrain()
    elif llm in ("mock", "ollama"):
        provider = "mock" if llm == "mock" else "ollama"
        retriever = Retriever(KnowledgeLoader(settings["knowledge"].get("repo", "")))
        brain = LLMBrain(llm=LLMClient(provider=provider,
                                       model=settings["llm"].get("model", "qwen2.5:7b"),
                                       base_url=settings["llm"].get("base_url", "http://127.0.0.1:11434")),
                          retriever=retriever)

    # 模拟模式: 用 MockGame 替换窗口/截图/驱动
    sim = MockGame()
    acc_cfg = settings["accounts"]["list"][0]
    account = Account(acc_cfg, settings)

    class _SimWin:
        hwnd = 1
        title = "SIM"
        x = y = 0
        w = h = 320
        def is_valid(self):
            return True

    account.win = _SimWin()

    class _SimAgent(GameAgent):
        def observe(self):
            screen = sim.observe()
            texts = screen.texts
            gs = self.account.sm.update(texts, screen.render(), screen.size)
            return gs

        def act(self, decision, gs):
            sim.act(decision.action)
            return type("AR", (), {"ok": True, "desc": decision.action, "error": None})()

    shimen_task = None
    if task == "shimen":
        from tasks.shimen import ShimenTask
        shimen_task = ShimenTask(max_rounds=3, max_minutes=1)
        shimen_task.bind(
            get_task=lambda: sim.act("ACCEPT_TASK"),
            run=lambda: sim.act("NAVIGATE"),
            interact=lambda: sim.act("INTERACT"),
            submit=lambda: sim.act("SUBMIT_TASK"),
            verify=lambda: True)

    # Phase 8: 记忆 + Replay
    memory = None
    replay = None
    if use_memory:
        from core.memory import LongTermMemory
        memory = LongTermMemory(os.path.join(settings["logging"]["dir"], "memory.db"))
    if use_replay:
        from core.replay import ReplayRecorder
        replay = ReplayRecorder(os.path.join(settings["logging"]["dir"], "..", "replay"),
                                account.account_id)

    agent = _SimAgent(account, brain=brain, task=shimen_task,
                      memory=memory, replay=replay, tick_seconds=0.2)
    print(f"== 模拟模式启动: 目标={goal} 步数={steps} "
          f"大脑={type(agent.brain).__name__} 任务={task or '无'} ==")
    if replay is not None:
        print(f"Replay 已启用: {replay.path}")
    agent.run(goal=goal, max_steps=steps)
    print(f"== 模拟结束: 师门任务进度=第{sim.round}次 ==")


def run_real(settings, account_id: str | None, steps: int, goal: str,
              llm: str | None = None, task: str | None = None,
              dry_run: bool = False,
              use_memory: bool = False, use_replay: bool = False) -> None:
    from core.account import Account
    from core.agent import GameAgent
    from core.brain import LLMBrain, RuleBrain
    from core.llm import LLMClient
    from knowledge.retriever import Retriever
    from knowledge.loader import KnowledgeLoader
    from vision.detector import TemplateMatcher
    from vision.tracker import Tracker
    import yaml

    # 决策大脑
    brain = None
    if llm == "rule":
        brain = RuleBrain()
    elif llm in ("mock", "ollama"):
        provider = "mock" if llm == "mock" else "ollama"
        retriever = Retriever(KnowledgeLoader(settings["knowledge"].get("repo", "")))
        brain = LLMBrain(llm=LLMClient(provider=provider,
                                       model=settings["llm"].get("model", "qwen2.5:7b"),
                                       base_url=settings["llm"].get("base_url", "http://127.0.0.1:11434")),
                          retriever=retriever)

    acc_cfg = next(
        (a for a in settings["accounts"]["list"]
         if (account_id is None and a.get("enabled")) or a.get("id") == account_id),
        None)
    if acc_cfg is None:
        print(f"未找到账号 {account_id or 'leader'}")
        return

    account = Account(acc_cfg, settings)
    if not account.bind_window():
        print("窗口绑定失败, 请先启动游戏")
        return
    # 模板检测器
    tracker = None
    try:
        tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "config", "templates.yaml")
        tpl_cfg = {}
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl_cfg = yaml.safe_load(f) or {}
        matcher = TemplateMatcher(tpl_cfg)
        if matcher.available:
            tracker = Tracker(matcher)
    except Exception:
        tracker = None

    # 任务绑定
    shimen_task = None
    if task == "shimen":
        from tasks.shimen import ShimenTask
        shimen_task = ShimenTask(
            max_rounds=settings.get("tasks", {}).get("shimen", {}).get("max_rounds", 20),
            max_minutes=settings.get("tasks", {}).get("shimen", {}).get("max_minutes", 60))
        print(f"任务: 师门 {shimen_task.state.target_rounds} 环")

    # Phase 8: 长期记忆 + Replay
    memory = None
    replay = None
    if use_memory:
        from core.memory import LongTermMemory
        memory = LongTermMemory(os.path.join(settings["logging"]["dir"], "memory.db"))
        print("长期记忆已启用")
    if use_replay:
        from core.replay import ReplayRecorder
        replay = ReplayRecorder(os.path.join(settings["logging"]["dir"], "..", "replay"),
                                account.account_id)
        print(f"Replay 已启用: {replay.path}")

    agent = GameAgent(account, brain=brain, tracker=tracker, task=shimen_task,
                      memory=memory, replay=replay,
                      ocr_backend=settings["vision"].get("ocr_backend", "rapidocr"),
                      tick_seconds=settings["automation"].get("tick_seconds", 0.5),
                      max_retry=settings["automation"].get("max_retry", 3))
    if dry_run:
        # 安全模式: 只观察+决策, 打印而不执行
        for i in range(steps):
            gs = agent.observe()
            if agent.task is not None:
                act = agent.task.step(gs)
                print(f"[{i}] 任务决策: {act['action']} - {act['reason']}")
            else:
                d = agent.think(gs, goal)
                print(f"[{i}] LLM/规则决策: {d.action} conf={d.confidence:.2f} - {d.reason}")
            import time
            time.sleep(agent.tick)
        print("== 安全模式(dry-run)结束: 未执行任何鼠标键盘操作 ==")
        return
    print(f"== 真实模式启动: 账号={account.account_id} 目标={goal} 步数={steps} "
          f"大脑={type(agent.brain).__name__} ==")
    agent.run(goal=goal, max_steps=steps)


def run_rag_demo(settings) -> None:
    """RAG + LLM 决策演示(无需本地模型)。"""
    import json as _json
    from core.llm import LLMClient
    from core.brain import LLMBrain
    from core.game_state import GameState, GameStatus
    from knowledge.loader import KnowledgeLoader
    from knowledge.retriever import Retriever

    repo = settings["knowledge"].get("repo", "")
    print(f"== RAG + LLM 决策演示 (知识库: {repo}) ==")
    ret = Retriever(KnowledgeLoader(repo))
    s = ret.stats()
    print(f"知识库: {s['docs']} 文档, {s['modules']} 模块, {s['chunks']} 块, backend={s['backend']}")

    # 当前真实画面状态
    gs = GameState(account_id="acc1", status=GameStatus.TASK_DIALOG, map_name="长安城",
                   position=(308, 137), task_name="师门任务", task_progress="第2次",
                   dialogue_open=True, dialog_text="任务完成，找师父交报告去")
    print(f"\n当前状态: {gs.to_dict()}")

    brain = LLMBrain(llm=LLMClient(provider="mock"), retriever=ret)
    d = brain.decide(gs, goal="完成师门任务")
    print(f"\nLLM 决策(mock): {_json.dumps(d.to_dict(), ensure_ascii=False, indent=2)}")
    print("\n提示: 安装 Ollama 后运行 --llm ollama 使用本地模型 qwen2.5:7b")


def run_team(settings, team_task: str, steps: int, dry_run: bool) -> None:
    """五开协调模式(Phase 5): 组建队伍 -> 绑定窗口 -> 规划 -> 执行。"""
    from core.coordinator import Coordinator
    from core.planner import GlobalPlanner
    import time

    print(f"== 五开协调模式: 任务={team_task} 步数={steps} dry_run={dry_run} ==")
    coord = Coordinator(settings)
    n = coord.build_from_config()
    print(f"队伍组建: {n} 个账号, leader={coord.team.leader}, "
          f"members={coord.team.members}, backup={coord.team.backup_leader}")
    if n == 0:
        print("无启用账号, 请检查 config.yaml accounts 段")
        return

    # Phase 7: 绑定任务(师门/抓鬼/封妖)
    task_map = {"shimen": "shimen", "师门": "shimen",
                "guigua": "guigua", "抓鬼": "guigua",
                "fengyao": "fengyao", "封妖": "fengyao"}
    task_key = task_map.get(team_task)
    if task_key:
        task = coord.bind_task(task_key)
        print(f"任务绑定: {task.name} (可用: {coord.task_manager.available})")
    else:
        print(f"任务 {team_task} 未注册, 可用: {coord.task_manager.available}")

    # 绑定窗口(真实模式)或模拟模式
    if dry_run:
        results = coord.bind_windows()
        print(f"窗口绑定: {results}")
    else:
        # 模拟窗口(无游戏也能演示五开流程)
        class _SimWin:
            hwnd = 0
            title = "SIM"
            x = y = 0
            w = h = 320
            def is_valid(self):
                return True
        for acc_id, acc in coord.accounts.items():
            acc.win = _SimWin()
        results = {aid: True for aid in coord.accounts}
        print("模拟窗口绑定完成")

    online = [aid for aid, ok in results.items() if ok]
    if not online:
        print("没有可用窗口")
        return
    coord.team.members = online
    coord.team.status = __import__("core.team", fromlist=["TeamStatus"]).TeamStatus.READY

    # 全局规划器
    planner = GlobalPlanner(coord.team)
    plan = planner.plan(team_task)
    print(f"\n全局计划: {plan.to_dict()}")

    # 创建 Agent(模拟模式使用假观察)
    coord.create_agents()
    if dry_run:
        print("\n== dry-run: 仅展示队伍状态, 不执行 ==")
        for i in range(steps):
            plan = planner.plan(team_task)
            print(f"[{i}] 阶段={plan.phase} 计划={plan.role_actions}")
            time.sleep(0.3)
        print("== dry-run 结束 ==")
        return

    print("\n== 队伍执行开始 ==")
    coord.start(goal=team_task, max_steps=steps)
    try:
        while any(ag.running for ag in coord.agents.values()):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n手动停止...")
    finally:
        coord.stop()
    print("== 队伍执行结束 ==")
    print(f"队伍状态: {coord.team.to_dict()}")


def run_my_plan(settings) -> None:
    """基于当前真实账号生成个性化攻略计划。"""
    from automation.window import WindowManager
    from vision.capture import capture_window
    from vision.ocr import OCREngine
    from strategies.daily_plan import plan_for_day, milestone_roadmap, PHASES
    from strategies.task_db import filter_by_level

    wm = WindowManager()
    acc_cfg = next((a for a in settings["accounts"]["list"] if a.get("enabled")), None)
    if acc_cfg is None:
        print("配置中没有启用账号")
        return
    try:
        win = wm.bind_account(acc_cfg["window_title"])
    except Exception as e:
        print(f"无法绑定窗口: {e}")
        return

    img, size = capture_window(win)
    ocr = OCREngine(settings["vision"].get("ocr_backend", "rapidocr"))
    texts = ocr.text_only(img, size)
    joined = " ".join(texts)

    # 解析当前等级/门派(简单启发式)
    level = None
    import re as _re
    # 优先精确匹配"等级 N"(角色信息区), 避免误判排队弹窗数字
    m = _re.search(r"等级\s*(\d+)", joined)
    if m:
        level = int(m.group(1))
    if level is None:
        print("提示: 未识别到明确等级信息(可能在排队/选服界面)")
    sect = ""
    for s in ("方寸山", "化生寺", "普陀山", "女儿村", "魔王寨", "大唐", "龙宫", "地府", "天宫", "凌波城"):
        if s in joined:
            sect = s
            break

    # 位置/阶段
    phase = "登录/选服"
    if "选择服务器" in joined or "排队" in joined:
        phase = "登录排队"
    elif "选择角色" in joined:
        phase = "选择角色"
    elif "长安城" in joined or "师门" in joined:
        phase = "游戏内"

    print(f"=== 当前账号: {sect or '未知门派'} {('等级' + str(level)) if level else ''} | 状态: {phase} ===")
    print()
    if level:
        # 找对应攻略阶段
        target_day = 1
        if level < 20: target_day = 1
        elif level < 40: target_day = 7
        elif level < 60: target_day = 10
        elif level < 69: target_day = 14
        elif level < 109: target_day = 30
        else: target_day = 60
        p = plan_for_day(target_day)
        print(f"—— 当前等级段攻略(第{target_day}天) ——")
        print(f"阶段: {p['phase']}")
        print(f"目标: {p['goal']}")
        print(f"今日流程: {' -> '.join(p['daily_flow'])}")
        print()
        print(f"—— 等级{level} 可做任务(按推荐度) ——")
        for t in filter_by_level(level):
            print(f"  [{t.tier}] {t.name:8s} 现金{t.cash:2s} 物品{t.item:2s}")
    else:
        print("未识别到等级(可能在登录/选服界面)。进入游戏后重跑 --my-plan。")
        print("当前界面要点: " + (sect or phase))
    print()
    # 阵容推荐(基于当前已识别门派)
    print("—— 五开阵容推荐 ——")
    try:
        from strategies.lineup import build_lineup
        r = build_lineup(sect or "方寸山", "low")
        print(f"{r['plan_name']}: {r['plan_desc']}")
        for u in r["lineup"]:
            print(f"  {u['slot']}: {u['sector']}({u['role']}) [{u['src']}]")
        print(f"停级点: {', '.join(str(lv) for lv in r['breakpoints'])}")
    except Exception as e:
        print(f"阵容生成: {e}")
    print()
    print("—— 五开里程碑 ——")
    for m in milestone_roadmap():
        print(f"  第{m['day']:>3}天: {m['goal']}")


if __name__ == "__main__":
    sys.exit(main())
