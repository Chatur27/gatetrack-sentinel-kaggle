#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev,adk]'
[ -f .env ] || cp .env.example .env
python -m backend.main
