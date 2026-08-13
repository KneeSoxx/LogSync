@echo off
REM LogSync Startup Script for Windows
REM Usage: run.bat [port]

set PORT=%~1
if "%PORT%"=="" set PORT=8000

echo Starting LogSync server on port %PORT%...
cd /d "%~dp0"

call venv\Scripts\activate
python -m uvicorn src.main:app --host 0.0.0.0 --port %PORT%
