$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,adk]"
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
}
python -m backend.main
