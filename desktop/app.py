# -*- coding: utf-8 -*-
"""PySide6 desktop controller for the existing MHXY harness.

This layer intentionally keeps the existing core/automation/vision/tasks code
and provides a native Windows desktop entry point instead of the legacy web UI.
"""
from __future__ import annotations

import sys
import threading
from typing import Any, Dict

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class HarnessDesktop(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MHXY Harness - PySide6 Desktop")
        self.resize(1280, 820)
        self.runner = None
        self.settings: Dict[str, Any] = {}
        self._build_ui()
        self._load_backend()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(1000)

    def _build_ui(self) -> None:
        root = QWidget()
        main = QHBoxLayout(root)
        self.setCentralWidget(root)

        self.nav = QListWidget()
        self.nav.addItems(["总览", "游戏窗口", "任务控制", "五开", "视觉/调试", "训练/优化"])
        self.nav.setFixedWidth(150)
        main.addWidget(self.nav)

        self.stack = QWidget()
        stack_layout = QVBoxLayout(self.stack)
        main.addWidget(self.stack, 1)

        self.page_title = QLabel("MHXY Harness")
        stack_layout.addWidget(self.page_title)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        controls = QGroupBox("真实游戏控制")
        form = QFormLayout(controls)
        self.window_box = QComboBox()
        self.task_box = QComboBox()
        self.task_box.addItems(["shimen", "抓鬼", "师门", "封妖"])
        self.account_box = QComboBox()
        self.goal_edit = QLineEdit("完成师门任务")
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(0, 1000000)
        self.steps_spin.setValue(0)
        form.addRow("游戏窗口", self.window_box)
        form.addRow("账号", self.account_box)
        form.addRow("任务", self.task_box)
        form.addRow("目标", self.goal_edit)
        form.addRow("最大步数(0=无限)", self.steps_spin)

        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新窗口")
        self.bind_btn = QPushButton("绑定窗口")
        self.start_btn = QPushButton("启动真实任务")
        self.stop_btn = QPushButton("停止")
        self.optimize_btn = QPushButton("训练优化")
        self.refresh_btn.clicked.connect(self.refresh_windows)
        self.bind_btn.clicked.connect(self.bind_selected)
        self.start_btn.clicked.connect(self.start_real)
        self.stop_btn.clicked.connect(self.stop_runner)
        self.optimize_btn.clicked.connect(self.optimize)
        for b in (self.refresh_btn, self.bind_btn, self.start_btn, self.stop_btn, self.optimize_btn):
            btns.addWidget(b)
        form_box = QVBoxLayout()
        form_box.addWidget(controls)
        form_box.addLayout(btns)
        stack_layout.addLayout(form_box)

        splitter = QSplitter()
        self.status_view = QPlainTextEdit()
        self.status_view.setReadOnly(True)
        splitter.addWidget(self.status_view)
        splitter.addWidget(self.log)
        stack_layout.addWidget(splitter, 1)

        self.nav.currentRowChanged.connect(self.on_nav)
        self.nav.setCurrentRow(0)

    def _load_backend(self) -> None:
        try:
            from core.config import load_config, load_env
            from game_runner import GameRunner
            load_env()
            self.settings = load_config("config.yaml")
            self.runner = GameRunner(self.settings, dry_run=False)
            self._append("已加载 mhxy_harness 核心引擎")
            self.refresh_windows()
            self.account_box.clear()
            for item in self.settings.get("accounts", {}).get("list", []):
                if item.get("enabled", False):
                    self.account_box.addItem(str(item.get("id", "")), item)
        except Exception as exc:
            self._append(f"核心加载失败: {exc}")
            QMessageBox.critical(self, "启动失败", str(exc))

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)

    def on_nav(self, index: int) -> None:
        self.page_title.setText(self.nav.item(index).text() if self.nav.item(index) else "MHXY Harness")

    def refresh_windows(self) -> None:
        try:
            from automation.window import WindowManager
            wins = WindowManager().find_game_windows()
            self.window_box.clear()
            for w in wins:
                self.window_box.addItem(f"{w.title}  [HWND={w.hwnd}]", w)
            self._append(f"发现 {len(wins)} 个游戏窗口")
        except Exception as exc:
            self._append(f"刷新窗口失败: {exc}")

    def bind_selected(self) -> None:
        win = self.window_box.currentData()
        if win is None:
            self._append("没有选中的游戏窗口")
            return
        self._append(f"已选择窗口: {win.title} rect={win.rect}")

    def start_real(self) -> None:
        if self.runner is None:
            return
        task = self.task_box.currentText()
        goal = self.goal_edit.text().strip()
        steps = self.steps_spin.value()
        if task == "师门":
            task = "shimen"
        ok = self.runner.start(task=task, goal=goal, auto=True)
        self._append(f"启动真实任务: {'成功' if ok else '失败'} task={task} goal={goal} steps={steps}")

    def stop_runner(self) -> None:
        if self.runner is not None:
            self.runner.stop()
            self._append("已请求停止任务")

    def optimize(self) -> None:
        if self.runner is None:
            return
        def work() -> None:
            result = self.runner.optimize(episodes=300)
            self.status_view.setPlainText(str(result))
            self._append(f"优化完成: {result}")
        threading.Thread(target=work, daemon=True).start()

    def refresh_status(self) -> None:
        if self.runner is None:
            return
        try:
            self.status_view.setPlainText(str(self.runner.status()))
        except Exception as exc:
            self._append(f"状态读取失败: {exc}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = HarnessDesktop()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
