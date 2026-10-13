<#
.SYNOPSIS
  Run the KLCN029 extraction API on this laptop and publish it through a Cloudflare quick tunnel.

.DESCRIPTION
  1. Downloads (first run) and hash-checks the pinned GGUF into <Root>\data\hf.
  2. Starts llama-server on 127.0.0.1:LLAMA_PORT (default 8091) with that exact file
     (GPU layers: N_GPU_LAYERS). Refuses to start if that port or 7860 is already taken.
  3. Starts the API on 127.0.0.1:7860 (LLAMA_SERVER_URL points it at llama-server).
  4. Starts "cloudflared tunnel --url" and prints the public https://*.trycloudflare.com URL.
  Nothing listens on the network directly; only the tunnel reaches the API, which requires
  X-API-Key. The quick-tunnel URL changes on every start: update EXTRACTION_API_URL on Render.
  Keeps Windows awake while running. Ctrl+C stops everything.

  -Fidelity runs the fidelity gate (10 synthetic CVs vs P0) on llama-server instead of
  serving, so the deployed GPU/CPU runtime is measured before the link is shared.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deployment\home_api\start_home.ps1 -Root E:\klcn029-home
#>
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [switch]$Fidelity,
    [int]$Samples = 10
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $Root).Path
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Api = Join-Path $Root "api"
$Logs = Join-Path $Root "logs"

$envFile = Join-Path $Root "home.env"
foreach ($line in Get-Content $envFile) {
    $line = $line.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $name, $value = $line.Split("=", 2)
        Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
    }
}
foreach ($required in "API_KEY", "HF_TOKEN", "GGUF_REPO_ID", "GGUF_FILENAME", "GGUF_REVISION", "GGUF_SHA256") {
    if (-not [Environment]::GetEnvironmentVariable($required)) { throw "Missing $required in $envFile" }
}
if ($env:API_KEY.StartsWith("hf_")) { throw "API_KEY must be a random key, not a Hugging Face token" }
$env:HF_HOME = Join-Path $Root "data\hf"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:FEEDBACK_DIR = Join-Path $Root "data\feedback"
$env:MODEL_CACHE_DIR = Join-Path $Root "data\models"
$llamaPort = if ($env:LLAMA_PORT) { [int]$env:LLAMA_PORT } else { 8091 }
$apiPort = 7860
$env:LLAMA_SERVER_URL = "http://127.0.0.1:$llamaPort"
$env:TEMP = Join-Path $Root "tmp"
$env:TMP = $env:TEMP
$gpuLayers = if ($env:N_GPU_LAYERS) { $env:N_GPU_LAYERS } else { "28" }

function Read-Log([string]$Path) {
    if (-not (Test-Path $Path)) { return "" }
    $stream = [System.IO.File]::Open($Path, "Open", "Read", "ReadWrite")
    try { return (New-Object System.IO.StreamReader($stream)).ReadToEnd() } finally { $stream.Dispose() }
}

function Assert-PortFree([int]$Port, [string]$Purpose) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        $ownerName = if ($owner) { $owner.ProcessName } else { "unknown" }
        throw ("Port $Port ($Purpose) is already used by PID $($listener.OwningProcess) ($ownerName). " +
               "Stop that program, or for llama-server set LLAMA_PORT to a free port in home.env.")
    }
}

function Test-LlamaHealth([int]$Port) {
    # llama-server answers {"status":"ok"} once the model is loaded; anything else is not ready.
    try {
        $health = Invoke-RestMethod -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$Port/health"
        return ($health -isnot [string]) -and ($health.status -eq "ok")
    } catch {
        return $false
    }
}

function Start-Logged([string]$Name, [string]$File, [string[]]$Arguments, [string]$WorkingDirectory = $Root) {
    $out = Join-Path $Logs "$Name.out.log"
    $err = Join-Path $Logs "$Name.err.log"
    Remove-Item $out, $err -ErrorAction SilentlyContinue
    return Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
        -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
}

Add-Type -Namespace Klcn029 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$processes = @()
try {
    [void][Klcn029.Power]::SetThreadExecutionState([uint32]2147483649)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

    Write-Host "== GGUF (first run downloads 2.5 GB; every run checks SHA-256)"
    Push-Location $Api
    try { $gguf = & $Python -c "from app.llm_runtime import download_gguf; print(download_gguf()[0])" } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "GGUF download or hash check failed" }
    $gguf = ($gguf | Select-Object -Last 1).Trim()
    Write-Host $gguf

    Assert-PortFree $llamaPort "llama-server"
    if (-not $Fidelity) { Assert-PortFree $apiPort "API" }

    Write-Host "== llama-server on 127.0.0.1:$llamaPort (GPU layers: $gpuLayers)"
    $llama = Start-Logged "llama-server" (Join-Path $Root "llama\llama-server.exe") @(
        "-m", "`"$gguf`"", "-c", "6144", "-b", "512", "--parallel", "1", "-ngl", $gpuLayers,
        "--host", "127.0.0.1", "--port", "$llamaPort")
    $processes += $llama
    $ready = $false
    for ($i = 0; $i -lt 150 -and -not $ready; $i++) {
        if ($llama.HasExited) { break }
        $ready = Test-LlamaHealth $llamaPort
        if (-not $ready) { Start-Sleep 2 }
    }
    if (-not $ready) {
        $tail = (Read-Log (Join-Path $Logs "llama-server.err.log")) -split "`n" | Select-Object -Last 25
        Write-Host ($tail -join "`n")
        throw "llama-server did not start. If the log mentions out of memory, lower N_GPU_LAYERS in home.env."
    }

    if ($Fidelity) {
        Write-Host "== Fidelity gate on llama-server ($Samples synthetic CVs)"
        Push-Location $Api
        try { & $Python fidelity_check.py gguf_fidelity_bundle_v1.zip --samples $Samples --app-runtime --host "windows_llama_server_ngl$gpuLayers" }
        finally { Pop-Location }
        return
    }

    Write-Host "== API on 127.0.0.1:$apiPort"
    $processes += Start-Logged "api" $Python @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$apiPort", "--workers", "1") $Api

    Write-Host "== Cloudflare quick tunnel"
    $tunnel = Start-Logged "cloudflared" (Join-Path $Root "cloudflared.exe") @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$apiPort")
    $processes += $tunnel
    $url = $null
    for ($i = 0; $i -lt 60 -and -not $url; $i++) {
        Start-Sleep 1
        $match = [regex]::Match((Read-Log (Join-Path $Logs "cloudflared.err.log")), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) { $url = $match.Value }
    }
    if (-not $url) { throw "No tunnel URL; see $Logs\cloudflared.err.log" }

    Write-Host ""
    Write-Host "Public API URL: $url" -ForegroundColor Green
    Write-Host "Set EXTRACTION_API_URL=$url on Render (leave EXTRACTION_HF_TOKEN empty)."
    Write-Host "Model status:  $url/health   (wait for ""model"": ""ready"")"
    Write-Host "Logs: $Logs. Keep this window open and the laptop plugged in; Ctrl+C stops everything."
    while ($true) {
        foreach ($process in $processes) {
            if ($process.HasExited) { throw "A process exited unexpectedly (id $($process.Id)); see $Logs" }
        }
        Start-Sleep 5
    }
}
finally {
    foreach ($process in $processes) {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
    [void][Klcn029.Power]::SetThreadExecutionState([uint32]2147483648)  # ES_CONTINUOUS: allow sleep again
    Write-Host "Stopped."
}
