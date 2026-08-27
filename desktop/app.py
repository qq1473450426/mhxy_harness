# -*- coding: utf-8 -*-
"""MHXY Harness 原生 Windows 桌面控制台。"""
from __future__ import annotations
import json, sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication,QComboBox,QFormLayout,QGroupBox,QHBoxLayout,QLabel,
    QLineEdit,QListWidget,QMainWindow,QPlainTextEdit,QPushButton,QSpinBox,QStackedWidget,QVBoxLayout,QWidget,QMessageBox)

class HarnessDesktop(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("MHXY Harness - PySide6 Desktop"); self.resize(1320,820)
        self.settings={}; self.runner=None; self.wm=None; self.windows=[]; self.bound=None
        self._build_ui(); self._load_backend(); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh_runtime); self.timer.start(700)

    def _build_ui(self):
        root=QWidget(); root_l=QHBoxLayout(root); self.setCentralWidget(root)
        self.nav=QListWidget(); self.nav.addItems(["总览","游戏窗口","任务控制","五开管理","视觉/调试","训练/优化"]); self.nav.setFixedWidth(150); root_l.addWidget(self.nav)
        self.stack=QStackedWidget(); root_l.addWidget(self.stack,1)
        self.stack.addWidget(self._overview_page()); self.stack.addWidget(self._window_page()); self.stack.addWidget(self._task_page()); self.stack.addWidget(self._team_page()); self.stack.addWidget(self._vision_page()); self.stack.addWidget(self._train_page())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0)

    def _page(self,title):
        w=QWidget(); l=QVBoxLayout(w); h=QLabel(title); h.setStyleSheet("font-size:18px;font-weight:bold;"); l.addWidget(h); return w,l
    def _overview_page(self):
        w,l=self._page("MHXY Harness · 本地桌面控制台")
        self.overview=QPlainTextEdit(); self.overview.setReadOnly(True); l.addWidget(self.overview); return w
    def _window_page(self):
        w,l=self._page("游戏窗口")
        box=QGroupBox("Windows 游戏窗口"); f=QFormLayout(box); self.window_box=QComboBox(); f.addRow("检测到的窗口",self.window_box); l.addWidget(box)
        row=QHBoxLayout(); self.refresh_btn=QPushButton("刷新窗口"); self.bind_btn=QPushButton("绑定选中窗口"); self.front_btn=QPushButton("置前"); row.addWidget(self.refresh_btn); row.addWidget(self.bind_btn); row.addWidget(self.front_btn); l.addLayout(row)
        self.refresh_btn.clicked.connect(self.refresh_windows); self.bind_btn.clicked.connect(self.bind_window); self.front_btn.clicked.connect(self.front_window)
        self.window_info=QPlainTextEdit(); self.window_info.setReadOnly(True); l.addWidget(self.window_info); return w
    def _task_page(self):
        w,l=self._page("任务控制")
        box=QGroupBox("真实执行"); f=QFormLayout(box); self.task_box=QComboBox(); self.task_box.addItem("师门", "shimen"); self.task_box.addItem("抓鬼", "zhuagui"); self.task_box.addItem("封妖", "fengyao"); self.goal=QLineEdit("完成师门任务"); f.addRow("任务",self.task_box); f.addRow("目标",self.goal); l.addWidget(box)
        row=QHBoxLayout(); self.start_btn=QPushButton("附着并启动真实任务"); self.stop_btn=QPushButton("停止"); self.manual_btn=QPushButton("测试鼠标移动"); row.addWidget(self.start_btn); row.addWidget(self.stop_btn); row.addWidget(self.manual_btn); l.addLayout(row)
        self.x=QSpinBox(); self.y=QSpinBox(); self.x.setRange(0,10000); self.y.setRange(0,10000); rf=QFormLayout(); rf.addRow("窗口相对 X",self.x); rf.addRow("窗口相对 Y",self.y); l.addLayout(rf)
        self.start_btn.clicked.connect(self.start_task); self.stop_btn.clicked.connect(self.stop_task); self.manual_btn.clicked.connect(self.test_mouse); self.task_log=QPlainTextEdit(); self.task_log.setReadOnly(True); l.addWidget(self.task_log); return w
    def _team_page(self):
        w,l=self._page("五开管理"); self.team_view=QPlainTextEdit(); self.team_view.setReadOnly(True); l.addWidget(self.team_view); row=QHBoxLayout(); self.pause=QPushButton("暂停队长"); self.resume=QPushButton("恢复队长"); row.addWidget(self.pause); row.addWidget(self.resume); l.addLayout(row); self.pause.clicked.connect(lambda:self._pause(True)); self.resume.clicked.connect(lambda:self._pause(False)); return w
    def _vision_page(self):
        w,l=self._page("视觉 / 调试"); self.preview=QLabel("暂无游戏截图"); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumHeight(420); self.preview.setStyleSheet("border:1px solid #aaa;"); l.addWidget(self.preview); self.vision_log=QPlainTextEdit(); self.vision_log.setReadOnly(True); l.addWidget(self.vision_log); return w
    def _train_page(self):
        w,l=self._page("训练 / 优化"); row=QHBoxLayout(); self.episodes=QSpinBox(); self.episodes.setRange(1,100000); self.episodes.setValue(300); self.opt_btn=QPushButton("开始模拟训练"); row.addWidget(QLabel("Episodes")); row.addWidget(self.episodes); row.addWidget(self.opt_btn); l.addLayout(row); self.train_log=QPlainTextEdit(); self.train_log.setReadOnly(True); l.addWidget(self.train_log); self.opt_btn.clicked.connect(self.optimize); return w

    def _load_backend(self):
        try:
            from core.config import load_config, load_env
            from game_runner import GameRunner
            from automation.window import WindowManager
            load_env(); self.settings=load_config("config.yaml"); self.runner=GameRunner(self.settings,dry_run=False); self.wm=WindowManager(); self._log("Harness 核心已加载"); self.refresh_windows()
        except Exception as exc: QMessageBox.critical(self,"启动失败",str(exc)); self._log("核心加载失败: "+str(exc))
    def _log(self,text):
        if hasattr(self,'task_log'): self.task_log.appendPlainText(text)
    def refresh_windows(self):
        if not self.wm: return
        try:
            self.windows=self.wm.find_game_windows(); self.window_box.clear()
            for win in self.windows: self.window_box.addItem(f"{win.title}  [HWND={win.hwnd}]",win)
            self.window_info.setPlainText("\n".join(f"{i}: {w.title} | hwnd={w.hwnd} | rect={w.rect}" for i,w in enumerate(self.windows)) or "未发现游戏窗口")
        except Exception as exc: self._log("刷新窗口失败: "+str(exc))
    def bind_window(self):
        self.bound=self.window_box.currentData()
        if not self.bound: self._log("没有选择游戏窗口"); return
        ok=self.wm.activate(self.bound); self._log(f"已绑定: {self.bound.title} hwnd={self.bound.hwnd}，置前={'成功' if ok else '失败'}")
    def front_window(self):
        if self.bound: self._log(f"置前: {'成功' if self.wm.activate(self.bound) else '失败'}")
    def start_task(self):
        if not self.bound: self.bind_window()
        if not self.bound: return
        task=self.task_box.currentData(); ok=self.runner.start_attached(self.bound,task,self.goal.text().strip(),True)
        self._log(f"附着真实任务: {'成功' if ok else '失败'} task={task}")
    def stop_task(self):
        if self.runner: self.runner.stop(); self._log("已请求停止")
    def test_mouse(self):
        if not self.bound: self.bind_window()
        if not self.bound: return
        try:
            from automation.input_driver import InputDriver
            d=InputDriver(self.bound,backend="win32",move_duration=0.35); r=d.move(self.x.value(),self.y.value(),"桌面鼠标测试")
            self._log(f"鼠标移动 {'成功' if r.ok else '失败'}: 窗口({self.x.value()},{self.y.value()}) -> 屏幕{d.to_abs(self.x.value(),self.y.value())}; {r.error or ''}")
        except Exception as exc: self._log("鼠标测试失败: "+str(exc))
    def _pause(self,resume):
        if not self.runner or not self.runner.coordinator: return
        aid=self.runner.coordinator.team.leader
        ok=self.runner.resume_account(aid) if resume else self.runner.pause_account(aid); self._log(f"账号 {aid} {'恢复' if resume else '暂停'}: {'成功' if ok else '失败'}")
    def optimize(self):
        self.opt_btn.setEnabled(False); self.train_log.appendPlainText("训练开始...")
        from threading import Thread
        def work():
            result=self.runner.optimize(self.episodes.value()); self.train_log.appendPlainText(json.dumps(result,ensure_ascii=False,indent=2)); self.opt_btn.setEnabled(True)
        Thread(target=work,daemon=True).start()
    def refresh_runtime(self):
        if not self.runner: return
        try:
            st=self.runner.status(); self.overview.setPlainText(json.dumps(st,ensure_ascii=False,indent=2,default=str)); self.team_view.setPlainText(json.dumps(st.get('accounts',{}),ensure_ascii=False,indent=2,default=str))
            if self.bound and self.bound.is_valid():
                from vision.capture import capture_window
                data,(ww,hh)=capture_window(self.bound); img=QImage(data,ww,hh,ww*3,QImage.Format_RGB888); self.preview.setPixmap(QPixmap.fromImage(img).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
                self.vision_log.setPlainText(f"窗口={self.bound.title}\nHWND={self.bound.hwnd}\n截图={ww}x{hh}")
        except Exception as exc: self.vision_log.setPlainText("运行状态读取失败: "+str(exc))
    def closeEvent(self,event):
        if self.runner: self.runner.stop()
        event.accept()

def main():
    app=QApplication.instance() or QApplication(sys.argv); win=HarnessDesktop(); win.show(); return app.exec()

if __name__ == "__main__": raise SystemExit(main())
