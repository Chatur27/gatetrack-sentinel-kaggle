# GateTrack Sentinel — Kaggle Capstone Edition

![GateTrack Sentinel logo](docs/assets/gatetrack-sentinel-logo.svg)

**AUREX Sentinel Labs · Agents for Business · RC2.3.8 feature-preserved submission-clean release**

GateTrack Sentinel is a synthetic, human-governed visitor risk-triage demonstration. It combines deterministic validation and security controls, a read-only MCP policy server, Google ADK, Gemini, structured-output validation, safe fallback, human decisions, searchable case records, evidence export and reproducible evaluation.

> Educational demonstration only. It does not make legal, regulatory, security, immigration, sanctions or compliance decisions.

## What is complete in RC2.3.8

- Feature-preserved RC2.2 application with a compact 1280×720 desktop profile and internal panel scrolling.
- Routine, elevated-review and unsafe-input scenarios.
- Deterministic validation, security and transparent risk routing.
- Pre-warmed reusable MCP policy connection.
- Single-pass ADK + Gemini grounded review with locked deterministic authority.
- Safe fallback, selective retry, circuit breaking and real attempted-latency evidence.
- Human approve, reject and request-information actions.
- Complete case audit lifecycle and downloadable evidence JSON.
- Searchable case library with status and route filters.
- Thirty-case deterministic evaluation plus an honest five-case live-agent reliability panel with a separate resilience lane.
- Portable Decision Proof Packets that survive browser JSON round trips, plus a standalone verifier and tamper demonstration.
- Smart Replay Lab case recommendations and material-change labels.
- Built-in Loop Observatory with explicit contracts, bounded attempts, no-progress detection, permission enforcement and stop-rule simulations.
- Built-in release Test Lab for feature-by-feature validation and clean-demo reset.
- Docker, Cloud Run guidance, CI, security notes, Kaggle writeup draft and video script.

## Architecture

```text
Synthetic visitor request
        ↓
Validation → pre-model security gate → deterministic route and score
        ↓
Controlled policy identifiers
        ↓
ADK root agent ── reusable MCP stdio ──> read-only policy server
        ↓
Loop contract: goal + permitted tools + attempts + verification + stop state
        ↓
Gemini bounded narrative → local repair → Pydantic and grounding validation
        ├── valid → grounded review
        └── invalid / quota / auth / timeout → safe deterministic fallback
        ↓
Human decision gate → final status → audit evidence → export
```

The model cannot alter the deterministic route, score or triggered factors. Unsafe input is blocked before any model call.

## Application sections

1. **Visitor request** — build and run a synthetic case.
2. **Review queue** — document authorised human decisions.
3. **Case library** — search records and download evidence packs.
4. **Audit viewer** — inspect every workflow event.
5. **Evaluation** — run deterministic and optional live-agent quality checks.
6. **Proof & replay** — verify portable proof, demonstrate tamper detection and run meaningful what-if replays.
7. **Loop control** — inspect loop contracts, run evidence and stop-rule simulations.
8. **Test lab** — validate the complete release feature by feature.

## Repository boundary

This public Kaggle edition excludes AUREX SICOS proprietary methods, client policies, commercial GateTrack code, real visitor information, biometric data and production screening databases.

## Requirements

- Python 3.12 recommended
- Node.js 20.19+ or 22.12+ recommended
- Gemini API key only for live ADK mode

## Windows quick start

```powershell
cd "E:\GITHUB\gatetrack-sentinel-kaggle"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,adk]"
Copy-Item .env.example .env
notepad .env
```

Set the key in `.env` without committing the file:

```env
GTS_MODEL_MODE=adk
GTS_MODEL=gemini-2.5-flash
GEMINI_API_KEY=YOUR_KEY_HERE
```

Start the backend:

```powershell
python scripts/check_agent_readiness.py
python -m backend.main
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm ci --registry=https://registry.npmjs.org/
npm run dev
```

Open `http://127.0.0.1:5173`.

For a clean first-time installation and launch:

```powershell
.\install_rc2_3_8.ps1
.\run_rc2_3_8.ps1
```

The lower-level launcher remains available at `scripts\launch_windows.ps1`.

## Testing

```powershell
python -m pytest
python scripts/run_evaluation.py
python scripts/verify_release.py
python scripts/verify_proof_packet.py path\to\downloaded-proof-packet.json --tamper-demo
cd frontend
npm run build
```

The optional live five-case evaluation is deliberately user-triggered:

```powershell
python scripts/run_agent_evaluation.py
```

## Submission materials

See `docs/submission/` for:

- Kaggle writeup draft;
- five-minute video script;
- demo runbook;
- feature-test checklist;
- judging evidence matrix;
- deployment guide;
- final submission checklist and release audit.

## About the Builders

**GateTrack Sentinel** was developed under **AUREX Sentinel Labs** as a human-governed AI control prototype for synthetic visitor-risk triage, bounded review, audit evidence and proof-carrying decisions.

- **Lead Developer / Co-Founder:** Chaturparsad Baijnath
- **Co-Developer / Founder:** Sarasvadee Kistnen Baijnath

The project reflects a joint founder-led effort to explore practical, auditable and human-supervised AI systems for operational risk, compliance support and responsible decision workflows.

## RC2.3.8 final polish layer

RC2.3.8 applies the final screenshot-driven presentation fixes: the official shield-gate GS logo, improved topbar subtitle spacing, a slightly taller Loop Control Goal panel and README branding alignment. It does not change the deterministic authority model, proof packet schema, evaluation harness, human-review workflow or safe fallback behavior.

## Licence

Apache License 2.0. See `LICENSE`, `NOTICE` and `docs/IP_BOUNDARY.md`.


## RC2.3.8 release layer

- Portable Decision Proof Packet with SHA-256-linked audit events, GTS-CJ-1 canonical JSON and independent verification after browser export.
- Source-confidence map separating declared, controlled, verified, inferred and human-authoritative evidence.
- Policy-conflict map that exposes tensions instead of silently merging them.
- Deterministic Replay Lab with smart case recommendations, material-change labels and explicit control-preservation outcomes.
- Honest live-agent metrics: model-eligible reliability is separated from intentional security bypass and outage resilience.

- Loop contracts record trigger, goal, permitted tools, verification evidence, attempt count, decision, terminal state and stop reason.
- Proof schema v4 cryptographically binds the loop-control map and loop-run evidence to each packet.
- The Loop Laboratory demonstrates pass, bounded retry, no-progress stop and unauthorised-tool blocking.

RC2.3.8 additionally aligns frontend/backend release identity, uses only public NPM package URLs, resets modal state cleanly, exposes honest unverified/loading/offline states, and protects the 1280×720 submission viewport without removing any RC2.2 capability.

See `RC2_3_8_REBUILD_REPORT.md`, `docs/proof-carrying-operations.md` and `docs/loop-engineering.md`.
