@echo off
setlocal
cd /d %~dp0
where py >nul 2>nul && set PY=py || set PY=python
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
%PY% -m desktop
if errorlevel 1 (
  echo Desktop exited with error.
  pause
)
endlocal
