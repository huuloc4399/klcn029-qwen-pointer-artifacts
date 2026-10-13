@echo off
rem Stop every process started from the deployment folder (llama-server, the API's python,
rem cloudflared), e.g. when the start_home window was closed but they kept running.
rem Double-click, or run: stop_home.bat [Root]   (default Root: F:\klcn029-home)
setlocal
set "ROOT=F:\klcn029-home"
if not "%~1"=="" set "ROOT=%~1"
set "KLCN029_ROOT=%ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$root = (Resolve-Path $env:KLCN029_ROOT).Path + '\'; $found = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) }; if (-not $found) { Write-Host 'Nothing is running from' $root; exit 0 }; $found | ForEach-Object { Write-Host ('Stopping ' + $_.ProcessName + ' (PID ' + $_.Id + ')'); Stop-Process -Id $_.Id -Force }"
pause
exit /b %ERRORLEVEL%
