@echo off
chcp 65001 >nul
cd /d %~dp0..
echo ================================================
echo   梦幻西游五开本地AI自动任务系统 - 启动器
echo ================================================
if not exist .venv (
  echo [1/3] 创建虚拟环境(Python 3.11+)...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [2/3] 安装依赖...
python -m pip install -r requirements.txt -q
echo [3/3] 启动...
python app.py %*
pause
