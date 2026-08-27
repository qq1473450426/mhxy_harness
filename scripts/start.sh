#!/usr/bin/env bash
# 梦幻西游五开本地AI自动任务系统 - Linux/macOS 开发启动(仅模拟模式)
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -r requirements.txt -q
python app.py "$@"
