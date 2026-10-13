<#
.SYNOPSIS
  One-time setup of the KLCN029 extraction API on this Windows laptop, without Docker.

.DESCRIPTION
  Everything goes under -Root (use the external drive; about 4 GB incl. the GGUF):
    llama\           llama-server from llama.cpp release b11312 (CUDA 12.4, CPU or Vulkan build)
    cloudflared.exe  Cloudflare quick tunnel client
    venv\            Python 3.11 with the API's core packages (no OCR)
    api\             API bundle built from this repository (hash-verified at startup)
    data\            GGUF cache, feedback ratings
    home.env         secrets and settings (copied from home.env.example; edit it)
  Downloads are checked against pinned SHA-256 digests. Re-running is safe.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File deployment\home_api\setup_home.ps1 -Root E:\klcn029-home
#>
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [ValidateSet("cuda", "cpu", "vulkan")][string]$Backend = "cuda"
)
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

# llama.cpp b11312 is the commit vendored by llama-cpp-python v0.3.36, which wrote the GGUF.
# CUDA 12.4 runs on NVIDIA drivers >= 551 (the CUDA 13 build needs >= 580).
$LlamaBase = "https://github.com/ggml-org/llama.cpp/releases/download/b11312"
$LlamaAssets = @{
    cuda   = @(
        @{ Name = "llama-b11312-bin-win-cuda-12.4-x64.zip"; Sha256 = "c7e67ed12791e31e21aba6a15856bade791586e4a1cefa313ea207f441089133" },
        @{ Name = "cudart-llama-bin-win-cuda-12.4-x64.zip"; Sha256 = "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6" }
    )
    cpu    = @(@{ Name = "llama-b11312-bin-win-cpu-x64.zip"; Sha256 = "d2d966c23e4d097d70633f9d92e4931245b575be7a5409201d8f352493f0e702" })
    vulkan = @(@{ Name = "llama-b11312-bin-win-vulkan-x64.zip"; Sha256 = "ad3e1e83bdcbc56c00fb2d740e8799e3012d63a12d0a64509407e625a77378a0" })
}
$CloudflaredUrl = "https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-windows-amd64.exe"
$CloudflaredSha256 = "86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c"

function Get-Verified([string]$Url, [string]$Path, [string]$Sha256) {
    if ((Test-Path $Path) -and (Get-FileHash $Path -Algorithm SHA256).Hash -eq $Sha256) {
        Write-Host "Already downloaded: $Path"
        return
    }
    Write-Host "Downloading $Url"
    curl.exe -L --fail --retry 3 -o $Path $Url
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $Url" }
    if ((Get-FileHash $Path -Algorithm SHA256).Hash -ne $Sha256) {
        Remove-Item $Path
        throw "SHA-256 mismatch, file removed: $Path"
    }
}

foreach ($dir in "", "downloads", "llama", "logs", "data", "tmp") {
    New-Item -ItemType Directory -Force (Join-Path $Root $dir) | Out-Null
}
$Root = (Resolve-Path $Root).Path
# Keep pip temp files off the nearly full system drive.
$env:TEMP = Join-Path $Root "tmp"
$env:TMP = $env:TEMP
$env:PIP_NO_CACHE_DIR = "1"

Write-Host "== llama.cpp b11312 ($Backend)"
foreach ($asset in $LlamaAssets[$Backend]) {
    $zip = Join-Path $Root "downloads\$($asset.Name)"
    Get-Verified "$LlamaBase/$($asset.Name)" $zip $asset.Sha256
    Expand-Archive -Path $zip -DestinationPath (Join-Path $Root "llama") -Force
}
if (-not (Test-Path (Join-Path $Root "llama\llama-server.exe"))) { throw "llama-server.exe not found after extraction" }

Write-Host "== cloudflared"
Get-Verified $CloudflaredUrl (Join-Path $Root "cloudflared.exe") $CloudflaredSha256

Write-Host "== Python 3.11 environment"
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 is required (py -3.11). Install it from python.org." }
$Python = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { & py -3.11 -m venv (Join-Path $Root "venv") }
$core = Get-Content (Join-Path $Repo "deployment\hf_space_api\requirements.txt") |
    Where-Object { $_ -match '^(fastapi|uvicorn|pydantic|huggingface_hub|requests|PyMuPDF|numpy|Pillow)==' }
$coreFile = Join-Path $Root "requirements-core.txt"
Set-Content -Path $coreFile -Value $core -Encoding ascii
& $Python -m pip install --upgrade pip --quiet
& $Python -m pip install --quiet -r $coreFile
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "== API bundle"
& $Python (Join-Path $Repo "deployment\home_api\build_bundle.py") --out (Join-Path $Root "api")
if ($LASTEXITCODE -ne 0) { throw "Bundle build failed" }

$envFile = Join-Path $Root "home.env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Repo "deployment\home_api\home.env.example") $envFile
    Write-Host "Created $envFile"
}
if ($Backend -ne "cuda") {
    Write-Host "Backend $($Backend): set N_GPU_LAYERS=0 in home.env for the CPU build."
}
Write-Host ""
Write-Host "Setup done. Next: fill API_KEY and HF_TOKEN in $envFile, then run"
Write-Host "  powershell -ExecutionPolicy Bypass -File deployment\home_api\start_home.ps1 -Root $Root -Fidelity"
