@echo off
setlocal EnableExtensions
set "PY="
call :try "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
echo MARK1=[%PY%]
set "PY="
call :try "C:/no/such/python.exe"
echo MARK2=[%PY%]
set "PY="
call :try "C:/Users/x/AppData/Local/Microsoft/WindowsApps/python.exe"
echo MARK3=[%PY%]
exit /b 0

:try
set "T=%~1"
rem  reject the Microsoft Store execution alias outright
if not "%T:WindowsApps=%"=="%T%" goto :eof
rem  must actually run and report version 3.8 or newer
"%T%" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%T%"
goto :eof
