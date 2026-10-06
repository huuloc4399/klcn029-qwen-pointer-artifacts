$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not $env:CV_WEB_SECRET_KEY) {
    $env:CV_WEB_SECRET_KEY = [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
}
python cv_evaluation_web/serve.py
