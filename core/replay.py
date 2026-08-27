# -*- coding: utf-8 -*-
"""Replay 系统 (Phase 8, 规格书 §43)。

将实际运行过程保存为:
    replay/YYYY-MM-DD_HH-MM-SS/
        screenshot_001.png
        state_001.json
        action_001.json
        meta.json

以后可以回放 AI 当时为什么做出这个决定。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReplayRecorder:
    """记录一次 Agent 运行的完整过程。"""

    def __init__(self, replay_dir: str = "replay", account_id: str = "account") -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.dir = os.path.join(replay_dir, f"{stamp}_{account_id}")
        os.makedirs(self.dir, exist_ok=True)
        self.account_id = account_id
        self._count = 0
        self._meta = {
            "account": account_id,
            "started_at": time.time(),
            "steps": 0,
            "status": "running",
        }
        self._save_meta()
        logger.info("Replay 开始: %s", self.dir)

    def _save_meta(self) -> None:
        with open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=1, default=str)

    def record_step(self, screenshot: Optional[bytes], state: Dict[str, Any],
                    decision: Dict[str, Any], result: Dict[str, Any]) -> int:
        """记录一步: 截图 + 状态 + 决策 + 结果。返回步骤号。"""
        self._count += 1
        n = self._count
        idx = f"{n:03d}"
        # 状态/决策 JSON
        with open(os.path.join(self.dir, f"state_{idx}.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1, default=str)
        with open(os.path.join(self.dir, f"action_{idx}.json"), "w", encoding="utf-8") as f:
            json.dump({"decision": decision, "result": result}, f,
                      ensure_ascii=False, indent=1, default=str)
        # 截图(有则保存)
        if screenshot is not None:
            try:
                from PIL import Image  # type: ignore
                import numpy as np  # type: ignore
                size = state.get("_size")
                if size:
                    w, h = size
                    arr = np.frombuffer(screenshot, dtype=np.uint8).reshape(h, w, 3)
                    Image.frombytes("RGB", (w, h), arr.tobytes()).save(
                        os.path.join(self.dir, f"screenshot_{idx}.png"))
            except Exception as e:
                logger.warning("Replay 截图保存失败: %s", e)
        self._meta["steps"] = n
        self._save_meta()
        return n

    def finish(self, status: str = "completed", note: str = "") -> None:
        """结束记录。"""
        self._meta["status"] = status
        self._meta["ended_at"] = time.time()
        self._meta["duration"] = round(time.time() - self._meta["started_at"], 1)
        if note:
            self._meta["note"] = note
        self._save_meta()
        logger.info("Replay 结束: %s (%s, %d 步)", self.dir, status, self._count)

    @property
    def path(self) -> str:
        return self.dir

    @property
    def step_count(self) -> int:
        return self._count


class ReplayPlayer:
    """回放一次运行记录。"""

    def __init__(self, replay_dir: str) -> None:
        self.dir = replay_dir

    def list_steps(self) -> List[int]:
        """列出所有步骤号。"""
        import re
        steps = []
        for f in os.listdir(self.dir):
            m = re.match(r"state_(\d+)\.json", f)
            if m:
                steps.append(int(m.group(1)))
        return sorted(steps)

    def get_step(self, n: int) -> Dict[str, Any]:
        """读取第 n 步的完整记录。"""
        idx = f"{n:03d}"
        step: Dict[str, Any] = {"step": n}
        for key, fname in (("state", f"state_{idx}.json"),
                           ("action", f"action_{idx}.json")):
            path = os.path.join(self.dir, fname)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    step[key] = json.load(f)
        shot = os.path.join(self.dir, f"screenshot_{idx}.png")
        if os.path.exists(shot):
            step["screenshot"] = shot
        return step

    def meta(self) -> Dict[str, Any]:
        path = os.path.join(self.dir, "meta.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
