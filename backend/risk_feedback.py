"""
risk_feedback.py — Phase 7: Verified Incident → Risk Feedback Loop.

DESIGN PRINCIPLES
-----------------
1. Verified incidents come ONLY from Verified Memory (memory.db).
   Only incidents that passed all four gates are eligible:
     • before-code test FAILED
     • proposed fix test PASSED
     • regression suite PASSED
     • verification_result == "PASS"

2. The existing Phase 1 heuristic risk_score is NEVER silently changed.
   Phase 7 adds NEW fields alongside the original score.

3. Two risk concepts are kept explicitly separate:
     • predicted_risk   — heuristic estimate from code signals (Phase 1)
     • verified_evidence — count + summary of independently verified incidents
     • observed_risk    — updated estimate after incorporating incident evidence

4. The formula is transparent and documented here:

   INCIDENT COMPONENT FORMULA
   --------------------------
   incident_score = min(30, verified_incident_count × 10)
     • 1 incident → +10 pts
     • 2 incidents → +20 pts
     • 3+ incidents → capped at +30 pts

   observed_risk = min(100, predicted_risk + incident_score)

   The incident component is ADDITIVE and CAPPED so that:
     - A single incident does NOT automatically make a file "dangerous"
     - The original heuristic score is fully visible alongside the update
     - The formula is deterministic and auditable

5. Cold-zone labelling (predicted risk ≥ 35, zero verified incidents)
   is preserved from the existing cold_zones.py module.

DISCLAIMER
----------
All risk scores — both predicted and observed — are heuristic estimates.
Verified incidents increase evidence weight but are NOT proof that future
bugs will occur in the same file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.memory import count_by_file, list_all, DB_PATH
from backend.cold_zones import COLD_ZONE_THRESHOLD, is_investigated


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Per-incident additive score contribution (pts per incident)
INCIDENT_SCORE_PER_INCIDENT: float = 10.0

# Maximum incident contribution (caps at 3+ incidents → 30 pts)
INCIDENT_SCORE_CAP: float = 30.0


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class FileFeedback:
    """Phase 7 risk feedback for a single file."""
    file:                     str
    # ── Phase 1 signals (unchanged) ──
    complexity_score:         float
    git_churn_commits:        int
    git_churn_score:          float
    test_coverage_pct:        float
    # ── Phase 1 risk (unchanged label/value) ──
    risk_score:               float   # same as Phase 1; NOT modified
    risk_level:               str
    # ── Phase 7: verified incident evidence ──
    verified_incident_count:  int
    verified_incident_evidence: list[dict]    # summaries of matching incidents
    is_cold_zone:             bool
    # ── Phase 7: observed/updated risk ──
    incident_score:           float   # additive contribution from incidents
    observed_risk:            float   # predicted_risk + incident_score
    observed_risk_level:      str
    # ── Human-readable explanation ──
    risk_explanation:         str

    def to_dict(self) -> dict[str, Any]:
        return {
            # Phase 1 fields (preserved, unchanged)
            "file":                       self.file,
            "complexity_score":           self.complexity_score,
            "git_churn_commits":          self.git_churn_commits,
            "git_churn_score":            self.git_churn_score,
            "test_coverage_pct":          self.test_coverage_pct,
            "risk_score":                 self.risk_score,
            "risk_level":                 self.risk_level,
            # Phase 7 fields (new)
            "verified_incident_count":    self.verified_incident_count,
            "verified_incident_evidence": self.verified_incident_evidence,
            "is_cold_zone":               self.is_cold_zone,
            "incident_score":             self.incident_score,
            "observed_risk":              self.observed_risk,
            "observed_risk_level":        self.observed_risk_level,
            "risk_explanation":           self.risk_explanation,
            # Formula documentation
            "risk_formula": (
                "predicted_risk = 0.35×complexity + 0.35×churn + 0.30×test_gap  [Phase 1, unchanged]\n"
                "incident_score = min(30, verified_incident_count × 10)          [Phase 7]\n"
                "observed_risk  = min(100, predicted_risk + incident_score)       [Phase 7]"
            ),
            "disclaimer": (
                "All risk scores are heuristic estimates — not predictions of future failures. "
                "Verified incidents increase evidence weight but do not guarantee future bugs."
            ),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _incident_score(count: int) -> float:
    """Deterministic, capped incident contribution."""
    return round(min(INCIDENT_SCORE_CAP, count * INCIDENT_SCORE_PER_INCIDENT), 2)


def _observed_risk(predicted: float, inc_score: float) -> float:
    return round(min(100.0, predicted + inc_score), 2)


def _risk_level(score: float) -> str:
    if score < 33:
        return "Low"
    if score < 66:
        return "Medium"
    return "High"


def _summarise_incidents(file_path: str, db_path: Path) -> list[dict]:
    """Return lightweight summaries of verified incidents for this file."""
    try:
        all_incidents = list_all(db_path)
    except Exception:
        return []

    base = Path(file_path).name
    matched = []
    for inc in all_incidents:
        if (
            inc.file_path == file_path
            or inc.file_path == base
            or inc.file_path.endswith(base)
        ):
            matched.append({
                "id":            inc.id,
                "problem":       inc.problem,
                "root_cause":    inc.root_cause,
                "function_name": inc.function_name,
                "created_at":    inc.created_at,
                "verified_at":   inc.created_at,
                "source":        "Verified Memory — independently verified by automated tests",
            })
    return matched


def _build_explanation(
    file: str,
    complexity_score: float,
    git_churn_commits: int,
    test_coverage_pct: float,
    risk_score: float,
    risk_level: str,
    verified_incident_count: int,
    incident_score: float,
    observed_risk: float,
    is_cold_zone: bool,
) -> str:
    parts: list[str] = []

    # Predicted risk drivers
    if complexity_score >= 15:
        parts.append(f"high cyclomatic complexity ({complexity_score:.1f}/100)")
    elif complexity_score >= 7:
        parts.append(f"moderate complexity ({complexity_score:.1f}/100)")

    if git_churn_commits >= 5:
        parts.append(f"high git churn ({git_churn_commits} commits)")
    elif git_churn_commits >= 3:
        parts.append(f"moderate churn ({git_churn_commits} commits)")

    if test_coverage_pct < 30:
        parts.append(f"very low test coverage ({test_coverage_pct:.0f}%)")
    elif test_coverage_pct < 70:
        parts.append(f"partial test coverage ({test_coverage_pct:.0f}%)")

    if parts:
        driver_text = "Predicted risk is elevated because of " + " and ".join(parts) + "."
    else:
        driver_text = f"Predicted risk is {risk_level.lower()} ({risk_score:.1f}/100) based on code signals."

    # Verified incident evidence
    if verified_incident_count == 0:
        incident_text = "No verified incident evidence yet."
    elif verified_incident_count == 1:
        incident_text = (
            "1 independently verified incident has been recorded for this file "
            f"(+{incident_score:.0f} pts → observed risk: {observed_risk:.1f}/100)."
        )
    else:
        incident_text = (
            f"{verified_incident_count} independently verified incidents have been recorded "
            f"for this file (+{incident_score:.0f} pts → observed risk: {observed_risk:.1f}/100)."
        )

    # Cold zone annotation
    if is_cold_zone:
        cold_text = (
            "Cold Zone — predicted risk without verified incident evidence. "
            "This file has elevated estimated risk but has not yet been investigated or verified."
        )
        return f"{driver_text} {incident_text} {cold_text}"

    return f"{driver_text} {incident_text}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enrich_with_feedback(
    scan_files: list[dict[str, Any]],
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    """
    Take the raw file-list from scan_repository() and return enriched dicts
    with Phase 7 risk feedback fields added.

    SAFETY: This function is read-only. It never modifies files or memory records.
    Only incidents with verification_result == 'PASS' stored in Verified Memory
    are counted as verified incident evidence.
    """
    enriched = []
    for f in scan_files:
        file_path = f.get("file", "")
        predicted = f.get("risk_score", 0.0)
        risk_level = f.get("risk_level", "Low")

        count = count_by_file(file_path, db_path) if file_path else 0
        inc_score = _incident_score(count)
        obs_risk = _observed_risk(predicted, inc_score)
        obs_level = _risk_level(obs_risk)

        investigated = is_investigated(file_path)
        is_cold = (
            predicted >= COLD_ZONE_THRESHOLD
            and count == 0
            and not investigated
        )

        evidence = _summarise_incidents(file_path, db_path)

        explanation = _build_explanation(
            file=file_path,
            complexity_score=f.get("complexity_score", 0.0),
            git_churn_commits=f.get("git_churn_commits", 0),
            test_coverage_pct=f.get("test_coverage_pct", 0.0),
            risk_score=predicted,
            risk_level=risk_level,
            verified_incident_count=count,
            incident_score=inc_score,
            observed_risk=obs_risk,
            is_cold_zone=is_cold,
        )

        feedback = FileFeedback(
            file=file_path,
            complexity_score=f.get("complexity_score", 0.0),
            git_churn_commits=f.get("git_churn_commits", 0),
            git_churn_score=f.get("git_churn_score", 0.0),
            test_coverage_pct=f.get("test_coverage_pct", 0.0),
            risk_score=predicted,
            risk_level=risk_level,
            verified_incident_count=count,
            verified_incident_evidence=evidence,
            is_cold_zone=is_cold,
            incident_score=inc_score,
            observed_risk=obs_risk,
            observed_risk_level=obs_level,
            risk_explanation=explanation,
        )
        enriched.append(feedback.to_dict())
    return enriched
