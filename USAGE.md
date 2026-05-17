# Talking v1 Usage Guide

## What this project is

Talking v1 is a private browser-based voice generation tool for Windows.
It runs locally with a FastAPI backend, SQLite user accounts, and XTTS v2 voice synthesis.

## Folder overview

- `server.py`: backend entry and generation logic
- `database.py`: user accounts and JWT auth
- `static/login.html`: login and registration page
- `static/app.html`: main generation page
- `setup.bat`: one-time environment setup
- `start.bat`: normal foreground startup
- `run_server.ps1`: PowerShell startup script
- `install_startup_task.ps1`: register Windows startup task
- `scripts/`: diagnostics and model preparation helpers

## First-time setup on Windows

1. Install Python 3.11.
2. Download or clone this repository.
3. Open the project folder.
4. Double-click `setup.bat`.
5. Wait for Python dependencies, PyTorch, and XTTS model files to finish installing.
6. After setup finishes, double-click `start.bat`.

## Local startup

Run:

- `start.bat` for a foreground window
- `run_server.ps1` for PowerShell startup
- `install_startup_task.bat` if you want the service to auto-start after Windows login

After startup, open:

- `http://127.0.0.1:8001` on the Windows host itself
- `http://<LAN-IP>:8001` from another device on the same network

## Normal usage flow

1. Open the web page.
2. Register an account on first use.
3. Log in.
4. Upload a clean reference audio file to `我的声音` if you want custom voice cloning.
5. Paste text into the main text box.
6. Choose a voice.
7. Click `开始生成`.
8. Wait for the MP3 result, then preview or download it.

## Recommended reference audio

For better custom voice cloning, use:

- 10 to 30 seconds of clean single-speaker audio
- no background music
- no echo-heavy room sound
- natural speaking tone
- common formats such as wav, mp3, m4a, flac, or ogg

## Outputs and data

Generated files and local data are stored in the project directory at runtime:

- `users.db`: account database
- `.jwt_secret`: local auth secret
- `output/`: generated wav and mp3 files
- `reference_voices/user_*`: uploaded user reference voices

These runtime files are intentionally not tracked in Git.

## Quick health checks

- Open `http://127.0.0.1:8001/health`
- The API should report `ok: true`
- If CUDA is available, it should also show the GPU device name

Useful diagnostics in `scripts/`:

- `check_auth_stack.py`
- `check_server_import.py`
- `check_tts_generate.py`

## Common problems

### Python 3.11 not found

Install Python 3.11, then run `setup.bat` again.

### GPU not available

Check NVIDIA driver, CUDA compatibility, and whether the PyTorch GPU build installed correctly.

### Upload succeeds but custom voice sounds wrong

Try a cleaner and shorter human voice reference.
Avoid long recordings with pauses, background noise, or multiple speaking styles.

### Port 8001 cannot be opened from phone

Make sure:

- the phone is on the same Wi-Fi
- Windows firewall allows the service
- the server is actually listening on port `8001`

## GitHub repository

Source repository:

- `https://github.com/deeplcheck/Talking-v1`
