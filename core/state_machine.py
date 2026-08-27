# -*- coding: utf-8 -*-
"""游戏状态机 (规格书 §6/§2 第二层)。

把 OCR 文本 + 窗口信息转换成标准 GameState。
规则优先(快), 复杂情况交给上层(LLM/规则扩展)。

识别关键词(可扩展, 配置化): 战斗/对话框/死亡/掉线/加载/登录...
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from .game_state import GameState, GameStatus

logger = logging.getLogger(__name__)

# 状态判定关键词(Level 4 语义, 可从配置文件扩展)
_STATUS_KEYWORDS = {
    GameStatus.BATTLE: ["战斗", "回合", "自动战斗", "逃跑"],
    GameStatus.TASK_DIALOG: ["请选择", "确认", "接受", "提交", "完成对话", "任务"],
    GameStatus.NPC_DIALOG: ["对话", "听说", "需要", "帮忙"],
    GameStatus.LOADING: ["加载", "读图中", "进入场景"],
    GameStatus.DEATH: ["死亡", "你已阵亡", "回到长安"],
    GameStatus.DISCONNECT: ["断开", "连接已断开", "网络异常", "重新连接"],
    GameStatus.LOGIN: ["登录", "账号", "输入密码", "选择服务器"],
    GameStatus.TEAM: ["队伍", "组队", "队长", "队员"],
    GameStatus.INVENTORY: ["背包", "物品", "道具"],
    GameStatus.TRADE: ["交易", "摆摊", "收购"],
}

# 地图关键词
_MAP_KEYWORDS = ["长安城", "建邺城", "傲来国", "长寿村", "宝象国", "朱紫国", "西梁女国",
                 "大唐国境", "大唐境外", "北俱芦洲", "东海湾", "沉船", "月宫", "天宫",
                 "龙宫", "普陀山", "化生寺", "方寸山", "女儿村", "魔王寨", "阴曹地府",
                 "狮驼岭", "盘丝洞", "五庄观", "地府", "大雁塔", "江南野外"]

# 坐标正则: X:304 Y:137 / 坐标(304,137)
_POS_RE = re.compile(r"X[:：]\s*(\d+)\s*Y[:：]\s*(\d+)", re.IGNORECASE)
_POS_RE2 = re.compile(r"\((\d+)\s*,\s*(\d+)\)")


class StateMachine:
    """把观察(OCR 文本等)转换为 GameState。"""

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        self.last_state: Optional[GameState] = None
        self.same_state_count = 0   # 状态无变化计数(防死循环, 规格书 §39)
        self.max_same_state = 5     # 超过进入 RECOVERY

    # ---------------- 主入口 ----------------
    def update(self, ocr_texts: List[str], raw_image: Optional[bytes] = None,
               raw_size: Optional[tuple] = None) -> GameState:
        """根据 OCR 文本更新状态。"""
        gs = GameState(account_id=self.account_id,
                       ocr_texts=ocr_texts,
                       raw_image=raw_image,
                       raw_size=raw_size)
        joined = " ".join(ocr_texts)
        gs.dialog_text = joined[:200]  # 画面文本摘要(供任务/LLM 使用)

        # 1. 地图识别
        for kw in _MAP_KEYWORDS:
            if kw in joined:
                gs.map_name = kw
                break

        # 2. 坐标识别
        m = _POS_RE.search(joined) or _POS_RE2.search(joined)
        if m:
            gs.position = (int(m.group(1)), int(m.group(2)))

        # 3. 血量蓝量(粗略): "HP 123/456" 或 "气血 123/456"
        m = re.search(r"(?:气血|HP|血)[:：]?\s*(\d+)\s*/\s*(\d+)", joined, re.IGNORECASE)
        if m:
            gs.hp = int(m.group(1))

        # 4. 任务识别
        if "师门" in joined:
            gs.task_name = "师门任务"
            m = re.search(r"第\s*(\d+)\s*(?:次|环)", joined)
            if m:
                gs.task_progress = f"第{m.group(1)}次"
        elif "抓鬼" in joined or "钟馗" in joined:
            gs.task_name = "抓鬼"

        # 5. 状态判定(关键词优先)
        for status, kws in _STATUS_KEYWORDS.items():
            if any(k in joined for k in kws):
                gs.status = status
                break
        else:
            # 6. 兜底: 有任务面板 = 任务状态; 有地图/坐标 = 场景内
            if gs.map_name or gs.position:
                gs.status = GameStatus.CITY if gs.map_name else GameStatus.MAP
            elif joined.strip():
                gs.status = GameStatus.UNKNOWN
            else:
                gs.status = GameStatus.UNKNOWN
                gs.detail = "无 OCR 文本, 可能黑屏/加载"

        # 7. 对话框判定 + 选项提取
        gs.dialogue_open = any(k in joined for k in ("接受", "提交", "确认", "给予", "取消"))
        gs.npc_detected = any(k in joined for k in ("听说", "对话", "帮忙", "需要", "拜见"))
        # 对话框选项: 常见动作词开头的短句
        for t in ocr_texts:
            tt = t.strip()
            if (any(k in tt for k in ("接受", "提交", "确认", "给予", "取消", "打听", "请教", "购买"))
                    and len(tt) <= 30 and tt not in gs.dialog_options):
                gs.dialog_options.append(tt)

        # 8. 战斗详情
        if gs.status == GameStatus.BATTLE:
            gs.in_battle = True
            m = re.search(r"回合\s*(\d+)", joined)
            if m:
                gs.battle_round = int(m.group(1))

        # 9. 队伍人数(粗略): "队伍 3/5"
        m = re.search(r"(?:队伍|队友)[:：]?\s*(\d+)\s*/\s*(\d+)", joined)
        if m:
            gs.team_members = int(m.group(1))

        # 10. 背包满
        if "背包已满" in joined or "道具栏已满" in joined:
            gs.inventory_full = True

        # 11. 状态变化检测
        self._track_change(gs)
        self.last_state = gs
        return gs

    # ---------------- 状态变化检测 ----------------
    def _track_change(self, gs: GameState) -> None:
        """统计连续相同状态次数。"""
        if self.last_state is not None:
            if (self.last_state.status == gs.status and
                    self.last_state.map_name == gs.map_name and
                    self.last_state.dialog_text == gs.dialog_text):
                self.same_state_count += 1
            else:
                self.same_state_count = 0

    @property
    def stuck(self) -> bool:
        """是否陷入死循环(需要 Recovery)。"""
        return self.same_state_count >= self.max_same_state
