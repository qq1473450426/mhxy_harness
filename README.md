# 梦幻西游五开本地 AI 自动任务系统 · PySide6 Desktop

> 当前桌面端开发分支：`feat/pyside6-desktop`
>
> 目标是把 Harness 的视觉、任务、Agent、状态机、执行器、五开协调和学习能力直接接入 Windows 原生 PySide6。

## 当前桌面端入口

Windows 10/11 + Python 3.11+：

```powershell
python -m pip install -r requirements.txt
python -m desktop
```

实际控制测试时，建议以管理员身份启动 PyCharm 或终端；如果游戏进程权限高于控制程序，Windows UIPI 可能阻止输入注入。

## 人类示范 → RL 学习 → 自主运行

现在桌面端支持“用户先教一遍，程序再学习”的实验闭环：

```text
绑定游戏窗口
    ↓
开始示范学习
    ↓
用户自己操作师门任务
    ↓
程序只监听绑定游戏窗口中的鼠标/键盘
    ↓
保存动作 + 当时的视觉快照
    ↓
停止示范并标记“任务成功/未完成”
    ↓
训练示范策略
    ↓
多次示范累积 replay buffer
    ↓
Monte-Carlo 回报 + Q 值强化
    ↓
自主运行一次
    ↓
实时视觉最近邻匹配
    ↓
pywin32 真实鼠标/键盘输入
    ↓
动作验证 + 终态视觉匹配
    ↓
输出评分
```

### 为什么不是直接从零做像素级 Q-learning

梦幻西游的状态空间远大于当前的网格模拟环境，直接随机探索会非常慢且容易产生大量无意义动作。因此第一版采用 **offline demonstration RL**：

- 用户示范负责探索正确路径；
- 每个示范保存视觉状态和动作；
- 成功示范获得更高回报；
- 多次示范按 episode 分开计算 Monte-Carlo return；
- Q 值用于强化同一视觉状态下更可靠的动作；
- 自主运行只在视觉相似度达到阈值时执行，不满足匹配就停止，避免盲点。

这套设计允许后续把 `VisualDemoPolicy.encode()` 替换成 OCR/YOLO/深度视觉 embedding，而不用推翻录制、replay buffer 和桌面输入层。

## 示范数据

学习数据默认写入：

```text
learning/
├── demos/
│   └── 20260828_123456/
│       ├── state_00001.png
│       ├── state_00002.png
│       ├── ...
│       ├── terminal.png
│       ├── actions.jsonl
│       └── meta.json
└── policy.json
```

`actions.jsonl` 保存窗口相对坐标或按键，不保存账号密码。`terminal.png` 来自用户标记成功的示范结束画面，用于自主运行的轻量完成判断。

可以重复示范：

```text
第 1 遍：正常完成师门
第 2 遍：另一种师门任务
第 3 遍：再完成一次
...
```

训练器会把每一遍当成独立 episode，而不是把不同任务错误拼成一条轨迹。

## 第一次学习建议

1. 手动启动游戏并登录。
2. 以管理员身份启动 PyCharm。
3. `python -m desktop`。
4. “游戏窗口”→刷新→选择→绑定。
5. “训练/优化”→“开始示范学习”。
6. 切回游戏，**完全由你操作**完成一遍师门任务。
7. 完成后回到桌面端，点击“停止示范（任务成功）”。
8. 点击“训练示范策略”。
9. 再把游戏恢复到可开始下一遍师门任务的状态。
10. 点击“自主运行一次”，程序才会接管鼠标/键盘。
11. 查看评分：完成度、动作成功率、效率、总分。

第一次建议只录制**一遍完整、成功、没有异常弹窗的师门流程**；确认自主运行能复现后，再录第二遍、第三遍，让策略获得更多任务变化样本。

## 当前真实执行链：师门单步

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

先用“执行一步”验证点击位置，再启动完整自动任务。

## OCR ROI

默认 OCR 不扫描整个游戏窗口，而是扫描右侧任务追踪区域和中下部对话区域；左侧聊天框不进入常规 OCR，以减少无关文本和 OCR 耗时。

## 真实输入

桌面分支默认：

```yaml
input:
  backend: win32
  move_duration: 0.08
```

`automation/input_driver.py` 使用 `pywin32` 的 `SetCursorPos`、Windows 鼠标事件和键盘事件，鼠标移动采用分段移动，方便调试时观察轨迹。

## YOLO / GPU

YOLO 是可选能力。师门文字流程优先使用 MSS + ROI OCR + 状态机，不在每个识别周期无条件运行 YOLO，避免视觉检测成为主循环瓶颈。需要目标检测时再启用 YOLO。

## 桌面端页面

| 页面 | 用途 |
| --- | --- |
| 总览 | GameRunner、客户端、队伍和 Agent 状态 |
| 游戏窗口 | 枚举、选择、绑定、置前游戏窗口 |
| 任务控制 | 师门/抓鬼/封妖、单步、自动启动、停止和鼠标测试 |
| 五开管理 | 队长状态、人工暂停/恢复 |
| 视觉/调试 | 实时游戏窗口截图和视觉信息 |
| 训练/优化 | 人类示范学习、策略训练、自主运行评分、传统模拟 RL |

## 传统 RL 模拟环境

项目原有 `core/rl_env.py` / `core/rl_trainer.py` 仍保留一个 GridEnv + Q-learning 环境，用于验证 RL 接口；它与新增的真实游戏人类示范学习是两条不同路径。真实游戏学习入口使用 `core/human_learning.py`。

## 安全边界

- 游戏账号登录仍由用户手动完成。
- 不在桌面 UI 中保存或自动填写账号密码。
- 示范监听只接受当前绑定且处于前台的游戏窗口输入。
- 自主策略低于视觉相似度阈值时停止，不继续盲目执行。
- 自动执行游戏任务可能违反游戏服务条款并带来账号风险，请自行承担使用风险。

## 关键目录

```text
core/                 Agent、Brain、Coordinator、StateMachine、RL、Human Learning
automation/           Windows 窗口、生命周期、pywin32 输入
vision/               MSS 截图、OCR、检测、跟踪
tasks/                师门/抓鬼/封妖状态机
desktop/              PySide6 原生桌面端
game_runner.py        桌面端直接使用的自主编排器
learning/             本地示范数据和训练策略（运行时生成）
config.yaml           本地运行配置
start_desktop.bat     Windows 桌面启动器
```
