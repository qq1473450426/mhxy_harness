# 梦幻西游五开本地 AI 自动任务系统 · PySide6 Desktop

> 当前桌面端开发分支：`feat/pyside6-desktop`
>
> 目标是把现有 Harness 的视觉、任务、Agent、状态机、执行器、五开协调和训练能力直接接入 Windows 原生 PySide6，不再依赖浏览器作战台。

## 当前桌面端入口

Windows 10/11 + Python 3.11+：

```powershell
python -m pip install -r requirements.txt
python -m desktop
```

也可以双击：

```text
start_desktop.bat
```

**开发/实际控制测试时，建议以管理员身份启动 PyCharm 或终端。**如果游戏进程以管理员权限运行，而控制程序不是同等级权限，Windows UIPI 可能阻止输入注入。

## 桌面端工作流

```text
启动游戏并手动完成登录
        ↓
PySide6「游戏窗口」刷新
        ↓
选择目标窗口并绑定
        ↓
「任务控制」选择任务
        ↓
附着并启动真实任务
        ↓
Harness GameRunner
        ↓
Vision → Brain/Planner → StateMachine → Executor
        ↓
pywin32 Windows 输入
        ↓
真实游戏窗口
```

桌面端的「附着」模式不会为了执行任务重新启动已经打开的游戏，也不会在停止任务时主动关闭用户手工启动的游戏。

## 桌面端页面

| 页面 | 用途 |
| --- | --- |
| 总览 | GameRunner、客户端、队伍和 Agent 状态 |
| 游戏窗口 | 枚举、选择、绑定、置前游戏窗口 |
| 任务控制 | 师门/抓鬼/封妖等任务启动、停止和鼠标测试 |
| 五开管理 | 队长状态、人工暂停/恢复 |
| 视觉/调试 | 实时游戏窗口截图和视觉信息 |
| 训练/优化 | 本地模拟 RL 训练 |

## 真实输入

桌面分支默认：

```yaml
input:
  backend: win32
  move_duration: 0.08
```

`automation/input_driver.py` 使用 `pywin32` 的 `SetCursorPos`、鼠标事件和键盘事件。鼠标移动采用短时间分段移动，方便调试时观察轨迹。

## 视觉

主截图使用 MSS。OCR 使用 RapidOCR。YOLO 是可选能力，不应该在每一个任务文字识别周期无条件运行；需要目标检测时才调用模型。

```yaml
vision:
  capture_backend: mss
  ocr_backend: rapidocr
```

## 五开

Harness 原有 `Coordinator` 负责：

- Leader / Backup Leader
- 多账号窗口绑定
- Agent 并发运行
- Leader/Follower 同步
- 单账号人工接管
- 队长异常切换

当前桌面端优先验证**单窗口真实执行闭环**，再逐步开放五开实际控制，避免多个相同标题窗口被错误绑定到同一账号。

## 安全边界

- 游戏账号登录仍由用户手动完成。
- 配置默认只启用 `account_01`，其余账号关闭，先验证单账号真实执行。
- 不在桌面 UI 中保存或自动填写账号密码。
- 自动执行游戏任务可能违反游戏服务条款并带来账号风险，请自行承担使用风险。

## 关键目录

```text
core/                 Agent、Brain、Coordinator、StateMachine、RL
automation/           Windows 窗口、生命周期、pywin32 输入
vision/               MSS 截图、OCR、检测、跟踪
tasks/                任务实现
desktop/              PySide6 原生桌面端
game_runner.py        桌面端直接使用的自主编排器
config.yaml           本地运行配置
start_desktop.bat     Windows 桌面启动器
```

## 从 Web 架构迁移

旧版本仍保留历史 Web 入口文件作为迁移参考，但桌面端不再通过 HTTP/WebSocket 控制核心。最终目标是：

```text
PySide6 UI
   ↓
GameRunner / Coordinator
   ↓
Harness Core
```

而不是：

```text
Browser → FastAPI → WebSocket → Harness Core
```

在桌面端稳定完成真实窗口、视觉、任务和输入闭环后，再清理不再需要的 Web 层文件。
