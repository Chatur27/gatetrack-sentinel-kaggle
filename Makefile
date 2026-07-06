.PHONY: install install-adk dev-api test lint evaluate evaluate-agent readiness frontend

install:
	python -m pip install -e ".[dev]"

install-adk:
	python -m pip install -e ".[dev,adk]"

dev-api:
	uvicorn backend.main:app --reload --port 8000

test:
	python -m pytest

lint:
	ruff check .

evaluate:
	python scripts/run_evaluation.py

evaluate-agent:
	python scripts/run_agent_evaluation.py

readiness:
	python scripts/check_agent_readiness.py

frontend:
	cd frontend && npm ci && npm run dev
