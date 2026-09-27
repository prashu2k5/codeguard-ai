"""
scanner.py — Core scanning logic for the Code Health & Risk Scanner.

IMPORTANT DISCLAIMER
--------------------
All scores produced by this module are *heuristic estimates* based on
code-complexity metrics, git commit history, and test-coverage data.
They are NOT predictions of future failures or guarantees of code quality.
Use them as a starting point for code-review prioritisation, not as a
definitive judgment on any file or developer.

Risk formula (Phase 1)
----------------------
  risk_score = 0.35 × complexity_score
             + 0.35 × churn_score
             + 0.30 × test_gap_score

Each component is normalised to [0, 100] before weighting:
  - complexity_score : based on radon average cyclomatic complexity
  - churn_score      : based on git commit count for the file
  - test_gap_score   : 100 − coverage_percentage  (higher gap = riskier)

The final risk_score is clamped to [0, 100].

Phase 7 extension (risk feedback loop)
---------------------------------------
When db_path is provided (or the default Verified Memory database exists),
scan_repository() also calls enrich_with_feedback() to add per-file fields:
  - verified_incident_count   : PASS incidents from Verified Memory for this file
  - verified_incident_evidence: lightweight summaries of those incidents
  - incident_score            : additive score contribution (min(30, count × 10))
  - observed_risk             : min(100, risk_score + incident_score)
  - observed_risk_level       : Low | Medium | High based on observed_risk
  - is_cold_zone              : True when risk ≥ 35, 0 incidents, not investigated
  - risk_explanation          : human-readable explanation of all signals
  - risk_formula              : transparent formula documentation

The Phase 1 risk_score and risk_level are NEVER modified — only new fields
are added so downstream code that reads risk_score remains unaffected.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from radon.complexity import cc_visit, average_complexity
from radon.metrics import mi_visit


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

def _radon_complexity(file_path: Path) -> float:
    """
    Return a 0–100 complexity score for a Python file using radon.

    Radon cyclomatic complexity grades:
        A (1–5)   → very low
        B (6–10)  → low
        C (11–15) → medium
        D (16–20) → high
        E (21–25) → very high
        F (>25)   → extremely high

    We compute the average CC across all blocks, then scale:
        raw_avg / 25 × 100, clamped to [0, 100].
    """
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        blocks = cc_visit(source)
        if not blocks:
            return 0.0
        avg_cc = average_complexity(blocks)
        # Scale: CC of 25+ maps to 100
        score = min(100.0, (avg_cc / 25.0) * 100.0)
        return round(score, 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Git churn
# ---------------------------------------------------------------------------

def _git_churn(file_path: Path, repo_root: Path) -> int:
    """
    Return the number of git commits that touched this file.
    Returns 0 if the file is not tracked or git is unavailable.
    """
    try:
        relative = file_path.relative_to(repo_root)
        result = subprocess.run(
            ["git", "log", "--oneline", "--", str(relative)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return 0
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return len(lines)
    except Exception:
        return 0


def _normalise_churn(churn: int, max_churn: int) -> float:
    """Normalise raw commit count to [0, 100]."""
    if max_churn == 0:
        return 0.0
    return round(min(100.0, (churn / max_churn) * 100.0), 2)


# ---------------------------------------------------------------------------
# Test coverage
# ---------------------------------------------------------------------------

def _run_coverage(repo_root: Path) -> dict[str, float]:
    """
    Run pytest with coverage inside repo_root and return a dict mapping
    relative file paths (e.g. "utils.py") → coverage percentage.

    Falls back to an empty dict on any error.
    """
    python = sys.executable
    try:
        # Run: python -m coverage run --source=. -m pytest <repo_root>
        run_result = subprocess.run(
            [
                python, "-m", "coverage", "run",
                f"--source={repo_root}",
                "--omit=*/tests/*,*/__init__.py",
                "-m", "pytest", str(repo_root),
                "-q", "--tb=no",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Generate JSON report
        json_result = subprocess.run(
            [python, "-m", "coverage", "json", "-o", "-"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15,
        )

        if json_result.returncode != 0:
            return {}

        import json as _json
        data = _json.loads(json_result.stdout)
        coverage_map: dict[str, float] = {}
        for abs_path, info in data.get("files", {}).items():
            p = Path(abs_path)
            # Store by relative path from repo_root for easy lookup
            try:
                rel = p.relative_to(repo_root)
            except ValueError:
                rel = p
            pct = info.get("summary", {}).get("percent_covered", 0.0)
            coverage_map[str(rel)] = round(pct, 2)

        return coverage_map

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Risk score
# ---------------------------------------------------------------------------

def _risk_score(
    complexity_score: float,
    churn_score: float,
    coverage_pct: float,
) -> float:
    """
    Heuristic risk formula:
      risk = 0.35 × complexity + 0.35 × churn + 0.30 × (100 − coverage)

    All inputs should be in [0, 100]. Output is clamped to [0, 100].
    """
    test_gap = 100.0 - coverage_pct
    raw = 0.35 * complexity_score + 0.35 * churn_score + 0.30 * test_gap
    return round(max(0.0, min(100.0, raw)), 2)


def _risk_level(score: float) -> str:
    if score < 33:
        return "Low"
    if score < 66:
        return "Medium"
    return "High"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_repository(repo_path: str, db_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Scan all Python files in a local repository and return risk scores.

    Parameters
    ----------
    repo_path : absolute or relative path to the repository root
    db_path   : optional path to Verified Memory database for Phase 7
                enrichment (defaults to the production memory.db)

    Returns
    -------
    dict with keys:
        files   : list of per-file result dicts (Phase 1 + Phase 7 fields)
        summary : aggregate statistics
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise ValueError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    # Collect all .py files, excluding test files and __init__ files
    py_files = [
        p for p in root.rglob("*.py")
        if "test" not in p.name.lower()
        and p.name != "__init__.py"
        and ".venv" not in p.parts
    ]

    if not py_files:
        return {
            "files": [],
            "summary": {
                "files_scanned": 0,
                "average_risk": 0.0,
                "highest_risk_files": [],
                "disclaimer": (
                    "No Python source files found. "
                    "Risk scores are heuristic estimates."
                ),
            },
        }

    # Compute raw churn counts first so we can normalise across all files
    raw_churns = {p: _git_churn(p, root) for p in py_files}
    max_churn = max(raw_churns.values()) if raw_churns else 1

    # Run coverage once for all files
    coverage_map = _run_coverage(root)

    results = []
    for file_path in sorted(py_files):
        rel_path = file_path.relative_to(root)
        rel_str = str(rel_path)

        complexity = _radon_complexity(file_path)
        churn_raw = raw_churns[file_path]
        churn_norm = _normalise_churn(churn_raw, max_churn)

        # Try several key formats to find coverage
        coverage_pct = 0.0
        for candidate in [
            rel_str,
            str(rel_path).replace("\\", "/"),
            file_path.name,
        ]:
            if candidate in coverage_map:
                coverage_pct = coverage_map[candidate]
                break

        score = _risk_score(complexity, churn_norm, coverage_pct)
        level = _risk_level(score)

        results.append(
            {
                "file": rel_str,
                "complexity_score": complexity,
                "git_churn_commits": churn_raw,
                "git_churn_score": churn_norm,
                "test_coverage_pct": coverage_pct,
                "risk_score": score,
                "risk_level": level,
            }
        )

    # Phase 7: enrich each file result with verified incident feedback
    try:
        from backend.risk_feedback import enrich_with_feedback
        from backend.memory import DB_PATH as _DEFAULT_DB
        _db = db_path if db_path is not None else _DEFAULT_DB
        results = enrich_with_feedback(results, db_path=_db)
    except Exception:
        # Enrichment failure must NEVER break the base scan results
        pass

    # Summary
    scores = [r["risk_score"] for r in results]
    avg_risk = round(sum(scores) / len(scores), 2) if scores else 0.0
    top_files = sorted(results, key=lambda r: r["risk_score"], reverse=True)[:3]

    # Count cold zones in the enriched results
    cold_zone_count = sum(1 for r in results if r.get("is_cold_zone", False))

    return {
        "files": results,
        "summary": {
            "files_scanned": len(results),
            "average_risk": avg_risk,
            "highest_risk_files": [f["file"] for f in top_files],
            "cold_zone_count": cold_zone_count,
            "disclaimer": (
                "Risk scores are heuristic estimates based on code complexity, "
                "git churn, and test coverage. They are NOT predictions of "
                "failures or guarantees of code quality. "
                "Verified incident counts come from independently verified bugs "
                "in Verified Memory only."
            ),
        },
    }
