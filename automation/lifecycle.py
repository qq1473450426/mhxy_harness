# -*- coding: utf-8 -*-
"""游戏客户端生命周期管理 (自主游戏闭环)。

实现: 启动 -> 监控 -> (任务由 Agent/Coordinator 完成) -> 结束

设计原则:
- 不注入凭据, 启动后由游戏/玩家完成登录(安全)
- 监控: 进程存活 + 窗口出现 + 状态检测
- 结束: 安全退出(可选保留/关闭)
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LifecycleError(Exception):
    """生命周期管理错误。"""


@dataclass
class ClientState:
    """客户端运行时状态。"""

    running: bool = False
    process_id: Optional[int] = None
    window_hwnd: Optional[int] = None
    window_title: str = ""
    phase: str = "idle"
    error: str = ""
    started_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"running": self.running, "process_id": self.process_id,
                "window_hwnd": self.window_hwnd, "window_title": self.window_title,
                "phase": self.phase, "error": self.error,
                "started_at": round(self.started_at, 1)}


class GameClient:
    """梦幻西游客户端生命周期控制器。"""

    def __init__(self, client_dir: str = "D:/梦幻西游",
                 launcher: str = "my.exe") -> None:
        self.client_dir = client_dir
        self.launcher = launcher
        self.state = ClientState()
        self._proc: Optional[subprocess.Popen] = None
        self._target_proc_names = ["my", "mhmain", "mhtab", "my_new"]

    # ---------------- 启动 ----------------
    def launch(self, window_title: str = "梦幻西游") -> bool:
        """启动客户端。返回是否已拉起(不保证已登录)。"""
        if self.state.running:
            logger.info("客户端已在运行, 跳过启动")
            return True
        exe = os.path.join(self.client_dir, self.launcher)
        if not os.path.exists(exe):
            raise LifecycleError("启动器不存在: " + exe)
        try:
            self._proc = subprocess.Popen([exe], cwd=self.client_dir)
            self.state.process_id = self._proc.pid
            self.state.phase = "launching"
            self.state.started_at = time.time()
            logger.info("客户端启动: pid=%s launcher=%s", self.state.process_id, exe)
            return True
        except Exception as e:
            self.state.error = str(e)
            self.state.phase = "stopped"
            raise LifecycleError("启动失败: " + str(e)) from e

    # ---------------- 进程检测 ----------------
    def _procs(self):
        """枚举游戏相关进程(psutil 优先)。"""
        try:
            import psutil  # type: ignore
            for p in psutil.process_iter(["pid", "name"]):
                name = (p.info.get("name") or "").lower().replace(".exe", "")
                if name in self._target_proc_names:
                    yield p.info["pid"], p.info["name"]
        except Exception:
            if self._proc is not None and self._proc.poll() is None:
                yield self._proc.pid, self.launcher

    def is_client_running(self) -> bool:
        """检测游戏进程是否存活。"""
        return any(True for _ in self._procs())

    # ---------------- 监控 ----------------
    def monitor(self, timeout: float = 120.0) -> Dict[str, Any]:
        """监控客户端直到窗口出现或超时。"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.is_client_running():
                self.state.phase = "stopped"
                return self.state.to_dict()
            win = self._find_window()
            if win is not None:
                self.state.window_hwnd = win[0]
                self.state.window_title = win[1]
                self.state.phase = "in_game"
                self.state.running = True
                return self.state.to_dict()
            time.sleep(1.0)
        self.state.phase = "login"
        self.state.running = self.is_client_running()
        return self.state.to_dict()

    def _find_window(self):
        """查找游戏主窗口。"""
        try:
            import win32gui  # type: ignore
            result = []
            def cb(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                t = win32gui.GetWindowText(hwnd) or ""
                if "梦幻西游" in t or "ONLINE" in t:
                    result.append((hwnd, t))
            win32gui.EnumWindows(cb, None)
            return result[0] if result else None
        except Exception:
            return None

    # ---------------- 结束 ----------------
    def shutdown(self, force: bool = False) -> bool:
        """关闭客户端。force=True 强制结束进程。"""
        killed = False
        for pid, name in list(self._procs()):
            try:
                import psutil  # type: ignore
                p = psutil.Process(pid)
                if force:
                    p.kill()
                else:
                    p.terminate()
                killed = True
            except Exception:
                pass
        self.state.running = False
        self.state.phase = "stopped"
        return killed

    def to_dict(self) -> Dict[str, Any]:
        return self.state.to_dict()
