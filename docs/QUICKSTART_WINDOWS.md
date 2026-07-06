# Windows quick start — Phase 4

```powershell
cd "E:\GITHUB\gatetrack-sentinel-kaggle"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,adk]"
Copy-Item .env.example .env
notepad .env
```

Set `GTS_MODEL_MODE=adk` and place the Gemini key in `GEMINI_API_KEY`.

Terminal 1:

```powershell
python scripts/check_agent_readiness.py
python -m backend.main
```

Terminal 2:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.
