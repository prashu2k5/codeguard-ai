# CodeGuard AI

> **Disclaimer:** All risk scores produced by this tool are **heuristic estimates** based on
> code complexity, git commit history, and test coverage. They are **not** predictions of future
> failures or guarantees of code quality. Use them as a starting point for code-review
> prioritisation and investigation only.

---

## What is CodeGuard AI?

CodeGuard AI is a local-first, hackathon-grade code quality assistant that connects six
distinct capabilities into a single transparent loop:

```
Find risk  →  Investigate bugs  →  Verify fixes  →  Remember knowledge  →  Reuse safely  →  Update risk evidence
```

It is built to demonstrate that **evidence-based software quality tooling** does not require
external AI APIs, cloud infrastructure, or fabricated data. Every score is auditable, every
fix requires independent test verification, and every stored incident has a clear provenance.

---

## The Problem

Code review tools either:
- score files with opaque ML models (black box, unauditable), or
- claim AI "verified" a fix without running a single test.

Neither approach builds trust with engineers or stakeholders.

---

## The Solution

CodeGuard AI uses four transparent, composable layers:

| Layer | What it does | What it does NOT do |
|-------|-------------|---------------------|
| **Risk Scanner** | Heuristic estimate from complexity + churn + coverage | Predict bugs |
| **Bug Investigator** | Pattern-based or AI analysis of root cause | Verify anything |
| **Verification Engine** | Three-stage automated test gate | Trust the AI blindly |
| **Verified Memory** | Store only PASS incidents; surface with re-verify warnings | Auto-apply fixes |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Repository                        │
│  (Python source files + git history + tests)        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              Code Health Scanner (Phase 1)          │
│  complexity_score + churn_score + test_gap_score    │
│  → predicted risk_score (0–100, heuristic estimate) │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              React Dashboard (Phase 2)              │
│  Risk table · Chart · File detail panel             │
└──────┬──────────────┬──────────────────────────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌────────────────────────────────────┐
│  Cold Zone │  │      Bug Investigation (Phase 3)   │
│ Detection  │  │  AI-assisted or heuristic fallback  │
│ (Phase 7)  │  │  → root cause + fix candidate       │
└────────────┘  └─────────────────┬──────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │     Verification Engine (Phase 4)   │
                │  Stage 1: bug reproduced (FAIL)      │
                │  Stage 2: fix applied (PASS)         │
                │  Stage 3: regression suite (PASS)    │
                │  verified = true only if all 3 pass  │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │      Verified Memory (Phase 5)      │
                │  SQLite · PASS-only · with warnings  │
                └──────┬──────────────────────────────┘
                       │
                       ▼
                ┌──────────────────────────────────────┐
                │   Memory Context (Phase 6)           │
                │  Keyword search · Similar incidents  │
                │  Always shows re-verify warning      │
                └──────┬───────────────────────────────┘
                       │
                       ▼
                ┌──────────────────────────────────────┐
                │   Risk Feedback Loop (Phase 7)       │
                │  incident_score = min(30, count×10)  │
                │  observed_risk = predicted + inc_score│
                │  Cold Zone = risk≥35 + 0 incidents   │
                └──────┬───────────────────────────────┘
                       │
                       ▼
                ┌──────────────────────────────────────┐
                │   Updated Risk Dashboard (Phase 8)  │
                │  Predicted · Evidence · Observed     │
                │  Demo Guide · System Status          │
                └──────────────────────────────────────┘
```

---

## Phase-by-Phase Capabilities

| Phase | Capability | Key output |
|-------|-----------|------------|
| 1 | Code Health Scanner | `risk_score` per file (0–100) |
| 2 | React Dashboard | Visual risk table + chart |
| 3 | AI Bug Investigation | Root cause + fix candidate |
| 4 | Independent Fix Verification | `verified = true` (three-stage gate) |
| 5 | Verified Memory | SQLite store, PASS-only |
| 6 | Memory Context | Similar incident retrieval |
| 7 | Risk Feedback Loop | `observed_risk` + Cold Zones |
| 8 | Demo Polish | System status, Demo Guide, README |

---

## Risk Formula

### Phase 1 — Predicted Risk (unchanged throughout all phases)

```
predicted_risk = 0.35 × complexity_score
               + 0.35 × churn_score
               + 0.30 × (100 − coverage_pct)

Clamped to [0, 100].
```

| Signal | Source | Normalisation |
|--------|--------|---------------|
| `complexity_score` | radon average cyclomatic complexity | `/25 × 100`, capped at 100 |
| `churn_score` | git commit count for the file | `/ max_churn × 100` |
| `test_gap_score` | `100 − coverage_percentage` | direct |

### Phase 7 — Observed Risk (additive, transparent)

```
incident_score = min(30, verified_incident_count × 10)
observed_risk  = min(100, predicted_risk + incident_score)
```

| Verified incidents | Contribution |
|--------------------|-------------|
| 0 | +0 pts |
| 1 | +10 pts |
| 2 | +20 pts |
| 3+ | +30 pts (capped) |

> The Phase 1 `risk_score` is **never modified**. `observed_risk` is an additional field.

### Risk levels

| Score | Level |
|-------|-------|
| 0–32 | 🟢 Low |
| 33–65 | 🟡 Medium |
| 66–100 | 🔴 High |

---

## Verification Workflow

```
BEFORE  ❌  Bug reproduced — test FAILS with original code
  FIX   🔧  Candidate fix applied to source
 AFTER  ✅  Same test PASSES with fix applied
 SUITE  ✅  Full regression suite still passes (nothing regressed)

RESULT  ✅  Fix independently verified by automated tests
```

Only when all three stages pass is `verified = true` and the incident is eligible
for Verified Memory. **The original file is always restored after verification.**

---

## Verified Memory

```
Safety gate: verification_result == "PASS" is required to store any incident.
Storage:     SQLite (backend/memory.db)
Schema:      id, repository, file_path, function_name, problem, root_cause,
             fix, regression_test, verification_result, before_output,
             after_output, created_at
```

**Memory is evidence — not automatic truth.**

When a stored incident is returned as a match for a new problem, the system always
displays:

> "Memory is evidence, NOT automatic truth. Re-check the current code before reusing
> the fix. A stored fix is not automatically verified for a new bug."

---

## Cold Zones

A **Cold Zone** is a file where:

1. `risk_score >= 35` (elevated predicted risk)
2. `verified_incident_count == 0` (no verified knowledge yet)
3. Not investigated in the current session

Cold Zones are **prioritisation signals — not proof of bugs.**

> "No verified incident" does NOT mean "safe." It means the area has not yet been
> investigated and verified.

---

## Safety Principles

- Verified incidents come **only** from the automated test verification gate.
- Non-PASS incidents are **never** stored in Verified Memory.
- Memory is **evidence** — every retrieval shows a re-verify warning.
- Phase 1 `risk_score` is **never silently changed** by Phase 7.
- Fix verification **always restores** the original file after testing.
- No AI claim is presented as verified unless automated tests confirm it.
- All risk scores are **heuristic estimates** — not predictions of failures.

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the React frontend)
- Git (for churn signal)

### Setup

```bash
# Clone or navigate to the project
cd codeguard-ai

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install Python dependencies
pip install fastapi uvicorn radon gitpython pytest coverage pydantic httpx2 starlette

# Install frontend dependencies (from the frontend/ directory)
cd frontend
npm install
cd ..
```

---

## Running the Project

### 1. Start the backend

```bash
# From the codeguard-ai/ directory, with .venv active
uvicorn backend.main:app --reload
```

The API starts at **http://127.0.0.1:8000**

### 2. Start the frontend

```bash
# From codeguard-ai/frontend/
npm run dev
```

The dashboard opens at **http://localhost:5173**

### 3. Verify the backend is running

```bash
curl http://127.0.0.1:8000/
```

Expected:
```json
{
  "status": "ok",
  "service": "CodeGuard AI",
  "version": "1.0.0"
}
```

---

## Demo Workflow

Follow these steps for a complete end-to-end demonstration:

1. **Open** the dashboard at `http://localhost:5173`
2. **Read the Demo Guide** (tab in the header) to understand the workflow
3. **Check System Status** — all 7 capabilities show ✓ Operational
4. **Click "Scan Repository"** — scans `demo_repo/` and shows risk scores
5. **Observe Cold Zones** — files with elevated risk and no verified incidents
6. **Click `data_processor.py`** — the highest-risk file
7. **Click "Investigate Bug"** — root cause and fix candidate appear
8. **Read the explanation** — see Predicted Risk vs Verified Evidence vs Observed Risk
9. **Click "Verify Fix"** — runs the three-stage automated test gate:
   - BEFORE: test FAILS (bug reproduced)
   - FIX: candidate applied
   - AFTER: test PASSES
   - SUITE: full regression passes
10. **Observed: `verified = true`**
11. **Click "Save to Verified Memory"**
12. **Open "Verified Memory" tab** — see the stored incident with full metadata
13. **Search memory** — type "normalize" or "zero division"
14. **Re-scan** — Cold Zone count for `data_processor.py` changes
15. **Open file again** — Verified Incident Evidence section now shows the stored incident
16. **Observed Risk** is updated with the incident contribution
17. **Investigate another file** — see that memory context surfaces the past incident

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check, version, phase list |
| POST | `/scan` | Scan repository — returns risk scores + Phase 7 fields |
| POST | `/investigate` | Investigate a single file for bugs |
| POST | `/verify-fix` | Run 3-stage verification gate |
| POST | `/memory/save` | Save a PASS incident to Verified Memory |
| GET | `/memory` | List all verified incidents |
| POST | `/memory/search` | Keyword search over verified incidents |
| POST | `/memory/context` | Get memory context for a file/function/problem |
| POST | `/cold-zones` | Detect Cold Zones in a repository |
| POST | `/risk-feedback` | Phase 7 enriched risk feedback per file |
| GET | `/demo/status` | System status for all 7 capabilities |
| POST | `/demo/reset-session` | Reset session investigation state (safe — no DB changes) |

Interactive API docs: **http://127.0.0.1:8000/docs**

---

## Running Tests

```bash
# From codeguard-ai/ with .venv active
python -m pytest backend/tests/ -v
```

### Test summary

| Test file | Coverage |
|-----------|---------|
| `test_investigate.py` | Phase 3 — AI investigation, fallback mode, endpoint |
| `test_memory.py` | Phase 5 — save/list/search, safety gate, endpoints |
| `test_memory_context.py` | Phase 6 — similar incidents, re-verify warnings |
| `test_verify.py` | Phase 4 — 3-stage gate, file restoration, endpoint |
| `test_risk_feedback.py` | Phase 7 — formula, enrichment, cold zones, endpoints |

**Expected planted-bug behaviour:** `test_normalize_wrong_result` and
`test_normalize_zero_division` in `test_investigate.py` demonstrate that the planted
bug in `demo_repo/data_processor.py` actually fails — this is intentional.

---

## Project Structure

```
codeguard-ai/
├── backend/
│   ├── main.py             FastAPI application (all endpoints)
│   ├── scanner.py          Phase 1 risk scanner
│   ├── ai_service.py       Phase 3 AI investigation + fallback
│   ├── verifier.py         Phase 4 verification engine
│   ├── memory.py           Phase 5 Verified Memory (SQLite)
│   ├── memory_context.py   Phase 6 similar incident retrieval
│   ├── cold_zones.py       Phase 7 Cold Zone detection
│   ├── risk_feedback.py    Phase 7 risk feedback loop
│   ├── memory.db           SQLite database (auto-created)
│   └── tests/
│       ├── test_investigate.py
│       ├── test_memory.py
│       ├── test_memory_context.py
│       ├── test_verify.py
│       └── test_risk_feedback.py
├── frontend/
│   └── src/
│       ├── App.jsx                 Main app + routing
│       ├── components/
│       │   ├── Header.jsx          Navigation + backend status
│       │   ├── SummaryCards.jsx    Risk + cold zone + incident counts
│       │   ├── RiskChart.jsx       Predicted + observed risk bars
│       │   ├── RiskTable.jsx       File table with Phase 7 columns
│       │   ├── FileDetail.jsx      Full detail panel (A→G sections)
│       │   ├── MemoryPage.jsx      Verified Memory browser
│       │   ├── DemoGuide.jsx       Phase 8 demo guide
│       │   ├── SystemStatus.jsx    Phase 8 system status panel
│       │   ├── ScanButton.jsx      Scan trigger
│       │   ├── Disclaimer.jsx      Heuristic disclaimer
│       │   └── ...
│       └── styles/app.css
├── demo_repo/
│   ├── data_processor.py   Contains planted bug (normalize off-by-one)
│   ├── utils.py
│   ├── risk_engine.py
│   ├── reporter.py
│   └── tests/
└── README.md
```

---

## Limitations

- **Python files only** — the scanner and investigator only work on `.py` files.
- **Heuristic risk only** — scores are estimates, not predictions. A low score does not mean safe.
- **Keyword-based memory search** — not semantic/ML similarity.
- **Single fixed-file verification** — the Phase 4 gate is configured for `data_processor.py`.
- **Local only** — no cloud deployment, no authentication, no multi-user support.
- **Session-scoped investigation state** — resets on server restart.

---

## Future Improvements

- Support for non-Python languages (TypeScript, Go, Java)
- Semantic/embedding-based memory search
- Configurable verification scripts per repository
- Multi-file verification gate
- Historical risk trend tracking across scans
- GitHub PR integration
- Team-level incident knowledge base
- Persistent investigation state (not session-scoped)

---

## Exact Commands to Run

```bash
# 1. Activate virtual environment (Windows)
cd codeguard-ai
.venv\Scripts\activate

# 2. Start backend
uvicorn backend.main:app --reload

# 3. (New terminal) Start frontend
cd frontend
npm run dev

# 4. Run all tests
python -m pytest backend/tests/ -v

# 5. Check API
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/demo/status
```

---

*CodeGuard AI — Hackathon project demonstrating transparent, evidence-based code quality tooling.*
*All risk scores are heuristic estimates. Fixes are only trusted after independent automated test verification.*
