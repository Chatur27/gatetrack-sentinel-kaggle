$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Vite = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"
$BackendHealthUrl = "http://127.0.0.1:8000/api/health"
$FrontendUrl = "http://127.0.0.1:5173"

Write-Host "GateTrack Sentinel RC2.3.8 · v1.2.3.8" -ForegroundColor Cyan

if (-not (Test-Path $Python)) {
    Write-Host "Python environment not found." -ForegroundColor Yellow
    Write-Host "Run .\install_rc2_3_7.ps1 first." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $Vite)) {
    Write-Host "Frontend dependencies are not installed." -ForegroundColor Yellow
    Write-Host "Run .\install_rc2_3_7.ps1, or run npm ci inside frontend." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$BackendCommand = "& `"$Python`" -m backend.main"
$BackendProcess = Start-Process powershell.exe `
    -WorkingDirectory $Root `
    -ArgumentList @("-NoExit", "-Command", $BackendCommand) `
    -PassThru

Write-Host "Waiting for backend health check" -NoNewline
$BackendReady = $false
$BackendTimeoutSeconds = 75

for ($Second = 1; $Second -le $BackendTimeoutSeconds; $Second++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline

    if ($BackendProcess.HasExited) {
        Write-Host ""
        Write-Host "Backend process exited before becoming ready." -ForegroundColor Red
        Write-Host "Review the backend PowerShell window for the exact Python error." -ForegroundColor Yellow
        exit 1
    }

    try {
        $Health = Invoke-RestMethod -Uri $BackendHealthUrl -Method Get -TimeoutSec 2
        if ($Health.status -eq "ok") {
            $BackendReady = $true
            break
        }
    }
    catch {
        # Normal while FastAPI, ADK and MCP are still initialising.
    }
}

Write-Host ""

if (-not $BackendReady) {
    Write-Host "Backend did not answer $BackendHealthUrl within $BackendTimeoutSeconds seconds." -ForegroundColor Red
    Write-Host "Keep the backend window open and inspect its last error message." -ForegroundColor Yellow
    exit 1
}

Write-Host "Backend ready." -ForegroundColor Green
Write-Host "Starting frontend on $FrontendUrl ..." -ForegroundColor Cyan
$FrontendCommand = "npm run dev"
$FrontendProcess = Start-Process powershell.exe `
    -WorkingDirectory (Join-Path $Root "frontend") `
    -ArgumentList @("-NoExit", "-Command", $FrontendCommand) `
    -PassThru

Write-Host "Waiting for frontend" -NoNewline
$FrontendReady = $false
$FrontendTimeoutSeconds = 30

for ($Second = 1; $Second -le $FrontendTimeoutSeconds; $Second++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline

    if ($FrontendProcess.HasExited) {
        Write-Host ""
        Write-Host "Frontend process exited before becoming ready." -ForegroundColor Red
        Write-Host "Review the frontend PowerShell window for the exact Vite error." -ForegroundColor Yellow
        exit 1
    }

    try {
        $Response = Invoke-WebRequest -Uri $FrontendUrl -Method Get -TimeoutSec 2 -UseBasicParsing
        if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
            $FrontendReady = $true
            break
        }
    }
    catch {
        # Normal while Vite is starting.
    }
}

Write-Host ""

if (-not $FrontendReady) {
    Write-Host "Frontend did not answer $FrontendUrl within $FrontendTimeoutSeconds seconds." -ForegroundColor Red
    Write-Host "Review the frontend PowerShell window for the exact Vite error." -ForegroundColor Yellow
    exit 1
}

Write-Host "Frontend ready. Opening GateTrack Sentinel." -ForegroundColor Green
Start-Process $FrontendUrl
Write-Host "Keep both PowerShell windows open while testing." -ForegroundColor Green
