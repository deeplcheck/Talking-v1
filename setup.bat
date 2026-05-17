@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0

echo [1/7] Checking Python 3.11...
py -3.11 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 is not installed.
  echo Please install it from:
  echo https://www.python.org/downloads/release/python-3119/
  echo After installation, run this setup.bat again.
  pause
  exit /b 1
)

echo [2/7] Creating virtual environment...
if not exist .venv (
  py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
set COQUI_TOS_AGREED=1
python -m pip install --upgrade pip setuptools wheel

echo [3/7] Installing PyTorch GPU build...
set TORCH_WHEEL=%TEMP%\torch-2.5.1+cu121-cp311-cp311-win_amd64.whl
if not exist "%TORCH_WHEEL%" (
  echo Downloading torch wheel with resume support...
  curl.exe --retry 20 --retry-delay 5 -L -C - -o "%TORCH_WHEEL%" "https://download.pytorch.org/whl/cu121/torch-2.5.1%%2Bcu121-cp311-cp311-win_amd64.whl"
)
pip install "%TORCH_WHEEL%"
if errorlevel 1 (
  echo Failed to install torch wheel.
  pause
  exit /b 1
)

pip install torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
  echo Failed to install torch GPU build.
  pause
  exit /b 1
)

echo [4/7] Installing project requirements...
pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install Python dependencies.
  pause
  exit /b 1
)

echo [5/7] Preparing folders...
if not exist output mkdir output
if not exist reference_voices mkdir reference_voices
if not exist static mkdir static

echo [6/7] Preparing XTTS model files...
python -u "%~dp0scripts\download_xtts_with_hf.py"
if errorlevel 1 (
  echo Failed to download XTTS model files.
  pause
  exit /b 1
)

echo [7/7] Generating preset voices...
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\prepare_voices.ps1"

echo Setup completed.
echo Next step: double-click start.bat
pause
