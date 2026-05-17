param(
  [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $baseDir ".venv\Scripts\python.exe"
$outLog = Join-Path $baseDir "server.out.log"
$errLog = Join-Path $baseDir "server.err.log"

if (-not (Test-Path $python)) {
  throw "Virtual environment not found. Run setup.bat first."
}

Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
  ForEach-Object {
    $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($process -and $process.Path -like "*python*") {
      Stop-Process -Id $_.OwningProcess -Force
    }
  }

$arguments = "-m uvicorn server:app --app-dir `"$baseDir`" --host 0.0.0.0 --port $Port"

$env:COQUI_TOS_AGREED = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$process = Start-Process `
  -FilePath $python `
  -ArgumentList $arguments `
  -WorkingDirectory $baseDir `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -WindowStyle Hidden `
  -PassThru

Start-Sleep -Seconds 10
if ($process.HasExited) {
  Write-Host "Server process exited with code $($process.ExitCode). stderr:"
  if (Test-Path $errLog) {
    Get-Content $errLog
  }
  Write-Host "stdout:"
  if (Test-Path $outLog) {
    Get-Content $outLog
  }
  exit 1
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if (-not $listener) {
  Write-Host "Server did not start. stderr:"
  if (Test-Path $errLog) {
    Get-Content $errLog
  }
  exit 1
}

Write-Host "Voice tool is running on port $Port with PID $($process.Id)."
