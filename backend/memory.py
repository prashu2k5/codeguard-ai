"""
memory.py — Persistent storage for INDEPENDENTLY VERIFIED debugging incidents.

SAFETY CONTRACT
---------------
Only incidents with verified=True from the /verify-fix endpoint may be saved.
The save() function enforces this at the database layer — it raises ValueError
if you attempt to store an unverified incident.

Memory is EVIDENCE, not automatic truth.
When a previous incident is returned as a search match, the caller MUST display
a warning that the fix requires fresh independent verification before reuse.

Database
--------
SQLite file at backend/memory.db (auto-created on first use).
Single table: verified_incidents
"""

from __future__ import annotations

import re
import sqlite3
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database location — sits next to this module inside backend/
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).parent / "memory.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS verified_incidents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    repository       TEXT    NOT NULL,
    file_path        TEXT    NOT NULL,
    function_name    TEXT    NOT NULL DEFAULT '',
    problem          TEXT    NOT NULL,
    root_cause       TEXT    NOT NULL,
    fix              TEXT    NOT NULL,
    regression_test  TEXT    NOT NULL DEFAULT '',
    verification_result TEXT NOT NULL DEFAULT 'PASS',
    before_output    TEXT    NOT NULL DEFAULT '',
    after_output     TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_file_path ON verified_incidents(file_path);
"""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class VerifiedIncident:
    repository:          str
    file_path:           str
    function_name:       str
    problem:             str
    root_cause:          str
    fix:                 str
    regression_test:     str = ""
    verification_result: str = "PASS"
    before_output:       str = ""
    after_output:        str = ""
    created_at:          str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id:                  Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "repository":          self.repository,
            "file_path":           self.file_path,
            "function_name":       self.function_name,
            "problem":             self.problem,
            "root_cause":          self.root_cause,
            "fix":                 self.fix,
            "regression_test":     self.regression_test,
            "verification_result": self.verification_result,
            "created_at":          self.created_at,
            "memory_warning": (
                "Memory is evidence, NOT automatic truth. "
                "Re-verify the fix against the current codebase before reuse."
            ),
        }


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the database and table if they don't already exist."""
    with _connect(db_path) as conn:
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_INDEX)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save(incident: VerifiedIncident, db_path: Path = DB_PATH) -> int:
    """
    Persist a verified incident to the database.

    Parameters
    ----------
    incident : VerifiedIncident — must have verification_result == "PASS"

    Returns
    -------
    int — the new row id

    Raises
    ------
    ValueError — if verification_result != "PASS" (safety gate)
    """
    if incident.verification_result != "PASS":
        raise ValueError(
            f"Cannot store unverified incident. "
            f"verification_result={incident.verification_result!r}. "
            "Only PASS incidents may be saved to Verified Memory."
        )

    init_db(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO verified_incidents
                (repository, file_path, function_name, problem, root_cause,
                 fix, regression_test, verification_result,
                 before_output, after_output, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.repository,
                incident.file_path,
                incident.function_name,
                incident.problem,
                incident.root_cause,
                incident.fix,
                incident.regression_test,
                incident.verification_result,
                incident.before_output,
                incident.after_output,
                incident.created_at,
            ),
        )
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_all(db_path: Path = DB_PATH) -> list[VerifiedIncident]:
    """Return all stored incidents, newest first."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM verified_incidents ORDER BY id DESC"
        ).fetchall()
    return [_row_to_incident(r) for r in rows]


def get_by_id(incident_id: int, db_path: Path = DB_PATH) -> Optional[VerifiedIncident]:
    """Return a single incident by id, or None if not found."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM verified_incidents WHERE id = ?", (incident_id,)
        ).fetchone()
    return _row_to_incident(row) if row else None


def count(db_path: Path = DB_PATH) -> int:
    """Return total number of stored incidents."""
    init_db(db_path)
    with _connect(db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM verified_incidents"
        ).fetchone()[0]


def count_by_file(file_path: str, db_path: Path = DB_PATH) -> int:
    """Return number of verified incidents associated with a specific file."""
    init_db(db_path)
    # Match on the basename as well to handle path separator differences
    base = Path(file_path).name
    with _connect(db_path) as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM verified_incidents
            WHERE file_path = ?
               OR file_path = ?
               OR file_path LIKE ?
            """,
            (file_path, base, f"%{base}"),
        ).fetchone()[0]


# ---------------------------------------------------------------------------
# Search — keyword-based, no embeddings
# ---------------------------------------------------------------------------

def search(
    query: str,
    file_path: str = "",
    db_path: Path = DB_PATH,
) -> list[dict]:
    """
    Search verified incidents using basic keyword matching.

    The relevance score is a SIMPLE keyword hit count — not ML similarity.
    It is clearly labelled as such in every returned result.

    Parameters
    ----------
    query     : free-text search terms
    file_path : optional filter by file name (substring match)

    Returns
    -------
    List of dicts with added 'relevance_score' and 'match_note' fields,
    sorted descending by relevance_score.  Only results with score > 0
    are returned (unless file_path filter yields a match on its own).
    """
    init_db(db_path)
    incidents = list_all(db_path)
    if not incidents:
        return []

    # Tokenise the query
    query_words = set(_tokenise(query))
    fp_lower = file_path.lower().strip()

    scored: list[dict] = []
    for inc in incidents:
        score = _score_incident(inc, query_words, fp_lower)
        if score > 0 or (fp_lower and fp_lower in inc.file_path.lower()):
            d = inc.to_dict()
            d["relevance_score"] = score
            d["match_note"] = (
                "Basic keyword match score — NOT ML similarity. "
                "Re-verify any suggested fix before applying it."
            )
            d["memory_warning"] = (
                "⚠ Similar verified incident found. "
                "Re-check the current code before reusing the fix. "
                "A stored fix is NOT automatically verified for a new problem."
            )
            scored.append(d)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored


def _tokenise(text: str) -> list[str]:
    """Split text into lowercase alphabetic tokens, min length 3."""
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w]


def _score_incident(
    inc: VerifiedIncident,
    query_words: set[str],
    fp_lower: str,
) -> int:
    """Return a simple keyword hit count across searchable fields."""
    if not query_words and not fp_lower:
        return 0

    # Build a corpus from the searchable fields
    corpus = " ".join([
        inc.file_path,
        inc.function_name,
        inc.problem,
        inc.root_cause,
        inc.fix,
        inc.regression_test,
    ]).lower()

    corpus_words = set(_tokenise(corpus))

    score = 0
    for word in query_words:
        if word in corpus_words:
            score += 1
        # Partial match bonus for longer terms
        elif any(word in cw for cw in corpus_words):
            score += 1

    # Exact file name match is a strong signal
    if fp_lower and fp_lower in inc.file_path.lower():
        score += 3

    return score


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_incident(row: sqlite3.Row) -> VerifiedIncident:
    return VerifiedIncident(
        id=row["id"],
        repository=row["repository"],
        file_path=row["file_path"],
        function_name=row["function_name"],
        problem=row["problem"],
        root_cause=row["root_cause"],
        fix=row["fix"],
        regression_test=row["regression_test"],
        verification_result=row["verification_result"],
        before_output=row["before_output"],
        after_output=row["after_output"],
        created_at=row["created_at"],
    )
