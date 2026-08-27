# -*- coding: utf-8 -*-
"""长期记忆 (Phase 8, 规格书 §19/§20)。

记录: 任务经验/NPC位置/成功路径/失败原因/物品价格。
经验学习(§20): best_action / success_rate / execution_time。
存储: SQLite(本地持久化)。
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LongTermMemory:
    """本地 SQLite 长期记忆。"""

    def __init__(self, db_path: str = "memory.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self) -> None:
        c = self._conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS task_experience (id INTEGER PRIMARY KEY AUTOINCREMENT, task_name TEXT NOT NULL, action TEXT NOT NULL, success_count INTEGER DEFAULT 0, fail_count INTEGER DEFAULT 0, total_time REAL DEFAULT 0, last_result TEXT DEFAULT '', updated_at REAL DEFAULT 0)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task ON task_experience(task_name)")
        c.execute("CREATE TABLE IF NOT EXISTS npc_location (id INTEGER PRIMARY KEY AUTOINCREMENT, npc_name TEXT UNIQUE NOT NULL, map_name TEXT DEFAULT '', x INTEGER DEFAULT 0, y INTEGER DEFAULT 0, found_count INTEGER DEFAULT 0, updated_at REAL DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS item_price (id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT UNIQUE NOT NULL, min_price INTEGER DEFAULT 0, max_price INTEGER DEFAULT 0, samples INTEGER DEFAULT 0, updated_at REAL DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_name TEXT NOT NULL, rounds INTEGER DEFAULT 0, status TEXT DEFAULT '', duration REAL DEFAULT 0, note TEXT DEFAULT '', created_at REAL DEFAULT 0)")
        self._conn.commit()

    # ---------------- 任务经验(§20) ----------------
    def record_action(self, task_name: str, action: str, success: bool,
                      duration: float = 0.0) -> None:
        c = self._conn.cursor()
        c.execute("SELECT id, success_count, fail_count, total_time FROM task_experience WHERE task_name=? AND action=?", (task_name, action))
        row = c.fetchone()
        now = time.time()
        if row is None:
            c.execute("INSERT INTO task_experience (task_name, action, success_count, fail_count, total_time, last_result, updated_at) VALUES (?,?,?,?,?,?,?)",
                      (task_name, action, 1 if success else 0, 0 if success else 1, duration, "成功" if success else "失败", now))
        else:
            _, sc, fc, tt = row
            c.execute("UPDATE task_experience SET success_count=?, fail_count=?, total_time=?, last_result=?, updated_at=? WHERE id=?",
                      (sc + (1 if success else 0), fc + (0 if success else 1), tt + duration, "成功" if success else "失败", now, row[0]))
        self._conn.commit()

    def best_action(self, task_name: str) -> Optional[str]:
        c = self._conn.cursor()
        c.execute("SELECT action FROM task_experience WHERE task_name=? ORDER BY (success_count*1.0/(success_count+fail_count+1)) DESC LIMIT 1", (task_name,))
        row = c.fetchone()
        return row[0] if row else None

    def task_stats(self, task_name: str) -> List[Dict[str, Any]]:
        c = self._conn.cursor()
        c.execute("SELECT action, success_count, fail_count, total_time FROM task_experience WHERE task_name=? ORDER BY success_count DESC", (task_name,))
        return [{"action": r[0], "success": r[1], "fail": r[2], "time": round(r[3], 1)} for r in c.fetchall()]

    # ---------------- NPC 位置 ----------------
    def record_npc(self, npc_name: str, map_name: str = "", x: int = 0, y: int = 0) -> None:
        c = self._conn.cursor()
        now = time.time()
        c.execute("INSERT INTO npc_location (npc_name, map_name, x, y, found_count, updated_at) VALUES (?,?,?,?,1,?) ON CONFLICT(npc_name) DO UPDATE SET map_name=excluded.map_name, x=excluded.x, y=excluded.y, found_count=found_count+1, updated_at=excluded.updated_at", (npc_name, map_name, x, y, now))
        self._conn.commit()

    def get_npc(self, npc_name: str) -> Optional[Dict[str, Any]]:
        c = self._conn.cursor()
        c.execute("SELECT npc_name, map_name, x, y, found_count FROM npc_location WHERE npc_name=?", (npc_name,))
        row = c.fetchone()
        if row is None:
            return None
        return {"name": row[0], "map": row[1], "x": row[2], "y": row[3], "found": row[4]}

    # ---------------- 物品价格 ----------------
    def record_price(self, item_name: str, price: int) -> None:
        c = self._conn.cursor()
        now = time.time()
        c.execute("INSERT INTO item_price (item_name, min_price, max_price, samples, updated_at) VALUES (?,?,?,1,?) ON CONFLICT(item_name) DO UPDATE SET min_price=MIN(min_price, excluded.min_price), max_price=MAX(max_price, excluded.max_price), samples=samples+1, updated_at=excluded.updated_at", (item_name, price, price, now))
        self._conn.commit()

    def get_price(self, item_name: str) -> Optional[Dict[str, int]]:
        c = self._conn.cursor()
        c.execute("SELECT min_price, max_price, samples FROM item_price WHERE item_name=?", (item_name,))
        row = c.fetchone()
        if row is None:
            return None
        return {"min": row[0], "max": row[1], "samples": row[2]}

    # ---------------- 任务运行记录 ----------------
    def record_run(self, task_name: str, rounds: int, status: str, duration: float, note: str = "") -> None:
        c = self._conn.cursor()
        c.execute("INSERT INTO task_runs (task_name, rounds, status, duration, note, created_at) VALUES (?,?,?,?,?,?)", (task_name, rounds, status, duration, note, time.time()))
        self._conn.commit()

    def recent_runs(self, task_name: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        c = self._conn.cursor()
        if task_name:
            c.execute("SELECT task_name, rounds, status, duration, note, created_at FROM task_runs WHERE task_name=? ORDER BY id DESC LIMIT ?", (task_name, limit))
        else:
            c.execute("SELECT task_name, rounds, status, duration, note, created_at FROM task_runs ORDER BY id DESC LIMIT ?", (limit,))
        return [{"task": r[0], "rounds": r[1], "status": r[2], "duration": round(r[3], 1), "note": r[4]} for r in c.fetchall()]

    # ---------------- 统计 ----------------
    def stats(self) -> Dict[str, Any]:
        c = self._conn.cursor()
        tables = ["task_experience", "npc_location", "item_price", "task_runs"]
        counts = []
        for t in tables:
            c.execute("SELECT COUNT(*) FROM " + t)
            counts.append(c.fetchone()[0])
        return {"task_experience": counts[0], "npc_locations": counts[1],
                "item_prices": counts[2], "task_runs": counts[3]}

    def close(self) -> None:
        self._conn.close()
