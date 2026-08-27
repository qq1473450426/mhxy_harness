# -*- coding: utf-8 -*-
"""每账号独立日志系统 (规格书 §31/§32)。

logs/
├── account_01/
│   ├── run_20260827_013000.log
│   └── screenshots/
├── account_02/
│   ...
"""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from automation.window import WindowInfo
from vision.capture import capture_to_png


class AccountLogger:
    """单个账号的日志 + 截图 + 决策记录。"""

    def __init__(self, account_id: str, log_dir: str,
                 level: int = logging.INFO,
                 max_bytes: int = 5 * 1024 * 1024,
                 backup_count: int = 3) -> None:
        self.account_id = account_id
        self.dir = os.path.join(log_dir, account_id)
        os.makedirs(self.dir, exist_ok=True)
        self.shot_dir = os.path.join(self.dir, "screenshots")
        os.makedirs(self.shot_dir, exist_ok=True)

        self.logger = logging.getLogger(f"mhxy.account.{account_id}")
        self.logger.setLevel(level)
        self.logger.propagate = False
        if not self.logger.handlers:
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
            fh = RotatingFileHandler(
                os.path.join(self.dir, "run.log"),
                maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)

    # ---------------- 日志 ----------------
    def info(self, msg: str) -> None:
        self.logger.info(msg)

    def warn(self, msg: str) -> None:
        self.logger.warning(msg)

    def error(self, msg: str) -> None:
        self.logger.error(msg)

    # ---------------- 截图 ----------------
    def save_screenshot(self, win: WindowInfo, tag: str = "") -> str:
        """保存当前窗口截图, 返回文件路径。"""
        import time
        fname = time.strftime("%Y%m%d_%H%M%S") + (f"_{tag}" if tag else "") + ".png"
        path = os.path.join(self.shot_dir, fname)
        ok = capture_to_png(win, path)
        return path if ok else ""

    # ---------------- AI 决策记录(规格书 §32) ----------------
    def record_decision(self, state: Dict[str, Any], decision: Dict[str, Any],
                        result: Dict[str, Any]) -> None:
        """记录一次 Agent 决策日志(JSONL)。"""
        row = {
            "account": self.account_id,
            "state": state,
            "decision": decision,
            "result": result,
        }
        with open(os.path.join(self.dir, "decisions.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + chr(10))

    # ---------------- 异常 ----------------
    def record_anomaly(self, anomaly: Dict[str, Any]) -> None:
        with open(os.path.join(self.dir, "anomalies.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(anomaly, ensure_ascii=False, default=str) + chr(10))
        self.error(f"异常: {anomaly}")
