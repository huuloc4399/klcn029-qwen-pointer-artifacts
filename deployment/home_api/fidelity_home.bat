@echo off
rem Run the fidelity gate (10 synthetic CVs vs P0) on llama-server instead of serving.
rem The output, including the final JSON for the report, is also saved to
rem <Root>\logs\fidelity_<date>_<time>.txt. Stop start_home.bat first.
rem Double-click, or run: fidelity_home.bat [Root]   (default Root: F:\klcn029-home)
setlocal
set "ROOT=F:\klcn029-home"
if not "%~1"=="" set "ROOT=%~1"
if not exist "%ROOT%\home.env" (
    echo %ROOT%\home.env not found. Run setup_home.bat first and fill in home.env.
    pause
    exit /b 1
)
set "KLCN029_SCRIPT=%~dp0start_home.ps1"
set "KLCN029_ROOT=%ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$log = Join-Path $env:KLCN029_ROOT ('logs\fidelity_' + (Get-Date -Format 'yyyyMMdd_HHmm') + '.txt'); & $env:KLCN029_SCRIPT -Root $env:KLCN029_ROOT -Fidelity | Tee-Object -FilePath $log; Write-Host ('Saved to ' + $log); exit $LASTEXITCODE"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" echo Fidelity run failed with exit code %CODE%.
pause
exit /b %CODE%
