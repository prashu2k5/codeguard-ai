# Code Health & Risk Scanner — Phase 1

> **Disclaimer:** All risk scores produced by this tool are **heuristic estimates**
> based on code complexity, git commit history, and test coverage.
> They are **not** predictions of future failures or guarantees of code quality.
> Use them as a starting point for code-review prioritisation only.

---

## What it does

The scanner analyses a local Python repository and assigns each `.py` file a
**risk score from 0 to 100** based on three transparent heuristics:

| Heuristic | Weight | Description |
|-----------|--------|-------------|
| Complexity | 35% | Average cyclomatic complexity (via `radon`) |
| Git churn | 35% | Number of commits that touched the file |
| Test gap | 30% | `100 − test_coverage_%` (low coverage = higher gap) |

**Risk levels**

| Score | Level |
|-------|-------|
| 0–32 | 🟢 Low |
| 33–65 | 🟡 Medium |
| 66–100 | 🔴 High |

---

## Risk formula

```
risk_score = 0.35 × complexity_score   (0–100, normalised CC)
           + 0.35 × churn_score        (0–100, normalised commit count)
           + 0.30 × test_gap_score     (0–100, = 100 − coverage%)

Final score clamped to [0, 100].
```

Each component is normalised relative to the maximum observed value in the
repository being scanned, so scores are always relative to the repo at hand.

---

## Project structure

```
bob-health/
├── backend/
│   ├── __init__.py
│   ├── main.py        ← FastAPI app (GET /, POST /scan)
│   └── scanner.py     ← Scanning logic
├── demo_repo/
│   ├── __init__.py
│   ├── utils.py           low complexity, low churn, 100% coverage
│   ├── data_processor.py  moderate complexity, some churn, 85% coverage
│   ├── risk_engine.py     high complexity, high churn, 94% coverage
│   ├── reporter.py        low complexity, low churn, 0% coverage (gap demo)
│   └── tests/
│       ├── __init__.py
│       └── test_demo.py   25 tests for the demo modules
└── README.md
```

---

## Requirements

All dependencies are installed in `.venv`:

```
fastapi     uvicorn     radon     gitpython
pytest      coverage    pydantic
```

---

## How to run

### 1. Start the server

```bash
# From the bob-health directory
uvicorn backend.main:app --reload
```

The server starts at **http://127.0.0.1:8000**.

### 2. Check it is running

```bash
curl http://127.0.0.1:8000/
```

Expected response:
```json
{
  "status": "ok",
  "service": "Code Health & Risk Scanner",
  "version": "0.1.0",
  "message": "Scanner is running. POST /scan with {\"repo_path\": \"<path>\"} to analyse a repository."
}
```

---

## How to scan the demo repository

```bash
curl -X POST http://127.0.0.1:8000/scan \
     -H "Content-Type: application/json" \
     -d '{"repo_path": "demo_repo"}'
```

Or with PowerShell:

```powershell
$body = '{"repo_path": "demo_repo"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/scan `
    -Method POST -Body $body -ContentType "application/json" |
    ConvertTo-Json -Depth 10
```

### Expected output (approximate)

```json
{
  "files": [
    {
      "file": "data_processor.py",
      "complexity_score": 13.6,
      "git_churn_commits": 3,
      "git_churn_score": 50.0,
      "test_coverage_pct": 84.62,
      "risk_score": 26.87,
      "risk_level": "Low"
    },
    {
      "file": "reporter.py",
      "complexity_score": 5.33,
      "git_churn_commits": 1,
      "git_churn_score": 16.67,
      "test_coverage_pct": 0.0,
      "risk_score": 37.7,
      "risk_level": "Medium"
    },
    {
      "file": "risk_engine.py",
      "complexity_score": 20.8,
      "git_churn_commits": 6,
      "git_churn_score": 100.0,
      "test_coverage_pct": 93.75,
      "risk_score": 44.16,
      "risk_level": "Medium"
    },
    {
      "file": "utils.py",
      "complexity_score": 5.0,
      "git_churn_commits": 1,
      "git_churn_score": 16.67,
      "test_coverage_pct": 100.0,
      "risk_score": 7.58,
      "risk_level": "Low"
    }
  ],
  "summary": {
    "files_scanned": 4,
    "average_risk": 29.08,
    "highest_risk_files": ["risk_engine.py", "reporter.py", "data_processor.py"],
    "disclaimer": "Risk scores are heuristic estimates..."
  }
}
```

### Why are the scores different?

| File | Story |
|------|-------|
| `utils.py` | Simple functions, 1 commit, 100% tested → **Low (7.6)** |
| `data_processor.py` | Moderate complexity, 3 commits, 85% tested → **Low (26.9)** |
| `reporter.py` | Low complexity but **0% coverage** → **Medium (37.7)** |
| `risk_engine.py` | Highest complexity, 6 commits, 94% covered → **Medium (44.2)** |

---

## Interactive API docs

FastAPI auto-generates documentation at:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

---

## Run the demo tests

```bash
# Run tests only
python -m pytest demo_repo/tests/ -v

# Run with coverage report
python -m coverage run --source=demo_repo --omit="*/tests/*" -m pytest demo_repo/tests/ -q
python -m coverage report --include="demo_repo/*.py"
```

---

## Scanning your own repository

```bash
curl -X POST http://127.0.0.1:8000/scan \
     -H "Content-Type: application/json" \
     -d '{"repo_path": "/absolute/path/to/your/repo"}'
```

Requirements for a meaningful scan:
- The path must be a git repository (`git log` is used for churn)
- Python files must exist outside of `tests/` directories
- For coverage, a `pytest`-compatible test suite is needed

---

## Phase 2 (not built yet)

Planned next steps:
- React/HTML frontend to visualise the risk scores
- AI-powered code review suggestions
- Historical tracking across scans
- GitHub integration
