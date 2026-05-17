param(
  [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $baseDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
  throw "Virtual environment not found. Run setup.bat first."
}

$env:COQUI_TOS_AGREED = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Set-Location $baseDir
& $python -m uvicorn server:app --app-dir $baseDir --host 0.0.0.0 --port $Port
