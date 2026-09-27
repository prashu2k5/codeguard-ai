"""
cold_zones.py — Deterministic Cold Zone detection for Phase 7.

DEFINITION
----------
A file is a Cold Zone when ALL of the following are true:

  1. risk_score >= COLD_ZONE_THRESHOLD  (default: 35)
  2. verified_incident_count == 0  (no verified knowledge in SQLite memory)
  3. investigated == False  (not yet investigated in the current session)

IMPORTANT WORDING
-----------------
A Cold Zone is a prioritisation signal — NOT evidence of a bug.

Use:
  "Potentially under-investigated risk area."
  "High estimated risk with limited verified knowledge."

Never say:
  "This file contains a bug."

Cold-zone detection is a READ-ONLY operation.
It never modifies risk scores, source files, or memory records.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.memory import count_by_file, DB_PATH

# ---------------------------------------------------------------------------
# Configurable threshold — edit here to tune sensitivity
# ---------------------------------------------------------------------------
COLD_ZONE_THRESHOLD: float = 35.0


# ---------------------------------------------------------------------------
# Investigation state — session-scoped in-memory set
# ---------------------------------------------------------------------------
# Stores file paths (strings) that have been successfully investigated in the
# current server process.  Resets on server restart (intentionally — session
# state only, not persistence).

_investigated: set[str] = set()


def mark_investigated(file_path: str) -> None:
    """Record that a file has been investigated this session."""
    _investigated.add(file_path.strip())


def is_investigated(file_path: str) -> bool:
    """Return True if this file has been investigated this session."""
    return file_path.strip() in _investigated


def reset_investigated() -> None:
    """Clear all investigation state (used in tests and on re-scan)."""
    _investigated.clear()


def get_investigated_files() -> set[str]:
    """Return a copy of the current investigated-files set."""
    return set(_investigated)


# ---------------------------------------------------------------------------
# Cold-zone dataclass
# ---------------------------------------------------------------------------

@dataclass
class ColdZone:
    file_path:              str
    risk_score:             float
    risk_level:             str
    investigated:           bool
    verified_incident_count: int
    reason:                 str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path":               self.file_path,
            "risk_score":              self.risk_score,
            "risk_level":              self.risk_level,
            "investigated":            self.investigated,
            "verified_incident_count": self.verified_incident_count,
            "reason":                  self.reason,
            "disclaimer":              (
                "Cold Zones are prioritisation signals, NOT proof of bugs. "
                "They identify areas with elevated estimated risk where the system "
                "has not yet recorded a verified incident or investigation."
            ),
        }


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def detect_cold_zones(
    scan_results: list[dict[str, Any]],
    threshold: float = COLD_ZONE_THRESHOLD,
    db_path: Path = DB_PATH,
) -> list[ColdZone]:
    """
    Scan a list of file-result dicts (from scan_repository) and return
    those that qualify as Cold Zones.

    Parameters
    ----------
    scan_results : list of dicts from scanner.scan_repository()["files"]
    threshold    : risk_score >= threshold to be considered elevated
    db_path      : path to the SQLite memory database

    Returns
    -------
    List of ColdZone objects sorted by risk_score descending.

    SAFETY: this function is read-only — it never modifies risk scores,
    source files, or memory records.
    """
    cold: list[ColdZone] = []

    for f in scan_results:
        file_path = f.get("file", "")
        risk_score = f.get("risk_score", 0.0)
        risk_level = f.get("risk_level", "Low")

        # Rule 1: risk above threshold?
        if risk_score < threshold:
            continue

        # Rule 2: no verified incident in memory?
        verified_count = _verified_count(file_path, db_path)
        if verified_count > 0:
            continue

        # Rule 3: not yet investigated this session?
        investigated = is_investigated(file_path)
        if investigated:
            continue

        reason = _build_reason(risk_score, risk_level, verified_count, investigated)
        cold.append(ColdZone(
            file_path=file_path,
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            investigated=investigated,
            verified_incident_count=verified_count,
            reason=reason,
        ))

    cold.sort(key=lambda z: z.risk_score, reverse=True)
    return cold


def classify_file(
    file_path: str,
    risk_score: float,
    risk_level: str,
    threshold: float = COLD_ZONE_THRESHOLD,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """
    Return the full cold-zone classification for a single file.

    Used by the frontend to refresh status after an investigation.
    """
    verified_count = _verified_count(file_path, db_path)
    investigated   = is_investigated(file_path)

    is_cold = (
        risk_score >= threshold
        and verified_count == 0
        and not investigated
    )

    return {
        "file_path":               file_path,
        "risk_score":              round(risk_score, 2),
        "risk_level":              risk_level,
        "investigated":            investigated,
        "verified_incident_count": verified_count,
        "is_cold_zone":            is_cold,
        "threshold":               threshold,
        "reason":                  _build_reason(risk_score, risk_level, verified_count, investigated),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verified_count(file_path: str, db_path: Path) -> int:
    """Return number of verified memory incidents associated with this file."""
    try:
        return count_by_file(file_path, db_path)
    except Exception:
        return 0


def _build_reason(
    risk_score: float,
    risk_level: str,
    verified_count: int,
    investigated: bool,
) -> str:
    parts: list[str] = []

    if risk_score >= COLD_ZONE_THRESHOLD:
        parts.append(
            f"Elevated estimated risk ({risk_score:.1f}/100, {risk_level})"
        )

    if verified_count == 0:
        parts.append("no verified incident recorded for this file")
    else:
        parts.append(f"{verified_count} verified incident(s) exist")

    if not investigated:
        parts.append("not yet investigated this session")
    else:
        parts.append("investigated this session")

    return " — ".join(parts) + "."
