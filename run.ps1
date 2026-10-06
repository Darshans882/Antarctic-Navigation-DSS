param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11+ and run this script again."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 18+ and run this script again."
}

$venvHealthy = Test-Path $pythonPath
if ($venvHealthy) {
    try {
        & $pythonPath --version 2>$null
        $venvHealthy = $LASTEXITCODE -eq 0
    }
    catch {
        $venvHealthy = $false
    }
}

if (-not $venvHealthy) {
    if (Test-Path $venvPath) {
        Write-Host "Recreating the stale Python virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvPath
    }
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
}

if (-not $SkipInstall) {
    if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $frontendPath
        try {
            & npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
        }
        finally {
            Pop-Location
        }
    }

    $requirementsStamp = Join-Path $venvPath ".requirements-installed"
    if (-not (Test-Path $requirementsStamp)) {
        Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
        & $pythonPath -m pip install -r (Join-Path $backendPath "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
        New-Item -ItemType File -Path $requirementsStamp -Force | Out-Null
    }
}

Write-Host "Starting backend on all network interfaces at http://0.0.0.0:8000 ..." -ForegroundColor Green
$allProcesses = Get-CimInstance Win32_Process
$backendLaunchers = @($allProcesses | Where-Object {
    $_.ExecutablePath -like "*powershell.exe" -and $_.CommandLine -match "uvicorn main:app.*--port 8000"
})
$backendProcessTree = @($backendLaunchers)
$parentIds = @($backendLaunchers | ForEach-Object ProcessId)
while ($parentIds.Count -gt 0) {
    $children = @($allProcesses | Where-Object { $_.ParentProcessId -in $parentIds })
    if ($children.Count -eq 0) { break }
    $backendProcessTree += $children
    $parentIds = @($children | ForEach-Object ProcessId)
}
for ($index = $backendProcessTree.Count - 1; $index -ge 0; $index--) {
    Stop-Process -Id $backendProcessTree[$index].ProcessId -Force -ErrorAction SilentlyContinue
}

$backendListeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($listenerProcessId in $backendListeners) {
    if (Get-Process -Id $listenerProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $listenerProcessId /T /F 2>$null | Out-Null
    }
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $listenerProcessId"
    $backendProcessId = $listenerProcessId
    while ($processInfo) {
        if ($processInfo.ExecutablePath -like "*python.exe" -and $processInfo.CommandLine -match "-m uvicorn main:app") {
            $backendProcessId = $processInfo.ProcessId
        }
        if ($processInfo.ParentProcessId -le 0 -or $processInfo.ParentProcessId -eq $processInfo.ProcessId) {
            break
        }
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($processInfo.ParentProcessId)"
    }
    if (Get-Process -Id $backendProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $backendProcessId /T /F 2>$null | Out-Null
    }
}
Start-Process powershell.exe -WorkingDirectory $backendPath -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "`$env:HOST='0.0.0.0'; `$env:CORS_ORIGINS='*'; & '$pythonPath' -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
)

Write-Host "Waiting for backend health check..." -ForegroundColor Cyan
$backendReady = $false
for ($attempt = 1; $attempt -le 120; $attempt++) {
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($health.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $backendReady) {
    throw "Backend did not become healthy within 120 seconds. Check the backend service window for startup errors."
}

Write-Host "Starting frontend on all network interfaces at http://0.0.0.0:4173 ..." -ForegroundColor Green
Start-Process powershell.exe -WorkingDirectory $frontendPath -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "& npm run dev -- --host 0.0.0.0"
)

Write-Host "Application started. Open http://<this-computer-ip>:4173 from another device." -ForegroundColor Green
Write-Host "Use Ctrl+C in each service window to stop it." -ForegroundColor DarkGray