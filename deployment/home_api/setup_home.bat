@echo off
rem One-time setup (or update after a git pull) of the extraction API on this laptop.
rem Double-click, or run: setup_home.bat [Root]   (default Root: F:\klcn029-home)
setlocal
set "ROOT=F:\klcn029-home"
if not "%~1"=="" set "ROOT=%~1"
if not exist "%ROOT:~0,3%" (
    echo Drive %ROOT:~0,2% not found. Plug in the external drive or pass another Root.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_home.ps1" -Root "%ROOT%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" echo Setup failed with exit code %CODE%.
pause
exit /b %CODE%
