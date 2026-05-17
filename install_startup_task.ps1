param(
  [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $baseDir ".venv\Scripts\python.exe"
$runner = Join-Path $baseDir "run_server.ps1"
$taskName = "VoiceToolRun"
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Port $Port"

if (-not (Test-Path $python)) {
  throw "Virtual environment not found. Run setup.bat first."
}
if (-not (Test-Path $runner)) {
  throw "Runner script not found: $runner"
}

Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
  ForEach-Object {
    $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($process -and $process.Path -like "*python*") {
      Stop-Process -Id $_.OwningProcess -Force
    }
  }

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $baseDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
  -TaskName $taskName `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Settings $settings `
  -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Host "Startup task installed and started: $taskName"
