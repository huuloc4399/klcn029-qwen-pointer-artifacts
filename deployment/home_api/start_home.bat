@echo off
rem Start llama-server, the API and the Cloudflare quick tunnel; prints the public URL.
rem Keep this window open while serving; Ctrl+C stops everything.
rem Double-click, or run: start_home.bat [Root]   (default Root: F:\klcn029-home)
setlocal
set "ROOT=F:\klcn029-home"
if not "%~1"=="" set "ROOT=%~1"
if not exist "%ROOT%\home.env" (
    echo %ROOT%\home.env not found. Run setup_home.bat first and fill in home.env.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_home.ps1" -Root "%ROOT%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" echo The service stopped with exit code %CODE%. Logs: %ROOT%\logs
pause
exit /b %CODE%
