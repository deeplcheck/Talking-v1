# Talking v1

Talking v1 is a private browser-based voice generation app built with FastAPI and XTTS v2.
It supports account login, preset voices, custom voice uploads, natural spoken-text cleanup, GPU-accelerated synthesis, and MP3 download.

## Tech stack

- FastAPI backend
- XTTS v2 via Coqui TTS
- SQLite user database
- Plain HTML/CSS/JavaScript frontend
- Windows helper scripts for setup and startup

## Project structure

- `server.py`: FastAPI app, XTTS generation flow, media token protection
- `database.py`: SQLite auth and JWT helpers
- `static/login.html`: login and registration page
- `static/app.html`: main voice generation console
- `setup.bat`: one-time Windows environment setup
- `start.bat`: foreground startup entry
- `run_server.ps1`: PowerShell server runner
- `install_startup_task.ps1`: register Windows startup task
- `scripts/`: diagnostics and model preparation helpers

## Quick start on Windows

1. Install Python 3.11.
2. Run `setup.bat`.
3. Run `start.bat` for local testing.
4. Open `http://127.0.0.1:8001`.

## Notes

This repository intentionally excludes generated audio, local databases, uploaded reference voices, and runtime secrets.
