$backendDir = $PSScriptRoot
$projectRoot = Split-Path $backendDir -Parent
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

$pythonExe = "python"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} elseif (Test-Path (Join-Path $backendDir "venv\Scripts\python.exe")) {
    $pythonExe = Join-Path $backendDir "venv\Scripts\python.exe"
}

Write-Host "Starting Antarctic Navigation DSS Backend on http://0.0.0.0:8000 ..." -ForegroundColor Green
$env:HOST = "0.0.0.0"
$env:PORT = "8000"
& $pythonExe -m uvicorn main:app --reload --reload-include "*.py" --reload-exclude "*.db*" --reload-exclude "*.sqlite*" --reload-exclude "*.log" --host 0.0.0.0 --port 8000
