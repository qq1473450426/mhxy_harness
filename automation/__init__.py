"""automation 包: Windows 窗口管理 + 统一输入驱动。"""
from .window import WindowManager, WindowInfo, WindowError, WindowLost  # noqa: F401
from .input_driver import InputDriver, Action, ActionResult  # noqa: F401
