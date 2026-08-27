@echo off
chcp 65001 >nul
cd /d %~dp0
title 梦幻西游五开 AI 作战台 - 一键启动

echo ================================================
echo    梦幻西游五开 AI 作战台 - 一键启动
echo ================================================
echo.

REM --- 检查 Python ---
where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python, 请先安装:
  echo   去 https://www.python.org/downloads/ 下载 3.11+
  echo   安装时勾选 "Add python.exe to PATH"
  pause
  exit /b 1
)

REM --- 创建虚拟环境 ---
if not exist .venv (
  echo [1/4] 首次运行, 创建虚拟环境...
  python -m venv .venv
)

REM --- 安装依赖 ---
if not exist .venv/Scripts/python.exe (
  echo [错误] 虚拟环境创建失败
  pause
  exit /b 1
)
echo [2/4] 检查依赖...
.venv/Scripts/python.exe -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
  echo        正在安装依赖(首次约1-2分钟)...
  .venv/Scripts/python.exe -m pip install -r requirements.txt -q
)

echo [3/4] 启动 Web 作战台...
echo.
echo   浏览器将打开: http://127.0.0.1:8080
echo   关闭此窗口即停止作战台
echo.
start "" http://127.0.0.1:8080

REM --- 启动 Web 服务器(默认 dry-run 安全模式) ---
echo [4/4] 运行中...(Ctrl+C 停止)

rem 设置安全模式环境变量: 1=只读不操作真实游戏(推荐), 0=允许真实操作(有封号风险)
set MHXY_DRY_RUN=1

.venv/Scripts/python.exe web_server.py --port 8080

pause