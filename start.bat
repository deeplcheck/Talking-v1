@echo off
setlocal
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  echo Virtual environment not found. Please run setup.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
set COQUI_TOS_AGREED=1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Starting FastAPI server on http://0.0.0.0:8001
echo Open locally: http://127.0.0.1:8001
python -m uvicorn server:app --app-dir "%~dp0" --host 0.0.0.0 --port 8001
pause
