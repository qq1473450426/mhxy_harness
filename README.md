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

也可以双击 `start_desktop.bat`。

**开发/实际控制测试时，建议以管理员身份启动 PyCharm 或终端。** 如果游戏进程以管理员权限运行，而控制程序不是同等级权限，Windows UIPI 可能阻止输入注入。

## 第一次真实测试：师门单步模式

不要直接启动完整自动循环。先用“执行一步”验证每个状态和点击位置。

1. 手动启动游戏并完成登录，进入游戏主界面。
2. 以管理员身份启动 PyCharm。
3. 运行 `python -m desktop`。
4. 打开“游戏窗口”，点击“刷新窗口”。
5. 选择 `梦幻西游 ONLINE`，点击“绑定选中窗口”。
6. 打开“任务控制”，选择“师门”。
7. **先点击“执行一步”。**
8. 如果右侧任务追踪识别到“师父”，Agent 会生成 `CLICK_NPC("师父")`，Resolver 从 OCR 坐标解析目标，InputDriver 用 pywin32 移动并点击。
9. 游戏出现 NPC 对话框后，再点击“执行一步”。识别到“师门任务”后会生成 `DIALOG_CHOICE("师门任务")` 并点击该选项。
10. 每一步确认截图、日志、鼠标位置和游戏状态正确后，再使用“附着并启动真实任务”。

单步模式的执行链：

```text
MSS 截图
  ↓
右侧任务/中下部对话 ROI OCR
  ↓
GameState
  ↓
ShimenTask
  ↓
语义 Action
  ↓
CoordinateResolver
  ↓
pywin32 InputDriver
  ↓
真实游戏窗口
```

## OCR ROI

默认 OCR 不扫描整个游戏窗口，而是扫描两个归一化区域：

- 右侧任务追踪区域：识别“师门任务 / 师父”等任务目标。
- 中下部对话区域：识别 NPC 对话和“师门任务”等选项。

左侧聊天框不进入常规 OCR，减少无关文本和 OCR 耗时。OCR 结果会自动恢复为完整游戏窗口坐标，因此 Resolver 和输入层无需知道截图被裁剪过。

## 真实输入

桌面分支默认：

```yaml
input:
  backend: win32
  move_duration: 0.08
```

`automation/input_driver.py` 使用 `pywin32` 的 `SetCursorPos`、Windows 鼠标事件和键盘事件。鼠标移动采用短时间分段移动，方便调试时观察轨迹。

## 桌面端页面

| 页面 | 用途 |
| --- | --- |
| 总览 | GameRunner、客户端、队伍和 Agent 状态 |
| 游戏窗口 | 枚举、选择、绑定、置前游戏窗口 |
| 任务控制 | 师门/抓鬼/封妖、单步、自动启动、停止和鼠标测试 |
| 五开管理 | 队长状态、人工暂停/恢复 |
| 视觉/调试 | 实时游戏窗口截图和视觉信息 |
| 训练/优化 | 本地模拟 RL 训练 |

## 师门状态机

当前真实执行链已经接入：

```text
INIT
 ↓
识别任务追踪“师父”
 ↓
CLICK_NPC("师父")
 ↓
识别 NPC 对话
 ↓
DIALOG_CHOICE("师门任务")
 ↓
RUN / INTERACT / SUBMIT / VERIFY
```

任务只产生语义目标，不直接携带屏幕坐标：

```text
Task → Decision(target="师父") → CoordinateResolver → InputDriver
```

每个 Agent 都拥有独立任务状态机，避免五开时共享同一个师门任务环数状态。

## 五开

Harness 原有 `Coordinator` 负责 Leader / Backup Leader、多账号窗口绑定、Agent 并发、同步、单账号人工接管和队长异常切换。

当前桌面端默认只启用 `account_01`。先验证单账号真实闭环，再逐个启用其他账号，避免多个相同标题窗口造成错误绑定。

## YOLO / GPU

YOLO 是可选能力。师门基础文字流程优先使用 MSS + ROI OCR + 状态机，不在每个文字识别周期无条件运行 YOLO，避免视觉检测成为主循环瓶颈。需要目标检测时再启用 YOLO。

## 安全边界

- 游戏账号登录仍由用户手动完成。
- 不在桌面 UI 中保存或自动填写账号密码。
- 自动执行游戏任务可能违反游戏服务条款并带来账号风险，请自行承担使用风险。

## 关键目录

```text
core/                 Agent、Brain、Coordinator、StateMachine、RL
automation/           Windows 窗口、生命周期、pywin32 输入
vision/               MSS 截图、OCR、检测、跟踪
tasks/                师门/抓鬼/封妖状态机
desktop/              PySide6 原生桌面端
game_runner.py        桌面端直接使用的自主编排器
config.yaml           本地运行配置
start_desktop.bat     Windows 桌面启动器
```

## 从 Web 架构迁移

桌面端直接调用 Harness Core：

```text
PySide6 UI
   ↓
GameRunner / Coordinator
   ↓
Harness Core
```

不经过 HTTP/WebSocket。历史 Web 文件暂时保留作为迁移参考，待桌面端真实闭环稳定后再清理。
