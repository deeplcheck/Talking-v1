@echo off
setlocal
cd /d %~dp0

call .venv\Scripts\activate.bat
set COQUI_TOS_AGREED=1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python -m uvicorn server:app --app-dir "%~dp0" --host 0.0.0.0 --port 8001
