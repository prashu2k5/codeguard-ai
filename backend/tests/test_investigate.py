"""
tests/test_investigate.py — Tests for the /investigate endpoint and ai_service.

These tests ALWAYS run in fallback mode (no OPENAI_API_KEY set) so they are
fully offline and deterministic.

Coverage:
  - POST /investigate with the known buggy file → returns structured result
  - POST /investigate fallback mode → mode field is "fallback-heuristic"
  - POST /investigate missing file → 404
  - POST /investigate empty file_path → 400
  - POST /investigate non-.py file → 400
  - POST /investigate empty repo_path → 400
  - ai_service.investigate() directly with known bug source
  - ai_service.investigate() with unknown source → low-confidence fallback
  - Bug documentation: normalize() actually fails with expected inputs
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

# Force fallback mode for all tests — never call a real AI API
os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.ai_service import investigate, InvestigationResult

client = TestClient(app)


# ---------------------------------------------------------------------------
# Bug documentation tests — proves the planted bug is real
# ---------------------------------------------------------------------------

class TestPlantedBug:
    """Verify that the bug in data_processor.normalize() actually fails."""

    def test_normalize_wrong_result(self):
        """normalize([0, 50, 100]) should return [0.0, 0.5, 1.0] but does not."""
        from demo_repo.data_processor import normalize
        result = normalize([0.0, 50.0, 100.0])
        # The buggy version gives ~[0, 0.505, 1.01] — NOT [0, 0.5, 1.0]
        assert result != [0.0, 0.5, 1.0], (
            "Bug has been fixed! Update this test to reflect the correct behaviour."
        )

    def test_normalize_zero_division(self):
        """normalize([0.0, 1.0]) should return [0.0, 1.0] but raises ZeroDivisionError."""
        from demo_repo.data_processor import normalize
        with pytest.raises(ZeroDivisionError):
            normalize([0.0, 1.0])

    def test_normalize_empty_still_works(self):
        """normalize([]) is not affected by the bug — guard against regression."""
        from demo_repo.data_processor import normalize
        assert normalize([]) == []

    def test_normalize_all_same_still_works(self):
        """normalize([5, 5, 5]) hits the min==max branch — not affected by bug."""
        from demo_repo.data_processor import normalize
        assert normalize([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# ai_service unit tests (always fallback mode)
# ---------------------------------------------------------------------------

class TestAiServiceFallback:

    def test_returns_investigation_result(self):
        source = (
            "def normalize(values):\n"
            "    min_v = min(values)\n"
            "    max_v = max(values)\n"
            "    return [(v - min_v) / (max_v - min_v - 1) for v in values]\n"
        )
        result = investigate("data_processor.py", source)
        assert isinstance(result, InvestigationResult)

    def test_fallback_is_flagged(self):
        result = investigate("data_processor.py", "def foo(): pass")
        assert result.is_fallback is True

    def test_known_bug_pattern_detected(self):
        """The off-by-one pattern should be detected by the heuristic."""
        source = "return [(v - min_v) / (max_v - min_v - 1) for v in values]\n"
        result = investigate("data_processor.py", source)
        assert result.is_fallback is True
        assert "ZeroDivisionError" in result.problem or "off-by-one" in result.problem.lower() or "wrong" in result.problem.lower()
        assert result.suggested_fix != ""
        assert result.confidence in ("High", "Medium", "Low")

    def test_no_pattern_returns_low_confidence(self):
        source = "def add(a, b):\n    return a + b\n"
        result = investigate("utils.py", source, bug_description="")
        assert result.is_fallback is True
        assert result.confidence == "Low"

    def test_syntax_error_detected(self):
        source = "def broken(\n"
        result = investigate("broken.py", source)
        assert result.is_fallback is True
        assert "syntax" in result.problem.lower() or "Syntax" in result.problem

    def test_to_dict_shape(self):
        result = investigate("data_processor.py", "def f(): pass")
        d = result.to_dict()
        for key in ("file", "problem", "root_cause", "evidence", "suggested_fix", "confidence", "mode", "disclaimer"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_mode_fallback(self):
        result = investigate("x.py", "def x(): pass")
        assert result.to_dict()["mode"] == "fallback-heuristic"

    def test_bug_description_included_in_fallback(self):
        result = investigate("x.py", "def x(): pass", bug_description="crashes on empty list")
        assert "crashes on empty list" in result.problem or result.confidence == "Low"


# ---------------------------------------------------------------------------
# POST /investigate endpoint tests
# ---------------------------------------------------------------------------

class TestInvestigateEndpoint:

    def test_investigate_known_bug_file(self):
        """Scanning the buggy data_processor.py should return a structured result."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["file"] == "data_processor.py"
        assert data["problem"]
        assert data["root_cause"]
        assert data["evidence"]
        assert data["suggested_fix"]
        assert data["confidence"] in ("High", "Medium", "Low")
        assert data["mode"] in ("ai-assisted", "fallback-heuristic")
        assert data["disclaimer"]

    def test_investigate_fallback_mode_label(self):
        """Without an API key the mode must be 'fallback-heuristic'."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert res.json()["mode"] == "fallback-heuristic"

    def test_investigate_with_bug_description(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
            "bug_description": "ZeroDivisionError when input has range of 1",
        })
        assert res.status_code == 200
        assert res.json()["file"] == "data_processor.py"

    def test_investigate_utils(self):
        """utils.py has no known bug — should return a low-confidence fallback."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "utils.py",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["confidence"] == "Low"
        assert data["mode"] == "fallback-heuristic"

    def test_investigate_missing_file(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "does_not_exist.py",
        })
        assert res.status_code == 404

    def test_investigate_empty_file_path(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "",
        })
        assert res.status_code == 400

    def test_investigate_empty_repo_path(self):
        res = client.post("/investigate", json={
            "repo_path": "",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 400

    def test_investigate_non_py_file(self, tmp_path):
        """Passing a non-.py file should return 400."""
        f = tmp_path / "notes.txt"
        f.write_text("some notes")
        res = client.post("/investigate", json={
            "repo_path": str(tmp_path),
            "file_path": "notes.txt",
        })
        assert res.status_code == 400

    def test_investigate_bad_repo_path(self):
        res = client.post("/investigate", json={
            "repo_path": "/path/that/does/not/exist/anywhere",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 404

    def test_investigate_all_demo_files(self):
        """All four demo source files should be investigatable without errors."""
        for fname in ("data_processor.py", "utils.py", "risk_engine.py", "reporter.py"):
            res = client.post("/investigate", json={
                "repo_path": "demo_repo",
                "file_path": fname,
            })
            assert res.status_code == 200, f"Failed for {fname}: {res.text}"


# ---------------------------------------------------------------------------
# Regression: Phase 1 endpoints still work
# ---------------------------------------------------------------------------

class TestPhase1Regression:

    def test_get_root(self):
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_post_scan(self):
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["files_scanned"] > 0
        assert all(0 <= f["risk_score"] <= 100 for f in data["files"])
