"""
memory_context.py — Connects the investigation workflow to Verified Memory.

This module is the Phase 6 bridge:

    investigation result  →  search_for_similar()  →  similar_incidents list

It uses the same basic keyword matching from memory.py — no ML, no embeddings.

SAFETY CONTRACT
---------------
Results are labelled as "Previously Verified", NOT as proof that the
current bug is identical to any historical incident.

Every result carries:
  reuse_warning  — human-readable re-check instruction
  provenance     — makes the source incident ID visible

The calling code must NEVER use these results to:
  * automatically apply the previous fix
  * skip Phase 4 independent verification
  * claim the current bug is "the same" as a previous one
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from backend.memory import search, VerifiedIncident, DB_PATH


# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------

def _extract_terms(
    file_path: str = "",
    function_name: str = "",
    problem: str = "",
    root_cause: str = "",
    bug_description: str = "",
) -> str:
    """
    Combine all available signals into a single search query string.

    Returns a space-joined string of unique tokens (3+ chars, alphabetic).
    The function name and file basename get extra weight via repetition.
    """
    # Basename without extension
    base = Path(file_path).stem if file_path else ""

    # Weight important fields by repeating their tokens
    raw = " ".join([
        base, base,               # file name — doubled
        function_name, function_name,  # function — doubled
        problem,
        root_cause,
        bug_description,
    ])

    tokens = re.findall(r"[a-z]{3,}", raw.lower())
    # Deduplicate while preserving order and weighting
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return " ".join(result)


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

_REUSE_WARNING = (
    "Re-check the current code before reusing this fix. "
    "Fresh independent verification is required."
)

_NOT_SAME_WARNING = (
    "⚠ This is previous verified knowledge, not proof that the current bug "
    "is identical. A stored fix is NOT automatically verified for a new problem."
)


def _enrich(raw: dict, rank: int) -> dict:
    """
    Convert a raw memory.search() result dict into a similar_incidents entry.

    Adds provenance, reuse_warning, and clear labelling.
    """
    return {
        "id":                  raw.get("id"),
        "file_path":           raw.get("file_path", ""),
        "function_name":       raw.get("function_name", ""),
        "problem":             raw.get("problem", ""),
        "root_cause":          raw.get("root_cause", ""),
        "fix":                 raw.get("fix", ""),
        "regression_test":     raw.get("regression_test", ""),
        "verification_result": raw.get("verification_result", "PASS"),
        "created_at":          raw.get("created_at", ""),
        "match_score":         raw.get("relevance_score", 0),
        "match_rank":          rank + 1,
        # Safety labels — these must appear in every result
        "reuse_warning":       _REUSE_WARNING,
        "not_same_warning":    _NOT_SAME_WARNING,
        "provenance_label":    f"Previously Verified Incident #{raw.get('id')}",
        "current_label":       "Current Investigation — Not Yet Verified",
        "match_note":          raw.get("match_note", "Basic keyword match — NOT ML similarity."),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_for_similar(
    file_path: str = "",
    function_name: str = "",
    problem: str = "",
    root_cause: str = "",
    bug_description: str = "",
    db_path: Path = DB_PATH,
    max_results: int = 3,
) -> list[dict]:
    """
    Search Verified Memory for incidents similar to the current investigation.

    Parameters
    ----------
    file_path, function_name, problem, root_cause, bug_description
        — signals extracted from the current investigation result
    db_path      — path to the SQLite database
    max_results  — cap on returned results

    Returns
    -------
    List of enriched dicts (may be empty).
    Each item is labelled with reuse_warning, not_same_warning, and provenance.
    """
    query = _extract_terms(
        file_path=file_path,
        function_name=function_name,
        problem=problem,
        root_cause=root_cause,
        bug_description=bug_description,
    )

    # Also pass the file_path as a direct filter to boost file-name matches
    raw_results = search(
        query=query,
        file_path=Path(file_path).name if file_path else "",
        db_path=db_path,
    )

    top = raw_results[:max_results]
    return [_enrich(r, i) for i, r in enumerate(top)]


def memory_context(
    file_path: str,
    function_name: str,
    problem: str,
    db_path: Path = DB_PATH,
) -> dict:
    """
    Build a full memory context response for POST /memory/context.

    Returns a structured dict with matches plus all safety labels.
    The response deliberately has NO field that could be interpreted as
    "the current issue is already verified".
    """
    similar = search_for_similar(
        file_path=file_path,
        function_name=function_name,
        problem=problem,
        db_path=db_path,
    )

    return {
        "file_path":     file_path,
        "function_name": function_name,
        "problem":       problem,
        "matches":       similar,
        "total_matches": len(similar),
        "search_note":   "Basic keyword match — NOT ML or semantic similarity.",
        "safety_notice": (
            "Memory context is EVIDENCE, not automatic truth. "
            "The current code must be independently re-verified before any fix "
            "is considered confirmed. A previous verified incident does NOT "
            "transfer its verification status to a new problem."
        ),
        # Explicit absence marker — caller should check this
        "current_verified": False,
        "current_verified_reason": (
            "Only POST /verify-fix can set the current issue as verified."
        ),
    }
