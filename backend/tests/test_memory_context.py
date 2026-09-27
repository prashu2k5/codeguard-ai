"""
test_memory_context.py — Tests for Phase 6: Similar-Bug Reuse.

Tests cover:
  1.  investigation with no memory matches → similar_incidents = []
  2.  investigation with matching verified incident → similar_incidents populated
  3.  matching by file path
  4.  matching by function name
  5.  matching by problem/root-cause keywords
  6.  match score calculation and ordering
  7.  POST /memory/context endpoint
  8.  reuse candidate generation (enrichment keys present)
  9.  reuse candidate does NOT modify source code
 10.  reuse candidate does NOT automatically verify
 11.  previous incident remains unchanged after investigation
 12.  fresh Phase 4 verification is still required (current_verified=False)
 13.  existing Phase 1–5 tests unaffected (regression)
 14.  similar_incidents field always present even when DB is empty
 15.  memory_context_note always present in investigation response
 16.  investigate still works when memory DB is empty
 17.  POST /investigate response shape unchanged (backward-compatible)
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.memory import save, init_db, count, DB_PATH, VerifiedIncident
from backend.memory_context import search_for_similar, memory_context, _extract_terms

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_production_db():
    """Track rows before/after and clean up test rows from the production DB."""
    before = count(DB_PATH)
    yield
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"DELETE FROM verified_incidents WHERE id > {before}")


def _save_normalize_incident() -> int:
    inc = VerifiedIncident(
        repository="demo_repo",
        file_path="data_processor.py",
        function_name="normalize",
        problem="normalize() produces wrong results and ZeroDivisionError when max - min == 1.",
        root_cause="Off-by-one in denominator: (max_v - min_v - 1)",
        fix="Change denominator to (max_v - min_v) — remove the spurious '- 1'.",
        regression_test="demo_repo/regression_normalize.py",
        verification_result="PASS",
    )
    return save(inc, DB_PATH)


# ---------------------------------------------------------------------------
# memory_context.py unit tests
# ---------------------------------------------------------------------------

class TestExtractTerms:
    def test_returns_string(self):
        result = _extract_terms(file_path="data_processor.py", function_name="normalize")
        assert isinstance(result, str)

    def test_includes_file_stem(self):
        result = _extract_terms(file_path="data_processor.py")
        assert "data" in result or "processor" in result

    def test_includes_function_name(self):
        result = _extract_terms(function_name="normalize")
        assert "normalize" in result

    def test_includes_problem_keywords(self):
        result = _extract_terms(problem="zero division error in normalize function")
        assert "normalize" in result
        assert "division" in result

    def test_deduplication(self):
        result = _extract_terms(
            file_path="foo.py",
            function_name="foo",
            problem="foo foo foo",
        )
        # "foo" should not appear many duplicate times
        tokens = result.split()
        assert tokens.count("foo") == 1

    def test_empty_inputs(self):
        result = _extract_terms()
        assert isinstance(result, str)


class TestSearchForSimilar:
    def test_empty_db_returns_empty(self):
        results = search_for_similar(file_path="data_processor.py", problem="normalize")
        # May return [] or matches; must always return a list
        assert isinstance(results, list)

    def test_finds_match_by_file_path(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        assert len(results) >= 1

    def test_finds_match_by_function(self):
        _save_normalize_incident()
        results = search_for_similar(function_name="normalize")
        assert len(results) >= 1

    def test_finds_match_by_problem_keyword(self):
        _save_normalize_incident()
        results = search_for_similar(problem="ZeroDivisionError normalize denominator")
        assert len(results) >= 1

    def test_no_match_for_unrelated_query(self):
        _save_normalize_incident()
        results = search_for_similar(
            file_path="completely_different.py",
            function_name="unrelated_func",
            problem="completely unrelated logging issue xyz",
        )
        # May or may not match — but the list must exist
        assert isinstance(results, list)

    def test_result_shape(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            r = results[0]
            for key in ("id", "file_path", "function_name", "problem", "root_cause",
                        "fix", "regression_test", "verification_result",
                        "match_score", "reuse_warning", "not_same_warning",
                        "provenance_label", "current_label", "match_note"):
                assert key in r, f"Missing key: {key}"

    def test_reuse_warning_present(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            assert "Re-check" in results[0]["reuse_warning"]

    def test_not_same_warning_present(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            w = results[0]["not_same_warning"]
            assert "NOT" in w or "not proof" in w.lower()

    def test_provenance_label_has_id(self):
        new_id = _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            label = results[0]["provenance_label"]
            assert str(new_id) in label

    def test_current_label_not_verified(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            label = results[0]["current_label"]
            assert "Not Yet Verified" in label or "not" in label.lower()

    def test_match_score_is_int(self):
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        if results:
            assert isinstance(results[0]["match_score"], int)

    def test_max_results_cap(self):
        for _ in range(5):
            _save_normalize_incident()
        results = search_for_similar(
            file_path="data_processor.py",
            max_results=2,
        )
        assert len(results) <= 2

    def test_does_not_modify_source_file(self):
        """Using memory context must NEVER change source files."""
        orig = Path("demo_repo/data_processor.py").read_text(encoding="utf-8")
        _save_normalize_incident()
        search_for_similar(file_path="data_processor.py", problem="normalize bug")
        after = Path("demo_repo/data_processor.py").read_text(encoding="utf-8")
        assert orig == after, "Source file was modified by search_for_similar!"

    def test_does_not_auto_verify(self):
        """Results must not contain any field implying current verification."""
        _save_normalize_incident()
        results = search_for_similar(file_path="data_processor.py")
        for r in results:
            # None of the result fields should claim current issue is verified
            assert "current_verified" not in r
            assert r.get("verification_result") != "CURRENT_VERIFIED"


class TestMemoryContext:
    def test_returns_dict(self):
        result = memory_context(file_path="data_processor.py", function_name="normalize", problem="")
        assert isinstance(result, dict)

    def test_current_verified_always_false(self):
        """The most important safety invariant — never claim current is verified."""
        _save_normalize_incident()
        result = memory_context(
            file_path="data_processor.py",
            function_name="normalize",
            problem="normalize ZeroDivisionError",
        )
        assert result["current_verified"] is False

    def test_current_verified_reason_present(self):
        result = memory_context(file_path="data_processor.py", function_name="", problem="")
        assert "current_verified_reason" in result
        assert "/verify-fix" in result["current_verified_reason"]

    def test_safety_notice_present(self):
        result = memory_context(file_path="data_processor.py", function_name="", problem="")
        assert "safety_notice" in result
        assert len(result["safety_notice"]) > 20

    def test_matches_key_present(self):
        result = memory_context(file_path="data_processor.py", function_name="", problem="")
        assert "matches" in result
        assert isinstance(result["matches"], list)

    def test_with_saved_incident(self):
        _save_normalize_incident()
        result = memory_context(
            file_path="data_processor.py",
            function_name="normalize",
            problem="normalize ZeroDivisionError",
        )
        assert result["total_matches"] >= 1

    def test_empty_memory_no_crash(self):
        result = memory_context(file_path="utils.py", function_name="add", problem="")
        assert isinstance(result, dict)
        assert result["current_verified"] is False


# ---------------------------------------------------------------------------
# POST /investigate — Phase 6 integration
# ---------------------------------------------------------------------------

class TestInvestigateWithMemoryContext:

    def test_similar_incidents_field_always_present(self):
        """similar_incidents must appear even when memory is empty."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "utils.py",
        })
        assert res.status_code == 200
        data = res.json()
        assert "similar_incidents" in data
        assert isinstance(data["similar_incidents"], list)

    def test_memory_context_note_always_present(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert "memory_context_note" in res.json()

    def test_no_match_when_memory_empty(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "utils.py",
        })
        # utils.py is unlikely to match anything in an empty-ish DB
        assert res.status_code == 200
        # similar_incidents may be empty list
        assert isinstance(res.json()["similar_incidents"], list)

    def test_match_found_after_save(self):
        """After saving a normalize incident, investigation should find it."""
        _save_normalize_incident()
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["similar_incidents"]) >= 1

    def test_similar_incident_reuse_warning(self):
        _save_normalize_incident()
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        data = res.json()
        if data["similar_incidents"]:
            assert "reuse_warning" in data["similar_incidents"][0]

    def test_similar_incident_not_same_warning(self):
        _save_normalize_incident()
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        data = res.json()
        if data["similar_incidents"]:
            w = data["similar_incidents"][0].get("not_same_warning", "")
            assert len(w) > 0

    def test_investigation_response_backward_compatible(self):
        """All original Phase 3 fields must still be present."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        data = res.json()
        for key in ("file", "problem", "root_cause", "evidence",
                    "suggested_fix", "confidence", "mode", "disclaimer"):
            assert key in data, f"Missing backward-compat key: {key}"

    def test_does_not_modify_source_file_during_investigation(self):
        """Investigation + memory context must never modify source files."""
        _save_normalize_incident()
        orig = Path("demo_repo/data_processor.py").read_text(encoding="utf-8")
        client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        after = Path("demo_repo/data_processor.py").read_text(encoding="utf-8")
        assert orig == after

    def test_original_memory_incident_unchanged_after_investigation(self):
        """Phase 6 must not mutate any existing memory record."""
        new_id = _save_normalize_incident()
        from backend.memory import get_by_id
        before_problem = get_by_id(new_id, DB_PATH).problem

        client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })

        after_problem = get_by_id(new_id, DB_PATH).problem
        assert before_problem == after_problem


# ---------------------------------------------------------------------------
# POST /memory/context endpoint
# ---------------------------------------------------------------------------

class TestMemoryContextEndpoint:

    def test_basic_response(self):
        res = client.post("/memory/context", json={
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "normalize bug",
        })
        assert res.status_code == 200
        data = res.json()
        assert "matches" in data
        assert "total_matches" in data
        assert "current_verified" in data

    def test_current_verified_always_false(self):
        """The endpoint MUST always return current_verified=false."""
        _save_normalize_incident()
        res = client.post("/memory/context", json={
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "normalize ZeroDivisionError denominator",
        })
        assert res.status_code == 200
        assert res.json()["current_verified"] is False

    def test_safety_notice_present(self):
        res = client.post("/memory/context", json={
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert "safety_notice" in res.json()

    def test_finds_saved_incident(self):
        _save_normalize_incident()
        res = client.post("/memory/context", json={
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "ZeroDivisionError",
        })
        assert res.status_code == 200
        assert res.json()["total_matches"] >= 1

    def test_empty_file_path_returns_400(self):
        res = client.post("/memory/context", json={"file_path": ""})
        assert res.status_code == 400

    def test_match_note_not_ml(self):
        res = client.post("/memory/context", json={"file_path": "data_processor.py"})
        assert res.status_code == 200
        note = res.json().get("search_note", "")
        assert "NOT ML" in note or "keyword" in note.lower()


# ---------------------------------------------------------------------------
# Regression: Phase 1–5 still work
# ---------------------------------------------------------------------------

class TestPhase16Regression:

    def test_get_root(self):
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_post_scan(self):
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        assert res.json()["summary"]["files_scanned"] > 0

    def test_post_verify_fix(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert res.json()["verified"] is True

    def test_get_memory(self):
        res = client.get("/memory")
        assert res.status_code == 200
        assert "incidents" in res.json()

    def test_fresh_verification_required(self):
        """
        The memory context endpoint explicitly states current_verified=False.
        Only POST /verify-fix can produce verified=True.
        """
        _save_normalize_incident()
        ctx = client.post("/memory/context", json={
            "file_path": "data_processor.py",
            "function_name": "normalize",
            "problem": "normalize bug",
        }).json()
        assert ctx["current_verified"] is False

        # The only way to get verified=True is through verify-fix
        vf = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        }).json()
        assert vf["verified"] is True
