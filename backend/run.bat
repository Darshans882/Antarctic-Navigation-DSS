@echo off
setlocal
cd /d "%~dp0"

set PYTHON_EXE=
if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting Antarctic Navigation DSS Backend on http://localhost:8000 ...
"%PYTHON_EXE%" -m uvicorn main:app --reload --reload-include "*.py" --reload-exclude "*.db*" --reload-exclude "*.sqlite*" --reload-exclude "*.log" --host 0.0.0.0 --port 8000
pause
