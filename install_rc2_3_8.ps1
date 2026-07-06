$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "GateTrack Sentinel RC2.3.8 installer" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.12 first."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 20.19+ or 22.12+ first."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev,adk]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Add GEMINI_API_KEY only when testing live mode." -ForegroundColor Yellow
}

Push-Location frontend
try {
    npm ci --registry=https://registry.npmjs.org/
} finally {
    Pop-Location
}

Write-Host "Installation complete. Run .\run_rc2_3_8.ps1" -ForegroundColor Green
