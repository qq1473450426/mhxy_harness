# -*- coding: utf-8 -*-
"""本地 LLM 接口 (Phase 3, 规格书 §3/§7/§45)。

支持后端:
- ollama: 默认(http://127.0.0.1:11434), 完全离线
- openai: OpenAI 兼容 API(LM Studio / vLLM / llama.cpp server)
- mock: 内置模拟(测试/无模型环境)

设计原则:
- LLM 只做语义决策, 不输出坐标(规格书 §8)
- 输出必须严格 JSON(规格书 §45)
- 事件触发, 不每帧调用(规格书 §52)
"""
from __future__ import annotations

import json
import logging
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用失败。"""


class LLMBackend(ABC):
    """LLM 后端抽象。"""

    name = "base"

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.2, max_tokens: int = 512) -> str:
        """发送对话, 返回纯文本回复。"""


class OllamaBackend(LLMBackend):
    """Ollama 本地模型。"""

    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434",
                 model: str = "qwen2.5:7b") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.2, max_tokens: int = 512) -> str:
        url = f"{self.base_url}/api/chat"
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")
        except Exception as e:
            raise LLMError(f"Ollama 调用失败: {e}") from e


class OpenAICompatBackend(LLMBackend):
    """OpenAI 兼容 API(LM Studio / vLLM / llama.cpp server)。"""

    name = "openai"

    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1",
                 model: str = "local-model",
                 api_key: str = "local") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.2, max_tokens: int = 512) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"OpenAI 兼容 API 调用失败: {e}") from e


class MockBackend(LLMBackend):
    """模拟后端: 无模型环境下的确定性响应(测试用)。"""

    name = "mock"

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.2, max_tokens: int = 512) -> str:
        last = messages[-1]["content"] if messages else ""
        # 精确匹配状态描述(避免 "战斗: False" 误判)
        if "战斗: True" in last or "BATTLE_AUTO" in last or "战斗中" in last:
            action = "BATTLE_AUTO"
        elif "师门" in last and ("提交" in last or "完成" in last):
            action = "SUBMIT_TASK"
        elif "师门" in last:
            action = "OPEN_TASK"
        elif "长安" in last:
            action = "IDLE"
        else:
            action = "UNKNOWN"
        return json.dumps({
            "goal": "完成当前任务",
            "observation": last[:50],
            "reason": "Mock 决策(测试用)",
            "action": {"type": action, "target": ""},
            "confidence": 0.9,
            "need_knowledge": False,
            "need_replan": False,
        }, ensure_ascii=False)


class LLMClient:
    """统一 LLM 客户端入口。"""

    def __init__(self, provider: str = "ollama",
                 model: str = "qwen2.5:7b",
                 base_url: str = "http://127.0.0.1:11434",
                 api_key: str = "local",
                 temperature: float = 0.2,
                 max_tokens: int = 512) -> None:
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        if provider == "ollama":
            self._backend: LLMBackend = OllamaBackend(base_url, model)
        elif provider in ("openai", "openai-compatible"):
            self._backend = OpenAICompatBackend(base_url, model, api_key)
        elif provider == "mock":
            self._backend = MockBackend()
        else:
            raise ValueError(f"未知 LLM provider: {provider}")

    @property
    def backend(self) -> LLMBackend:
        return self._backend

    def chat(self, messages: List[Dict[str, str]]) -> str:
        return self._backend.chat(messages, self.temperature, self.max_tokens)

    def chat_json(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """请求 JSON 输出(严格 JSON, 规格书 §45)。"""
        system_hint = ("输出必须是合法的 JSON 对象, 不要输出任何其他文字、代码块标记或解释。")
        if messages and messages[0]["role"] == "system":
            messages = [dict(messages[0], content=messages[0]["content"] + system_hint)] + messages[1:]
        else:
            messages = [{"role": "system", "content": system_hint}] + messages
        text = self.chat(messages)
        return parse_json_response(text)


def parse_json_response(text: str) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON(容忍代码块/前后缀)。"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹(实际文件中用三反引号)
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"LLM 输出不是合法 JSON: {text[:200]}")
