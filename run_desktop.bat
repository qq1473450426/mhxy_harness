@echo off
setlocal
cd /d %~dp0
where py >nul 2>nul || where python >nul 2>nul || (
  echo Python not found.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
python -m desktop
if errorlevel 1 pause
endlocal
