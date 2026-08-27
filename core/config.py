# -*- coding: utf-8 -*-
"""配置加载 (规格书 §53 配置中心)。

支持: config.yaml 为主, .env 覆盖(环境变量 MHXY_*)
"""
from __future__ import annotations

import os
from typing import Any, Dict

import yaml

DEFAULT_CONFIG = {
    "system": {"max_accounts": 5, "language": "zh-CN"},
    "automation": {"auto_start": False, "max_retry": 3,
                   "action_timeout": 10, "state_timeout": 30, "tick_seconds": 0.5},
    "vision": {"fps": 10, "capture_backend": "mss", "ocr_backend": "rapidocr"},
    "input": {"backend": "pyautogui", "failsafe": True},
    "llm": {"provider": "ollama", "model": "qwen2.5:7b",
            "base_url": "http://127.0.0.1:11434"},
    "knowledge": {"repo": "", "vector_db": "faiss"},
    "ui": {"host": "127.0.0.1", "port": 8080},
    "logging": {"level": "INFO", "dir": "logs", "max_bytes": 5242880, "backup_count": 3},
    "accounts": {"leader": "account_01", "list": []},
}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """加载配置: 默认 -> config.yaml -> 环境变量覆盖。"""
    cfg = _deep_merge(dict(DEFAULT_CONFIG), {})
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
        _deep_merge(cfg, file_cfg)

    # 环境变量覆盖
    env_map = {
        "MHXY_LOG_DIR": ("logging", "dir"),
        "MHXY_REPLAY_DIR": ("replay", "dir"),
        "MHXY_LLM_PROVIDER": ("llm", "provider"),
        "MHXY_LLM_MODEL": ("llm", "model"),
        "MHXY_OLLAMA_BASE_URL": ("llm", "base_url"),
        "MHXY_EMBEDDING_MODEL": ("embedding", "model"),
        "MHXY_KNOWLEDGE_REPO": ("knowledge", "repo"),
        "MHXY_UI_HOST": ("ui", "host"),
        "MHXY_UI_PORT": ("ui", "port"),
    }
    for env_name, keys in env_map.items():
        val = os.getenv(env_name)
        if val:
            node = cfg
            for k in keys[:-1]:
                node = node.setdefault(k, {})
            node[keys[-1]] = int(val) if val.isdigit() else val

    # 路径归一化
    cfg["logging"]["dir"] = os.path.abspath(cfg["logging"]["dir"])
    os.makedirs(cfg["logging"]["dir"], exist_ok=True)
    return cfg


def load_env(path: str = ".env") -> None:
    """加载 .env(存在时)。"""
    if os.path.exists(path):
        try:
            from dotenv import load_dotenv
            load_dotenv(path)
        except Exception:
            pass
