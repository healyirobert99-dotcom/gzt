@echo off
rem A/H investment & trading workbench launcher
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3 and add it to PATH.
  pause
  exit /b 1
)
echo Starting workbench, browser will open at http://127.0.0.1:8765
echo Close this window or press Ctrl+C to stop.
"%PY%" "app\server.py"
pause
