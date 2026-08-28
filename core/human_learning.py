# -*- coding: utf-8 -*-
"""人类示范 + 轻量离线 RL。

设计目标：先让用户亲自完成一遍师门任务，程序只监听绑定游戏窗口中的鼠标/键盘
动作并保存与动作对应的视觉快照；随后用示范轨迹初始化策略，再用奖励回报做
Monte-Carlo/Q 值更新。这样不要求第一遍任务与第二遍像素完全一致，多遍示范会
自然增加 replay buffer，并由最近视觉状态匹配选择动作。

这不是“用随机 Q-learning 直接从零学会梦幻西游”。真实游戏状态空间过大，第一版
采用更稳妥的 offline demonstration RL：行为示范负责探索，奖励负责筛选/强化动作。
后续可以把 state_encoder 换成 YOLO/OCR embedding，而不改变录制与训练接口。
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class DemoAction:
    ts: float
    kind: str
    x: Optional[int] = None
    y: Optional[int] = None
    key: Optional[str] = None
    mods: Optional[List[str]] = None
    state_file: str = ""


class HumanDemoRecorder:
    """监听绑定游戏窗口，记录用户动作和低频视觉快照。"""

    def __init__(self, win, root: str = "learning/demos", sample_hz: float = 4.0) -> None:
        self.win = win
        self.root = root
        self.sample_hz = max(1.0, float(sample_hz))
        self.session_dir = ""
        self.actions: List[DemoAction] = []
        self._running = False
        self._mouse_hook = None
        self._keyboard_hook = None
        self._sampler: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[Tuple[float, bytes, int, int]] = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> str:
        if self._running:
            return self.session_dir
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.root, stamp)
        os.makedirs(self.session_dir, exist_ok=True)
        self.actions = []
        self._running = True
        self._sampler = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()
        try:
            import mouse  # type: ignore
            import keyboard  # type: ignore
            self._mouse_hook = mouse.hook(self._on_mouse)
            self._keyboard_hook = keyboard.hook(self._on_keyboard)
        except Exception:
            self.stop()
            raise
        self._write_meta({"status": "recording", "started_at": time.time(), "hwnd": self.win.hwnd})
        return self.session_dir

    def stop(self) -> str:
        if not self._running:
            return self.session_dir
        self._running = False
        try:
            import mouse  # type: ignore
            import keyboard  # type: ignore
            if self._mouse_hook is not None:
                mouse.unhook(self._mouse_hook)
            if self._keyboard_hook is not None:
                keyboard.unhook(self._keyboard_hook)
        except Exception:
            pass
        if self._sampler is not None:
            self._sampler.join(timeout=1.0)
        self._save_actions()
        self._write_meta({
            "status": "completed", "ended_at": time.time(),
            "actions": len(self.actions), "hwnd": self.win.hwnd,
        })
        return self.session_dir

    def _inside(self, sx: int, sy: int) -> bool:
        try:
            return self.win.x <= sx < self.win.x + self.win.width and self.win.y <= sy < self.win.y + self.win.height
        except Exception:
            return False

    def _foreground_is_game(self) -> bool:
        try:
            import win32gui  # type: ignore
            return int(win32gui.GetForegroundWindow()) == int(self.win.hwnd)
        except Exception:
            return True

    def _on_mouse(self, event: Any) -> None:
        if not self._running or not self._foreground_is_game():
            return
        try:
            if getattr(event, "event_type", "") != "down" or getattr(event, "button", "") != "left":
                return
            sx, sy = int(event.x), int(event.y)
            if not self._inside(sx, sy):
                return
            x, y = sx - int(self.win.x), sy - int(self.win.y)
            frame = self._latest_frame
            state_file = self._save_action_frame(frame)
            with self._lock:
                self.actions.append(DemoAction(time.time(), "CLICK", x, y, state_file=state_file))
        except Exception:
            pass

    def _on_keyboard(self, event: Any) -> None:
        if not self._running or not self._foreground_is_game():
            return
        try:
            if getattr(event, "event_type", "") != "down":
                return
            # mouse/keyboard 库会产生 modifier 本身的 down；保留它们，训练时会过滤。
            name = str(getattr(event, "name", ""))
            if not name:
                return
            state_file = self._save_action_frame(self._latest_frame)
            with self._lock:
                self.actions.append(DemoAction(time.time(), "PRESS", key=name, state_file=state_file))
        except Exception:
            pass

    def _sample_loop(self) -> None:
        interval = 1.0 / self.sample_hz
        while self._running:
            started = time.time()
            try:
                from vision.capture import capture_window
                data, (w, h) = capture_window(self.win)
                self._latest_frame = (time.time(), data, w, h)
            except Exception:
                pass
            time.sleep(max(0.01, interval - (time.time() - started)))

    def _save_action_frame(self, frame: Optional[Tuple[float, bytes, int, int]]) -> str:
        if frame is None:
            return ""
        _, data, w, h = frame
        idx = len(self.actions) + 1
        path = os.path.join(self.session_dir, f"state_{idx:05d}.png")
        try:
            from PIL import Image  # type: ignore
            Image.frombytes("RGB", (w, h), data).save(path)
            return os.path.basename(path)
        except Exception:
            return ""

    def _save_actions(self) -> None:
        path = os.path.join(self.session_dir, "actions.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for item in self.actions:
                f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    def _write_meta(self, patch: Dict[str, Any]) -> None:
        path = os.path.join(self.session_dir, "meta.json")
        meta = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        meta.update(patch)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


class VisualDemoPolicy:
    """基于视觉状态最近邻的轻量策略，并维护 Q 值。"""

    def __init__(self, max_samples: int = 5000) -> None:
        self.samples: List[Dict[str, Any]] = []
        self.q: Dict[str, Dict[str, float]] = {}
        self.max_samples = max_samples
        self.alpha = 0.35
        self.gamma = 0.92

    @staticmethod
    def encode(frame: bytes, width: int, height: int) -> np.ndarray:
        arr = np.frombuffer(frame, dtype=np.uint8).reshape(height, width, 3)
        # 低分辨率灰度特征，避免每次推理调用 YOLO/OCR。
        import cv2  # type: ignore
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        return small.reshape(-1)

    @staticmethod
    def key(vec: np.ndarray) -> str:
        # 量化后作为 Q-table key，允许轻微渲染变化。
        q = np.clip(np.round(vec * 12), 0, 12).astype(np.uint8)
        return q.tobytes().hex()

    def add_demo(self, frame: bytes, width: int, height: int, action: DemoAction, reward: float) -> None:
        vec = self.encode(frame, width, height)
        act = self._action_id(action)
        self.samples.append({"vec": vec, "action": asdict(action), "action_id": act, "reward": float(reward)})
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]

    def train(self, passes: int = 8) -> Dict[str, Any]:
        if not self.samples:
            return {"ok": False, "error": "没有示范样本"}
        # Monte-Carlo return：一条完整示范越接近任务结尾，获得的回报越高。
        for _ in range(max(1, passes)):
            for i, sample in enumerate(self.samples):
                ret = float(sample["reward"])
                discount = 1.0
                for j in range(i + 1, min(len(self.samples), i + 80)):
                    discount *= self.gamma
                    ret += discount * float(self.samples[j]["reward"])
                key = self.key(sample["vec"])
                row = self.q.setdefault(key, {})
                old = row.get(sample["action_id"], 0.0)
                row[sample["action_id"]] = old + self.alpha * (ret - old)
        return {
            "ok": True,
            "samples": len(self.samples),
            "states": len(self.q),
            "actions": len({s["action_id"] for s in self.samples}),
        }

    def predict(self, frame: bytes, width: int, height: int, min_similarity: float = 0.82) -> Optional[Dict[str, Any]]:
        if not self.samples:
            return None
        vec = self.encode(frame, width, height)
        best = None
        best_dist = float("inf")
        # 只保留相似视觉状态的示范动作。
        for sample in self.samples:
            d = float(np.mean((vec - sample["vec"]) ** 2))
            if d < best_dist:
                best_dist = d
                best = sample
        similarity = max(0.0, 1.0 - math.sqrt(best_dist) * 1.8)
        if best is None or similarity < min_similarity:
            return None
        key = self.key(vec)
        qrow = self.q.get(key, {})
        action_id = max(qrow, key=qrow.get) if qrow else best["action_id"]
        # 从所有同类动作中选最接近当前画面的一个，减少坐标漂移。
        candidates = [s for s in self.samples if s["action_id"] == action_id]
        chosen = min(candidates or [best], key=lambda s: float(np.mean((vec - s["vec"]) ** 2)))
        result = dict(chosen["action"])
        result["similarity"] = round(similarity, 4)
        result["q"] = round(float(qrow.get(action_id, 0.0)), 3)
        return result

    @staticmethod
    def _action_id(action: DemoAction) -> str:
        if action.kind == "CLICK":
            # 40x40 网格化点击区域，让同一按钮附近的点击归为同类。
            return f"CLICK:{int(action.x or 0)//40}:{int(action.y or 0)//40}"
        return f"PRESS:{str(action.key or '').lower()}"

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {"samples": [], "q": self.q}
        for s in self.samples:
            payload["samples"].append({
                "vec": s["vec"].tolist(), "action": s["action"],
                "action_id": s["action_id"], "reward": s["reward"],
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "VisualDemoPolicy":
        obj = cls()
        if not os.path.exists(path):
            return obj
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        obj.q = payload.get("q", {})
        for s in payload.get("samples", []):
            s["vec"] = np.asarray(s["vec"], dtype=np.float32)
            obj.samples.append(s)
        return obj


class LearningScore:
    """一次自主运行的评分。"""

    @staticmethod
    def calculate(steps: int, successful_actions: int, failed_actions: int,
                  completed: bool, duration_s: float) -> Dict[str, Any]:
        efficiency = max(0.0, 1.0 - max(0, steps - 1) / max(1, steps + 40))
        reliability = successful_actions / max(1, successful_actions + failed_actions)
        score = 55.0 * (100.0 if completed else 35.0) / 100.0 + 30.0 * reliability + 15.0 * efficiency
        return {
            "score": round(score, 1), "completed": bool(completed),
            "steps": steps, "successful_actions": successful_actions,
            "failed_actions": failed_actions, "duration_s": round(duration_s, 2),
            "reliability": round(reliability, 3), "efficiency": round(efficiency, 3),
        }
