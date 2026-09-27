"""
main.py — FastAPI application for the Code Health & Risk Scanner.

Start with:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.scanner import scan_repository
from backend.ai_service import investigate
from backend.verifier import verify_fix
from backend.memory import (
    save as memory_save,
    list_all as memory_list,
    search as memory_search,
    count as memory_count,
    VerifiedIncident,
    DB_PATH as MEMORY_DB_PATH,
)
from backend.memory_context import search_for_similar, memory_context as build_memory_context
from backend.cold_zones import (
    detect_cold_zones,
    mark_investigated,
    is_investigated,
    reset_investigated,
    classify_file,
    get_investigated_files,
    COLD_ZONE_THRESHOLD,
)
from backend.risk_feedback import enrich_with_feedback

app = FastAPI(
    title="CodeGuard AI",
    description=(
        "CodeGuard AI — Find risk. Investigate bugs. Verify fixes. Remember knowledge. "
        "All risk scores are heuristic estimates — not predictions or guarantees."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    repo_path: str


class InvestigateRequest(BaseModel):
    repo_path: str
    file_path: str
    bug_description: str = ""


class VerifyFixRequest(BaseModel):
    repo_path: str
    file_path: str


class SaveMemoryRequest(BaseModel):
    repository:      str
    file_path:       str
    function_name:   str = ""
    problem:         str
    root_cause:      str
    fix:             str
    regression_test: str = ""
    before_output:   str = ""
    after_output:    str = ""
    # Safety: only "PASS" is accepted — enforced in memory.save()
    verification_result: str = "PASS"


class MemorySearchRequest(BaseModel):
    query:     str
    file_path: str = ""


class MemoryContextRequest(BaseModel):
    file_path:     str
    function_name: str = ""
    problem:       str = ""


class ColdZonesRequest(BaseModel):
    repo_path: str
    # Optionally accept pre-computed files list to avoid a double scan
    files: list[dict] = []


class RiskFeedbackRequest(BaseModel):
    repo_path: str
    # Optionally accept pre-computed files list to avoid a double scan
    files: list[dict] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root() -> dict:
    """Health check — confirms the scanner is running."""
    return {
        "status": "ok",
        "service": "CodeGuard AI",
        "version": "1.0.0",
        "message": (
            "CodeGuard AI is running. "
            "POST /scan with {\"repo_path\": \"<path>\"} to analyse a repository."
        ),
        "phases": {
            "phase_1": "Code Health & Risk Scanner",
            "phase_2": "React Dashboard",
            "phase_3": "AI Bug Investigation",
            "phase_4": "Independent Fix Verification",
            "phase_5": "Verified Memory",
            "phase_6": "Memory Context & Similar Incidents",
            "phase_7": "Risk Feedback Loop",
            "phase_8": "Final Integration & Demo Polish",
        },
        "disclaimer": (
            "Risk scores are heuristic estimates only — "
            "not predictions of failures or guarantees of code quality."
        ),
    }


@app.post("/scan")
def scan(request: ScanRequest) -> dict:
    """
    Scan a local Python repository and return risk scores for each file.

    Body
    ----
    {
        "repo_path": "/absolute/or/relative/path/to/repo"
    }

    Response
    --------
    {
        "files": [
            {
                "file": "relative/path.py",
                "complexity_score": 0–100,
                "git_churn_commits": <int>,
                "git_churn_score": 0–100,
                "test_coverage_pct": 0–100,
                "risk_score": 0–100,
                "risk_level": "Low" | "Medium" | "High"
            },
            ...
        ],
        "summary": {
            "files_scanned": <int>,
            "average_risk": 0–100,
            "highest_risk_files": ["path.py", ...],
            "disclaimer": "..."
        }
    }
    """
    repo_path = request.repo_path.strip()
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path must not be empty.")

    # Resolve to absolute path — accept paths relative to current working dir
    resolved = Path(repo_path)
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    resolved = resolved.resolve()

    if not resolved.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Path not found: {resolved}",
        )
    if not resolved.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {resolved}",
        )

    try:
        result = scan_repository(str(resolved))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Scan failed: {exc}",
        )

    # Phase 7: fresh scan resets investigation state so cold zones are recalculated
    reset_investigated()

    return result


@app.post("/investigate")
def investigate_file(request: InvestigateRequest) -> dict:
    """
    Run an AI-powered bug investigation on a single Python file.

    Body
    ----
    {
        "repo_path": "demo_repo",
        "file_path": "data_processor.py",
        "bug_description": "optional hint"   // optional
    }

    Response
    --------
    {
        "file": "...",
        "problem": "...",
        "root_cause": "...",
        "evidence": "...",
        "suggested_fix": "...",
        "confidence": "High|Medium|Low",
        "mode": "ai-assisted|fallback-heuristic",
        "disclaimer": "..."
    }
    """
    repo_path = request.repo_path.strip()
    file_path = request.file_path.strip()

    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path must not be empty.")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path must not be empty.")

    # Resolve repo root
    root = Path(repo_path)
    if not root.is_absolute():
        root = Path.cwd() / root
    root = root.resolve()

    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail=f"Repo path not found: {root}")

    # Resolve target file (allow both relative-to-repo and relative-to-cwd)
    target = Path(file_path)
    if not target.is_absolute():
        candidate = root / target
        if candidate.exists():
            target = candidate
        else:
            target = (Path.cwd() / target).resolve()
    target = target.resolve()

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
    if target.suffix != ".py":
        raise HTTPException(status_code=400, detail="Only .py files are supported.")

    try:
        source_code = target.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read file: {exc}")

    # Use the relative path for labelling in the result
    try:
        label = str(target.relative_to(root))
    except ValueError:
        label = target.name

    try:
        result = investigate(
            file_path=label,
            source_code=source_code,
            bug_description=request.bug_description,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Investigation failed: {exc}")

    response = result.to_dict()

    # Phase 6: search verified memory for similar past incidents
    try:
        similar = search_for_similar(
            file_path=label,
            function_name="",          # extracted heuristically by memory_context
            problem=result.problem,
            root_cause=result.root_cause,
            bug_description=request.bug_description,
        )
        response["similar_incidents"] = similar
        response["memory_context_note"] = (
            "Similar incidents are EVIDENCE from verified history. "
            "They do NOT verify the current issue. "
            "Fresh independent verification (POST /verify-fix) is always required."
        )
    except Exception:
        # Memory search failure must never break the investigation response
        response["similar_incidents"] = []
        response["memory_context_note"] = "Memory search unavailable."

    # Phase 7: mark this file as investigated in the current session
    # (investigation != verification — these are separate states)
    mark_investigated(label)
    response["investigated"] = True

    return response


@app.post("/verify-fix")
def verify_fix_endpoint(request: VerifyFixRequest) -> dict:
    """
    Run a controlled before/fix/after verification sequence for a known bug.

    Body
    ----
    {
        "repo_path": "demo_repo",
        "file_path": "data_processor.py"
    }

    Response
    --------
    {
        "file": "...",
        "fix_description": "...",
        "before": {
            "test_result": "FAIL",
            "output": "...",
            "tests_passed": 0,
            "tests_failed": 5
        },
        "after": {
            "test_result": "PASS",
            "output": "...",
            "tests_passed": 8,
            "tests_failed": 0
        },
        "regression_suite": {
            "result": "PASS",
            "output": "...",
            "tests_passed": 24,
            "tests_failed": 0
        },
        "verified": true,
        "failure_reason": "",
        "disclaimer": "Fix independently verified by automated tests..."
    }

    SAFETY: verified=true only when before=FAIL, after=PASS, suite=PASS.
    The original source file is ALWAYS restored after verification.
    """
    repo_path = request.repo_path.strip()
    file_path = request.file_path.strip()

    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path must not be empty.")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path must not be empty.")

    root = Path(repo_path)
    if not root.is_absolute():
        root = Path.cwd() / root
    root = root.resolve()

    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail=f"Repo path not found: {root}")

    try:
        result = verify_fix(str(root), file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verification failed unexpectedly: {exc}")

    return result.to_dict()


# ---------------------------------------------------------------------------
# Memory endpoints (Phase 5)
# ---------------------------------------------------------------------------

@app.post("/memory/save")
def save_to_memory(request: SaveMemoryRequest) -> dict:
    """
    Save a VERIFIED incident to persistent memory.

    SAFETY: only incidents with verification_result == "PASS" are accepted.
    Attempting to save a non-PASS incident returns HTTP 400.

    Body
    ----
    {
        "repository":          "demo_repo",
        "file_path":           "data_processor.py",
        "function_name":       "normalize",
        "problem":             "...",
        "root_cause":          "...",
        "fix":                 "...",
        "regression_test":     "...",
        "before_output":       "...",
        "after_output":        "...",
        "verification_result": "PASS"
    }
    """
    if request.verification_result != "PASS":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot save incident with verification_result="
                f"{request.verification_result!r}. "
                "Only PASS incidents may be stored in Verified Memory."
            ),
        )

    incident = VerifiedIncident(
        repository=request.repository,
        file_path=request.file_path,
        function_name=request.function_name,
        problem=request.problem,
        root_cause=request.root_cause,
        fix=request.fix,
        regression_test=request.regression_test,
        verification_result=request.verification_result,
        before_output=request.before_output,
        after_output=request.after_output,
    )

    try:
        new_id = memory_save(incident)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save incident: {exc}")

    return {
        "saved": True,
        "id": new_id,
        "message": "Verified incident saved to memory.",
        "warning": (
            "Memory is evidence, NOT automatic truth. "
            "Re-verify any fix before applying it to a new codebase."
        ),
    }


@app.get("/memory")
def get_memory() -> dict:
    """
    Return all stored verified incidents, newest first.
    """
    try:
        incidents = memory_list()
        total = memory_count()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read memory: {exc}")

    return {
        "total": total,
        "incidents": [i.to_dict() for i in incidents],
        "warning": (
            "Memory is evidence, NOT automatic truth. "
            "Re-verify any fix before applying it to a new codebase."
        ),
    }


@app.post("/memory/search")
def search_memory(request: MemorySearchRequest) -> dict:
    """
    Search verified memory using basic keyword matching.

    Body
    ----
    {
        "query":     "normalize zero division",
        "file_path": "data_processor.py"   // optional
    }

    The relevance_score in results is a SIMPLE keyword hit count.
    It is NOT ML similarity or semantic search.

    SAFETY: Results include a memory_warning reminding callers that a
    stored fix must NEVER be automatically marked verified for a new bug.
    """
    query = request.query.strip()
    if not query and not request.file_path.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide at least a query or a file_path to search.",
        )

    try:
        results = memory_search(query=query, file_path=request.file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    return {
        "query": query,
        "file_path_filter": request.file_path,
        "total_matches": len(results),
        "results": results,
        "search_note": (
            "Results ranked by basic keyword match score — NOT semantic similarity. "
            "Always re-verify a fix before applying it to a new problem."
        ),
    }


@app.post("/memory/context")
def memory_context_endpoint(request: MemoryContextRequest) -> dict:
    """
    Retrieve verified memory context for a given file/function/problem.

    Body
    ----
    {
        "file_path":     "data_processor.py",
        "function_name": "normalize",
        "problem":       "normalization produces incorrect values"
    }

    Response
    --------
    {
        "file_path":     "...",
        "function_name": "...",
        "problem":       "...",
        "matches":       [ { ... similar_incident ... } ],
        "total_matches": 0,
        "search_note":   "Basic keyword match — NOT ML or semantic similarity.",
        "safety_notice": "...",
        "current_verified": false,
        "current_verified_reason": "..."
    }

    SAFETY: current_verified is ALWAYS false in this response.
    Only POST /verify-fix can produce a verified=true result.
    """
    file_path     = request.file_path.strip()
    function_name = request.function_name.strip()
    problem       = request.problem.strip()

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path must not be empty.")

    try:
        ctx = build_memory_context(
            file_path=file_path,
            function_name=function_name,
            problem=problem,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Memory context failed: {exc}")

    return ctx


@app.post("/cold-zones")
def cold_zones_endpoint(request: ColdZonesRequest) -> dict:
    """
    Identify Cold Zones in a repository.

    A Cold Zone is a file where:
      * risk_score >= threshold (default: 35)
      * no verified incident exists in memory for that file
      * the file has not been investigated in the current session

    Cold Zones are prioritisation signals — NOT proof of bugs.

    Body
    ----
    {
        "repo_path": "demo_repo",
        "files": []   // optional — pass scan results to avoid re-scanning
    }

    Response
    --------
    {
        "cold_zones": [
            {
                "file_path": "...",
                "risk_score": 0–100,
                "risk_level": "...",
                "investigated": false,
                "verified_incident_count": 0,
                "reason": "...",
                "disclaimer": "..."
            }
        ],
        "threshold": 35,
        "total_cold_zones": 0,
        "investigated_files": [...],
        "disclaimer": "..."
    }
    """
    repo_path = request.repo_path.strip()
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path must not be empty.")

    # Use provided files list or re-scan
    files = request.files
    if not files:
        root = Path(repo_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        root = root.resolve()

        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=404, detail=f"Repo path not found: {root}")

        try:
            scan_result = scan_repository(str(root))
            files = scan_result.get("files", [])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")

    try:
        cold = detect_cold_zones(files)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cold-zone detection failed: {exc}")

    return {
        "cold_zones":        [z.to_dict() for z in cold],
        "total_cold_zones":  len(cold),
        "threshold":         COLD_ZONE_THRESHOLD,
        "investigated_files": sorted(list(get_investigated_files())),
        "disclaimer": (
            "Cold Zones are prioritisation signals, NOT proof of bugs. "
            "They identify areas with elevated estimated risk where the system "
            "has not yet recorded a verified incident or completed an investigation. "
            "Use wording: 'Potentially under-investigated risk area.'"
        ),
    }


@app.post("/risk-feedback")
def risk_feedback_endpoint(request: RiskFeedbackRequest) -> dict:
    """
    Return Phase 7 risk feedback for a repository's files.

    For each file this endpoint returns:
      - All Phase 1 heuristic signals (unchanged)
      - verified_incident_count  : PASS incidents from Verified Memory
      - verified_incident_evidence: summaries of those incidents
      - incident_score           : additive score (min(30, count × 10))
      - observed_risk            : predicted_risk + incident_score, capped at 100
      - observed_risk_level      : Low | Medium | High
      - is_cold_zone             : True when risk ≥ 35, 0 incidents, uninvestigated
      - risk_explanation         : human-readable explanation

    SAFETY
    ------
    Verified incidents come ONLY from Verified Memory (SQLite). Only incidents
    that passed the full verification gate (before=FAIL, after=PASS,
    suite=PASS, verification_result=PASS) are counted.
    Non-PASS incidents are never counted as evidence.

    Formula
    -------
    predicted_risk = 0.35×complexity + 0.35×churn + 0.30×test_gap   [Phase 1]
    incident_score = min(30, verified_incident_count × 10)           [Phase 7]
    observed_risk  = min(100, predicted_risk + incident_score)        [Phase 7]

    Body
    ----
    {
        "repo_path": "demo_repo",
        "files": []     // optional — pass pre-computed scan results
    }

    Response
    --------
    {
        "files": [
            {
                "file": "...",
                // Phase 1 fields (unchanged)
                "complexity_score": 0–100,
                "git_churn_commits": <int>,
                "git_churn_score": 0–100,
                "test_coverage_pct": 0–100,
                "risk_score": 0–100,
                "risk_level": "Low|Medium|High",
                // Phase 7 fields (new)
                "verified_incident_count": <int>,
                "verified_incident_evidence": [...],
                "incident_score": 0–30,
                "observed_risk": 0–100,
                "observed_risk_level": "Low|Medium|High",
                "is_cold_zone": true|false,
                "risk_explanation": "...",
                "risk_formula": "...",
                "disclaimer": "..."
            }
        ],
        "summary": {
            "files_scanned": <int>,
            "total_verified_incidents": <int>,
            "cold_zone_count": <int>,
            "formula_note": "...",
            "disclaimer": "..."
        }
    }
    """
    repo_path = request.repo_path.strip()
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path must not be empty.")

    files = request.files
    if not files:
        root = Path(repo_path)
        if not root.is_absolute():
            root = Path.cwd() / root
        root = root.resolve()

        if not root.exists() or not root.is_dir():
            raise HTTPException(status_code=404, detail=f"Repo path not found: {root}")

        try:
            # Use raw scan without Phase 7 enrichment to avoid double enrichment
            from backend.scanner import scan_repository as _scan
            raw = _scan(str(root))
            # raw["files"] already has Phase 7 fields from scanner.py integration
            # but we return them directly here for the dedicated endpoint
            files = raw.get("files", [])
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")

    # If caller passed raw Phase 1 files (no Phase 7 fields yet), enrich them
    if files and "verified_incident_count" not in files[0]:
        try:
            files = enrich_with_feedback(files, db_path=MEMORY_DB_PATH)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Risk feedback enrichment failed: {exc}")

    total_verified = sum(f.get("verified_incident_count", 0) for f in files)
    cold_zone_count = sum(1 for f in files if f.get("is_cold_zone", False))

    return {
        "files": files,
        "summary": {
            "files_scanned":          len(files),
            "total_verified_incidents": total_verified,
            "cold_zone_count":        cold_zone_count,
            "formula_note": (
                "predicted_risk = 0.35×complexity + 0.35×churn + 0.30×test_gap  [Phase 1]\n"
                "incident_score = min(30, verified_incident_count × 10)          [Phase 7]\n"
                "observed_risk  = min(100, predicted_risk + incident_score)       [Phase 7]"
            ),
            "disclaimer": (
                "All risk scores are heuristic estimates — not predictions of future failures. "
                "Verified incidents increase evidence weight but are NOT proof of future bugs. "
                "Only incidents from Verified Memory (independently verified by automated tests) "
                "are counted as evidence."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Demo support endpoints (Phase 8)
# ---------------------------------------------------------------------------

@app.get("/demo/status")
def demo_status() -> dict:
    """
    Return overall system status for the demo presentation panel.

    All capability flags reflect what is actually implemented and tested —
    not aspirational features.

    This endpoint never modifies state.
    """
    verified_count = 0
    try:
        verified_count = memory_count()
    except Exception:
        pass

    return {
        "system": "CodeGuard AI",
        "version": "1.0.0",
        "capabilities": {
            "code_health_scan":         {"status": "operational", "description": "Heuristic risk scoring (complexity + churn + test gap)"},
            "bug_investigation":        {"status": "operational", "description": "AI-assisted or heuristic fallback bug analysis"},
            "independent_verification": {"status": "operational", "description": "Before/fix/regression test gate — fixes only pass all three stages"},
            "verified_memory":          {"status": "operational", "description": "SQLite-backed persistent store — PASS-only incidents"},
            "memory_context":           {"status": "operational", "description": "Keyword-based similar incident retrieval with re-verify warnings"},
            "risk_feedback_loop":       {"status": "operational", "description": "Verified incidents add transparent, capped evidence to risk score"},
            "cold_zone_detection":      {"status": "operational", "description": "Flags high-risk files with no verified incidents yet"},
        },
        "verified_incidents_stored": verified_count,
        "investigated_files_this_session": sorted(list(get_investigated_files())),
        "safety_principles": [
            "Verified incidents come ONLY from the automated test verification gate.",
            "Non-PASS incidents are never stored.",
            "Memory is evidence — not automatic truth.",
            "Phase 1 risk_score is never silently changed by Phase 7.",
            "Fix verification always restores the original file after testing.",
        ],
        "disclaimer": (
            "All risk scores are heuristic estimates — not predictions of future failures."
        ),
    }


@app.post("/demo/reset-session")
def demo_reset_session() -> dict:
    """
    Reset the in-memory investigation session state.

    SAFETY: This resets ONLY the in-memory set of investigated files for the
    current server session. It does NOT:
      - delete any verified incidents from memory.db
      - create any fake incidents
      - bypass the verification safety gate
      - modify any source files

    Use this before a fresh demo run so cold-zone detection starts clean.
    """
    reset_investigated()
    return {
        "reset": True,
        "message": "Session investigation state cleared. Verified Memory is unchanged.",
        "warning": (
            "This reset affects only the in-memory session state. "
            "Verified Memory (SQLite) is permanently preserved and was not modified."
        ),
    }
