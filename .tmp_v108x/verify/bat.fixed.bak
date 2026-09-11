@echo off
setlocal EnableExtensions
title A/H Workbench

rem ======================================================================
rem  A/H Investment and Trading Workbench - launcher
rem
rem  WHY THIS FILE IS ASCII-ONLY
rem  ---------------------------
rem  cmd.exe reads a .bat file byte by byte and interprets it under the
rem  console's active code page (936 / 65001 / ...). Non-ASCII bytes pasted
rem  in here would be mis-decoded and could corrupt the very paths we hand
rem  to the shell. Every literal below therefore stays ASCII.
rem
rem  WHY %USERPROFILE% IS USED BELOW
rem  -------------------------------
rem  The interpreter that really runs this project lives at
rem      %USERPROFILE%\.workbuddy\binaries\python\versions\<ver>\python.exe
rem  The Windows user name on this machine is non-ASCII. Writing the path as
rem  %USERPROFILE%\... keeps this script free of non-ASCII bytes while still
rem  resolving to the correct absolute path at run time.
rem
rem  WHY A BARE "python" COMMAND IS NOT ENOUGH
rem  ----------------------------------------
rem  The persistent PATH on this machine contains only
rem      %LOCALAPPDATA%\Microsoft\WindowsApps
rem  and the python.exe in that folder is a Microsoft Store *placeholder*,
rem  not an interpreter - running it opens the Store. So every candidate is
rem  probed for real and the Store alias is rejected explicitly.
rem ======================================================================

cd /d "%~dp0"

echo.
echo   ==============================================
echo     A/H Workbench
echo   ==============================================
echo.

if not exist "app\server.py" (
  echo   [ERROR] app\server.py not found.
  echo   [ERROR] Keep this launcher in the workbench root,
  echo   [ERROR] next to the "app" folder, then retry.
  echo.
  pause
  exit /b 1
)

set "PY="

rem --- candidate 1: pinned managed interpreter (preferred) --------------
if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" call :try "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"

rem --- candidate 2: any other managed interpreter -----------------------
if not defined PY for /d %%V in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do if not defined PY if exist "%%~fV\python.exe" call :try "%%~fV\python.exe"

rem --- candidate 3: the official Python launcher ------------------------
if not defined PY call :try "py"

rem --- candidate 4: whatever "python" resolves to on PATH ---------------
if not defined PY call :try "python"

if not defined PY (
  echo   [ERROR] No usable Python 3 interpreter was found.
  echo.
  echo   [ERROR] Note: the python.exe inside
  echo   [ERROR]   %%LOCALAPPDATA%%\Microsoft\WindowsApps
  echo   [ERROR] is only a Microsoft Store placeholder, not a real Python.
  echo   [ERROR] Install Python 3.8+ from https://www.python.org and tick
  echo   [ERROR] "Add python.exe to PATH" during setup, then retry.
  echo.
  pause
  exit /b 1
)

echo   Python  : "%PY%"
echo   Address : http://127.0.0.1:8765
echo.
echo   The browser opens automatically. Keep this window open;
echo   close it or press Ctrl+C to stop the server.
echo.

"%PY%" "app\server.py"

echo.
echo   Server stopped.
echo.
pause
endlocal
exit /b 0

rem ======================================================================
rem  :try <candidate>
rem  Accepts the candidate only if it is a real, runnable Python 3.8+.
rem  Sets PY on success; leaves it untouched otherwise.
rem ======================================================================
:try
set "T=%~1"
rem  reject the Microsoft Store execution alias outright
if not "%T:WindowsApps=%"=="%T%" goto :eof
rem  must actually run and report version 3.8 or newer
"%T%" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%T%"
goto :eof
