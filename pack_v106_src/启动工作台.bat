@echo off
rem A/H tou yan jiao yi gong zuo tai qi dong qi
cd /d "%~dp0"
set "PY=C:\Users\ÒË´º·¨Ôº\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
  )
  set "PY=python"
)
echo Starting workbench, browser will open...
echo Close this window or press Ctrl+C to stop.
"%PY%" "app\server.py"
pause
