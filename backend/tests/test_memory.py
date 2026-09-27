"""
test_memory.py — Tests for the Verified Memory system (Phase 5).

Tests cover:
  1. memory.py module — save, list, count, search, safety gate
  2. POST /memory/save  — accept PASS, reject non-PASS
  3. GET  /memory       — returns all incidents
  4. POST /memory/search — keyword search, match note, safety warning
  5. Persistence       — data survives module reload (separate db file)
  6. Similar incident matching — re-verify warning present
  7. Memory NEVER auto-verifies a new bug
"""

from __future__ import annotations

import os
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.memory import (
    save, list_all, count, search, get_by_id, init_db,
    VerifiedIncident, DB_PATH,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures — always use a temporary database so tests don't pollute production
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    """Yield a temporary database path and clean up after the test."""
    db = tmp_path / "test_memory.db"
    init_db(db)
    yield db


def _make_incident(**kwargs) -> VerifiedIncident:
    defaults = dict(
        repository="demo_repo",
        file_path="data_processor.py",
        function_name="normalize",
        problem="normalize() produces wrong results and ZeroDivisionError",
        root_cause="Off-by-one in denominator: (max_v - min_v - 1)",
        fix="Change to (max_v - min_v)",
        regression_test="demo_repo/regression_normalize.py",
        verification_result="PASS",
    )
    defaults.update(kwargs)
    return VerifiedIncident(**defaults)


# ---------------------------------------------------------------------------
# memory.py unit tests
# ---------------------------------------------------------------------------

class TestMemorySave:

    def test_save_verified_incident(self, tmp_db):
        inc = _make_incident()
        new_id = save(inc, tmp_db)
        assert isinstance(new_id, int)
        assert new_id >= 1

    def test_save_returns_incrementing_ids(self, tmp_db):
        id1 = save(_make_incident(problem="bug 1"), tmp_db)
        id2 = save(_make_incident(problem="bug 2"), tmp_db)
        assert id2 > id1

    def test_save_rejects_non_pass(self, tmp_db):
        """Safety gate: unverified incidents must be rejected."""
        inc = _make_incident(verification_result="FAIL")
        with pytest.raises(ValueError, match="PASS"):
            save(inc, tmp_db)

    def test_save_rejects_error_status(self, tmp_db):
        inc = _make_incident(verification_result="ERROR")
        with pytest.raises(ValueError):
            save(inc, tmp_db)

    def test_save_rejects_empty_status(self, tmp_db):
        inc = _make_incident(verification_result="")
        with pytest.raises(ValueError):
            save(inc, tmp_db)


class TestMemoryRead:

    def test_list_empty(self, tmp_db):
        assert list_all(tmp_db) == []

    def test_list_returns_saved(self, tmp_db):
        save(_make_incident(), tmp_db)
        items = list_all(tmp_db)
        assert len(items) == 1
        assert items[0].file_path == "data_processor.py"

    def test_list_newest_first(self, tmp_db):
        save(_make_incident(problem="older"), tmp_db)
        save(_make_incident(problem="newer"), tmp_db)
        items = list_all(tmp_db)
        assert items[0].problem == "newer"
        assert items[1].problem == "older"

    def test_count_zero(self, tmp_db):
        assert count(tmp_db) == 0

    def test_count_increments(self, tmp_db):
        save(_make_incident(), tmp_db)
        assert count(tmp_db) == 1
        save(_make_incident(), tmp_db)
        assert count(tmp_db) == 2

    def test_get_by_id(self, tmp_db):
        new_id = save(_make_incident(), tmp_db)
        inc = get_by_id(new_id, tmp_db)
        assert inc is not None
        assert inc.id == new_id
        assert inc.function_name == "normalize"

    def test_get_by_id_missing(self, tmp_db):
        assert get_by_id(9999, tmp_db) is None

    def test_to_dict_has_memory_warning(self, tmp_db):
        new_id = save(_make_incident(), tmp_db)
        inc = get_by_id(new_id, tmp_db)
        d = inc.to_dict()
        assert "memory_warning" in d
        assert "NOT automatic truth" in d["memory_warning"] or "evidence" in d["memory_warning"]


class TestMemorySearch:

    def test_search_empty_db(self, tmp_db):
        results = search("normalize", db_path=tmp_db)
        assert results == []

    def test_search_finds_by_keyword(self, tmp_db):
        save(_make_incident(), tmp_db)
        results = search("normalize", db_path=tmp_db)
        assert len(results) == 1

    def test_search_by_file_path(self, tmp_db):
        save(_make_incident(), tmp_db)
        results = search("", file_path="data_processor", db_path=tmp_db)
        assert len(results) == 1

    def test_search_no_match(self, tmp_db):
        save(_make_incident(), tmp_db)
        results = search("completely unrelated xyz", db_path=tmp_db)
        assert len(results) == 0

    def test_search_relevance_score_present(self, tmp_db):
        save(_make_incident(), tmp_db)
        results = search("normalize", db_path=tmp_db)
        assert "relevance_score" in results[0]
        assert isinstance(results[0]["relevance_score"], int)

    def test_search_match_note_not_ml(self, tmp_db):
        save(_make_incident(), tmp_db)
        results = search("normalize", db_path=tmp_db)
        note = results[0].get("match_note", "")
        assert "NOT ML" in note or "keyword" in note.lower()

    def test_search_memory_warning_present(self, tmp_db):
        """Search results must always carry the re-verify warning."""
        save(_make_incident(), tmp_db)
        results = search("normalize", db_path=tmp_db)
        warning = results[0].get("memory_warning", "")
        assert len(warning) > 0

    def test_search_no_auto_verified_claim(self, tmp_db):
        """Memory must NEVER claim the stored fix is verified for a new problem."""
        save(_make_incident(), tmp_db)
        results = search("normalize", db_path=tmp_db)
        for r in results:
            # Must not say "this is verified" without a warning
            assert "memory_warning" in r
            # The memory_warning must include a re-check instruction
            assert any(word in r["memory_warning"].lower()
                       for word in ["re-check", "re-verify", "not automatically", "not automatic"])

    def test_search_sorted_by_relevance(self, tmp_db):
        save(_make_incident(problem="normalize denominator bug zero division"), tmp_db)
        save(_make_incident(problem="unrelated issue with logging"), tmp_db)
        results = search("normalize zero", db_path=tmp_db)
        if len(results) > 1:
            assert results[0]["relevance_score"] >= results[1]["relevance_score"]


class TestMemoryPersistence:

    def test_persists_across_reconnect(self, tmp_db):
        """Simulate application restart by creating a new connection."""
        save(_make_incident(), tmp_db)
        # Reconnect — read from the same file
        items = list_all(tmp_db)
        assert len(items) == 1
        assert items[0].problem == "normalize() produces wrong results and ZeroDivisionError"

    def test_multiple_saves_persist(self, tmp_db):
        for i in range(3):
            save(_make_incident(problem=f"bug {i}"), tmp_db)
        items = list_all(tmp_db)
        assert len(items) == 3


# ---------------------------------------------------------------------------
# Endpoint tests — use the real production DB_PATH but clean up after
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_production_db():
    """
    Remove any incidents added during endpoint tests from the production DB.
    We track IDs before and after so other tests' data is unaffected.
    """
    before = count(DB_PATH)
    yield
    # Remove only rows that were added during this test
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"DELETE FROM verified_incidents WHERE id > {before}")


class TestMemoryEndpoints:

    def test_save_endpoint_accepts_pass(self):
        res = client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "Test problem",
            "root_cause": "Test root cause",
            "fix": "Change denominator",
            "verification_result": "PASS",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["saved"] is True
        assert "id" in data
        assert data["message"] == "Verified incident saved to memory."

    def test_save_endpoint_rejects_fail(self):
        res = client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "problem": "unverified",
            "root_cause": "unknown",
            "fix": "unknown",
            "verification_result": "FAIL",
        })
        assert res.status_code == 400

    def test_save_endpoint_rejects_error_status(self):
        res = client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "problem": "p", "root_cause": "r", "fix": "f",
            "verification_result": "ERROR",
        })
        assert res.status_code == 400

    def test_get_memory_returns_list(self):
        # Save one first
        client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "problem": "p", "root_cause": "r", "fix": "f",
            "verification_result": "PASS",
        })
        res = client.get("/memory")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "incidents" in data
        assert isinstance(data["incidents"], list)
        assert "warning" in data

    def test_get_memory_has_safety_warning(self):
        res = client.get("/memory")
        assert res.status_code == 200
        assert "NOT automatic truth" in res.json()["warning"] or \
               "evidence" in res.json()["warning"].lower()

    def test_search_endpoint(self):
        # Save a known incident
        client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "normalize ZeroDivisionError off-by-one",
            "root_cause": "denominator minus 1",
            "fix": "remove minus 1",
            "verification_result": "PASS",
        })
        res = client.post("/memory/search", json={"query": "normalize"})
        assert res.status_code == 200
        data = res.json()
        assert data["total_matches"] >= 1
        assert "search_note" in data

    def test_search_endpoint_not_ml(self):
        res = client.post("/memory/search", json={"query": "normalize"})
        assert res.status_code == 200
        note = res.json().get("search_note", "")
        assert "keyword" in note.lower() or "NOT semantic" in note

    def test_search_endpoint_results_have_warning(self):
        client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "problem": "normalize bug",
            "root_cause": "denominator",
            "fix": "fix denominator",
            "verification_result": "PASS",
        })
        res = client.post("/memory/search", json={"query": "normalize"})
        assert res.status_code == 200
        results = res.json().get("results", [])
        if results:
            assert "memory_warning" in results[0]

    def test_search_endpoint_empty_query_rejected(self):
        res = client.post("/memory/search", json={"query": "", "file_path": ""})
        assert res.status_code == 400

    def test_memory_does_not_auto_verify_new_bug(self):
        """
        Storing a past verified fix must NEVER mean the fix is verified
        for a new invocation. The warning must be explicit.
        """
        client.post("/memory/save", json={
            "repository": "demo_repo",
            "file_path": "data_processor.py",
            "problem": "normalize zero division",
            "root_cause": "denominator",
            "fix": "fix it",
            "verification_result": "PASS",
        })
        res = client.post("/memory/search", json={"query": "normalize zero division"})
        data = res.json()
        for result in data.get("results", []):
            w = result.get("memory_warning", "")
            # Must contain a re-check instruction — never say "this IS verified"
            assert any(kw in w.lower() for kw in
                       ["re-check", "re-verify", "not automatically", "not automatic"]), \
                f"Safety warning missing or wrong: {w!r}"

    def test_phase1_regression(self):
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        assert res.json()["summary"]["files_scanned"] > 0

    def test_phase3_regression(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo", "file_path": "data_processor.py"
        })
        assert res.status_code == 200

    def test_phase4_regression(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo", "file_path": "data_processor.py"
        })
        assert res.status_code == 200
        assert res.json()["verified"] is True
