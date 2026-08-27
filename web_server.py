# -*- coding: utf-8 -*-
"""FastAPI Web 控制台 (规格书 §33-35/§61)。

功能: REST API + WebSocket 实时推送 + 简单前端。
启动: python web_server.py [--port 8080]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

PROJECT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from core.config import load_config, load_env

app = FastAPI(title="梦幻西游五开本地AI控制台", version="1.0.0")

STATE: Dict[str, Any] = {
    "team": {},
    "accounts": {},
    "tasks": {},
    "started_at": 0,
    "status": "idle",
    "runner_obj": None,      # 进程内唯一的 GameRunner 实例
    "runner_cache": {},
}

_clients: List[WebSocket] = []

# 自主游戏运行器(懒加载, 由 /api/control 启停)
_RUNNER = None


def _get_runner():
    """加载 GameRunner(首次调用时初始化)。存于 STATE.runner_obj, 规避模块双加载。"""
    runner = STATE.get("runner_obj")
    if runner is None:
        from game_runner import GameRunner
        from core.config import load_config
        dry_run = os.getenv("MHXY_DRY_RUN", "1") == "1"
        runner = GameRunner(load_config(os.path.join(PROJECT, "config.yaml")),
                            dry_run=dry_run)
        STATE["runner_obj"] = runner
    return runner


# ---------------- Pydantic 模型 ----------------
class AccountOut(BaseModel):
    account_id: str
    role: str = "follower"
    character_name: str = ""
    level: int = 0
    state: str = "UNKNOWN"
    hp: int = 0
    mp: int = 0
    map: str = ""
    task: str = ""
    enabled: bool = True
    running: bool = False
    last_activity: str = ""
    anomaly: bool = False


class TeamOut(BaseModel):
    leader: str = ""
    members: List[str] = Field(default_factory=list)
    status: str = "IDLE"
    task: str = ""
    shared_goal: str = ""
    team_ready: bool = False
    backup_leader: str = ""
    synced: int = 0
    total: int = 0


class StatusOut(BaseModel):
    status: str = "idle"
    started_at: float = 0
    uptime: float = 0
    team: Dict[str, Any] = Field(default_factory=dict)
    accounts: Dict[str, Any] = Field(default_factory=dict)
    tasks: Dict[str, Any] = Field(default_factory=dict)
    runner: Dict[str, Any] = Field(default_factory=dict)


class ControlCmd(BaseModel):
    account_id: str = ""
    action: str = "STOP"


# ---------------- 状态管理 ----------------
def update_state(key: str, value: Any) -> None:
    STATE[key] = value
    _broadcast_sync()


def _broadcast_sync() -> None:
    payload = json.dumps({"type": "state", "data": get_status_dict()}, ensure_ascii=False)
    for ws in list(_clients):
        try:
            import asyncio
            asyncio.get_event_loop().create_task(ws.send_text(payload))
        except Exception:
            pass


def get_status_dict() -> Dict[str, Any]:
    uptime = time.time() - STATE["started_at"] if STATE["started_at"] else 0
    runner_status = {}
    runner = STATE.get("runner_obj")
    if runner is not None:
        try:
            runner_status = runner.status()
        except Exception as e:  # pragma: no cover
            runner_status = {"phase": "idle", "running": False,
                             "error": str(e)[:80]}
    # 兜底: 用缓存
    if not runner_status and STATE.get("runner_cache"):
        runner_status = STATE["runner_cache"]
    # 优先用 runner 的实时数据(自主游戏运行时), 否则用 config 静态值
    team = STATE["team"]
    accounts = STATE["accounts"]
    if runner_status:
        if runner_status.get("team"):
            team = runner_status["team"]
        if runner_status.get("accounts"):
            accounts = runner_status["accounts"]
    return {
        "status": STATE["status"],
        "started_at": STATE["started_at"],
        "uptime": round(uptime, 1),
        "team": team,
        "accounts": accounts,
        "tasks": STATE["tasks"],
        "runner": runner_status,
    }


# ---------------- REST API ----------------
@app.get("/", response_class=HTMLResponse)
async def index():
    # 优先返回独立前端文件(web/index.html), 含控制按钮
    frontend = os.path.join(PROJECT, "web", "index.html")
    if os.path.exists(frontend):
        with open(frontend, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_INDEX_HTML)


@app.get("/api/status", response_model=StatusOut)
async def api_status():
    return get_status_dict()


@app.get("/api/accounts")
async def api_accounts():
    return STATE["accounts"]


@app.get("/api/team", response_model=TeamOut)
async def api_team():
    return STATE["team"]


@app.get("/api/screenshot/{account_id}")
async def api_screenshot(account_id: str):
    shot_dir = os.path.join(PROJECT, "logs", account_id, "screenshots")
    if not os.path.isdir(shot_dir):
        return {"error": "无截图"}
    snaps = sorted(f for f in os.listdir(shot_dir) if f.endswith(".png"))
    if not snaps:
        return {"error": "无截图"}
    return FileResponse(os.path.join(shot_dir, snaps[-1]), media_type="image/png")


@app.post("/api/game/launch")
async def api_game_launch():
    """启动游戏客户端(通过 lifecycle)。"""
    try:
        from automation.lifecycle import GameClient
        client = GameClient()
        ok = client.launch()
        if ok:
            _broadcast_sync()
            return {"ok": True, "note": "游戏客户端已启动, 请手动登录"}
        return {"ok": False, "note": "启动失败(可能在运行中)"}
    except Exception as e:
        return {"ok": False, "note": "启动失败: " + str(e)[:80]}


@app.post("/api/game/shutdown")
async def api_game_shutdown():
    """关闭游戏客户端。"""
    try:
        from automation.lifecycle import GameClient
        client = GameClient()
        ok = client.shutdown(force=True)
        _broadcast_sync()
        return {"ok": ok, "note": "游戏客户端已关闭"}
    except Exception as e:
        return {"ok": False, "note": "关闭失败: " + str(e)[:80]}


@app.get("/api/tasks/recommend")
async def api_tasks_recommend(level: int = 109):
    """按等级推荐最值得做的任务(攻略 §17 联动系统)。"""
    try:
        from strategies.task_db import filter_by_level
        tasks = [t.to_dict() for t in filter_by_level(level)]
        return {"level": level, "count": len(tasks), "tasks": tasks}
    except Exception as e:
        return {"level": level, "count": 0, "tasks": [], "error": str(e)}


@app.get("/api/plan/daily")
async def api_plan_daily(day: int = 7):
    """逐日五开计划(攻略落地)。"""
    try:
        from strategies.daily_plan import plan_for_day
        return plan_for_day(day)
    except Exception as e:
        return {"day": day, "error": str(e)}


@app.get("/api/plan/roadmap")
async def api_plan_roadmap():
    """五开里程碑路线。"""
    try:
        from strategies.daily_plan import milestone_roadmap
        return {"roadmap": milestone_roadmap()}
    except Exception as e:
        return {"roadmap": [], "error": str(e)}


@app.post("/api/control")
async def api_control(cmd: ControlCmd):
    """控制命令: START/STOP/PAUSE/RESUME/MANUAL/AUTO + 优化。"""
    action = cmd.action.upper()
    runner = _get_runner()
    # 缓存 runner 状态到 STATE(供 get_status_dict 可靠读取)
    try:
        STATE["runner_cache"] = runner.status()
    except Exception:
        STATE["runner_cache"] = {"phase": "idle", "running": False}
    if action in ("START", "AUTO"):
        task = cmd.account_id or cmd.account_id or "shimen"
        ok = runner.start(task=task if task in ("shimen", "guigua", "fengyao") else "shimen")
        if ok:
            STATE["status"] = "running"
            _broadcast_sync()
            return {"ok": True, "cmd": action, "note": "自主游戏启动"}
        return {"ok": False, "cmd": action, "note": "已在运行"}
    if action in ("STOP", "PAUSE"):
        runner.stop()
        STATE["status"] = "idle"
        _broadcast_sync()
        return {"ok": True, "cmd": action, "note": "自主游戏停止"}
    if action in ("OPTIMIZE", "TRAIN"):
        # 强化学习优化: 训练策略(模拟环境演示)
        stats = runner.optimize(episodes=300)
        _broadcast_sync()
        return {"ok": True, "cmd": action, "note": "RL优化完成", "stats": stats}
    if action == "MANUAL":
        # 人工接管(§47): 有 account_id 则暂停单账号, 否则整体暂停
        if cmd.account_id:
            r = runner.pause_account(cmd.account_id)
            _broadcast_sync()
            return {"ok": r, "cmd": action, "account": cmd.account_id,
                    "note": ("已接管 " + cmd.account_id) if r else ("账号不存在 " + cmd.account_id)}
        runner.stop()
        STATE["status"] = "manual"
        _broadcast_sync()
        return {"ok": True, "cmd": action, "note": "人工接管模式"}
    if action == "RESUME":
        # 恢复单账号(§47)
        if cmd.account_id:
            r = runner.resume_account(cmd.account_id)
            _broadcast_sync()
            return {"ok": r, "cmd": action, "account": cmd.account_id,
                    "note": ("已恢复 " + cmd.account_id) if r else ("账号不存在 " + cmd.account_id)}
        _broadcast_sync()
        return {"ok": True, "cmd": action, "note": "已恢复全部"}
    _broadcast_sync()
    return {"ok": True, "cmd": action, "account": cmd.account_id, "note": "已记录"}


# ---------------- WebSocket ----------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    await ws.send_text(json.dumps({"type": "state", "data": get_status_dict()}, ensure_ascii=False))
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _clients:
            _clients.remove(ws)

_INDEX_HTML = "<!DOCTYPE html><html lang='zh'><head><meta charset='UTF-8'><title>五开控制台</title><style>body{font-family:system-ui;margin:20px;background:#1a1a2e;color:#eee}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}.card{background:#16213e;border:1px solid #333;border-radius:8px;padding:12px}.card h3{color:#f5c518}.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}.running{background:#2ecc71}.stopped{background:#555}.anomaly{background:#e74c3c}.log{font-family:monospace;font-size:12px;color:#aaa}</style></head><body><h1>梦幻西游五开本地 AI 控制台</h1><div id=team></div><div class=grid id=accounts></div><script>const ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws');ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='state')render(m.data)};function render(d){const t=d.team||{};document.getElementById('team').innerHTML='<div class=card><h3>队伍状态</h3><p>队长: <b>'+(t.leader||'-')+'</b> | 备用: '+(t.backup_leader||'-')+' | '+t.status+'</p><p>任务: '+(t.task||'-')+' | '+(t.synced||0)+'/'+(t.total||0)+' 同步</p></div>';const a=d.accounts||{};document.getElementById('accounts').innerHTML=Object.entries(a).map(([id,x])=>'<div class=card><h3>'+(x.character_name||id)+' <span class=badge '+(x.running?'running':'stopped')+'>'+(x.running?'运行中':'停止')+'</span></h3><p>状态: '+x.state+' | '+x.map+' | '+x.task+'</p><p>最近: <span class=log>'+(x.last_activity||'-')+'</span></p><img src=/api/screenshot/'+id+' style=width:100%;border-radius:4px onerror=this.style.display=\'none\'></div>').join('')}fetch('/api/status').then(r=>r.json()).then(render);</script></body></html>"


def main() -> None:
    ap = argparse.ArgumentParser(description="梦幻西游 Web 控制台")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    load_env()
    settings = load_config(os.path.join(PROJECT, "config.yaml"))
    accs = {}
    for c in settings.get("accounts", {}).get("list", []):
        accs[c["id"]] = {
            "account_id": c["id"], "role": c.get("role", "follower"),
            "enabled": c.get("enabled", False), "state": "IDLE",
            "running": False, "hp": 0, "mp": 0, "map": "", "task": "",
            "character_name": "", "level": 0, "last_activity": "", "anomaly": False,
        }
    STATE["accounts"] = accs
    STATE["team"] = {"leader": settings.get("accounts", {}).get("leader", ""),
                     "members": [c["id"] for c in settings.get("accounts", {}).get("list", []) if c.get("enabled")],
                     "status": "IDLE", "task": "", "shared_goal": "",
                     "team_ready": False, "backup_leader": "", "synced": 0, "total": 0}
    STATE["started_at"] = time.time()
    STATE["status"] = "running"
    import uvicorn
    print(f"Web 控制台: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
