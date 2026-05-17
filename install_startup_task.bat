@echo off
setlocal
cd /d %~dp0

powershell -ExecutionPolicy Bypass -File "%~dp0install_startup_task.ps1"
if errorlevel 1 (
  echo Failed to create startup task.
  pause
  exit /b 1
)

echo Startup task installed. The service will start when this Windows user logs in.
pause
