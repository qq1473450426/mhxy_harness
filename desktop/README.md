# PySide6 Desktop

`desktop` 是 `mhxy_harness` 的原生 Windows 桌面入口。它直接调用现有 `core/`、`automation/`、`vision/`、`tasks/` 和 `game_runner.py`，不再需要浏览器作战台才能控制。

## 启动

建议以管理员权限启动 PyCharm/PowerShell，再在仓库根目录执行：

```powershell
python -m desktop
```

或双击根目录 `run_desktop.bat`。

## 当前能力

- 发现并选择梦幻西游窗口
- 调用现有 `GameRunner` 启动/停止真实任务
- 实时查看 Harness 状态
- 调用已有 RL 优化入口
- 保留现有核心任务、视觉、输入、多账号协调能力

## 后续桌面化方向

下一阶段将继续把现有 Web 作战台功能逐项迁移到 PySide6：账号卡片、任务状态、视觉预览、战斗监控、人工接管/恢复、Replay 和日志，并统一由桌面 UI 直接调用核心模块。
