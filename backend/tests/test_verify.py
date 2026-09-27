"""
test_verify.py — Tests for the /verify-fix endpoint and verifier module.

These tests verify:
  1. The full verification workflow against the live buggy file
  2. Safety: verified=True only when all three conditions pass
  3. before=FAIL (bug is present)
  4. after=PASS (fix works)
  5. regression_suite=PASS (nothing else broken)
  6. Error handling: missing file, unknown file, bad repo
  7. The original file is ALWAYS restored after verification

Tests run offline (no AI key needed) and are deterministic.
The demo_repo/data_processor.py bug MUST be present for these tests to pass.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Ensure no OpenAI key bleeds in
os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.verifier import verify_fix, _apply_fix, _find_registered_fix, VerificationResult

client = TestClient(app)

# Path to the buggy file
DATA_PROCESSOR = Path("demo_repo/data_processor.py")
BUGGY_PATTERN  = "(max_v - min_v - 1)"
FIXED_PATTERN  = "(max_v - min_v)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_is_buggy() -> bool:
    return BUGGY_PATTERN in DATA_PROCESSOR.read_text(encoding="utf-8")


def _source_is_fixed() -> bool:
    return FIXED_PATTERN in DATA_PROCESSOR.read_text(encoding="utf-8") and \
           BUGGY_PATTERN not in DATA_PROCESSOR.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# verifier unit tests
# ---------------------------------------------------------------------------

class TestApplyFix:
    def test_known_pattern_replaced(self):
        source = "return [(v - min_v) / (max_v - min_v - 1) for v in values]"
        result = _apply_fix(source, "(max_v - min_v - 1)", "(max_v - min_v)")
        assert "(max_v - min_v - 1)" not in result
        assert "(max_v - min_v)" in result

    def test_original_not_mutated(self):
        source = "x = (max_v - min_v - 1)"
        fixed = _apply_fix(source, "(max_v - min_v - 1)", "(max_v - min_v)")
        assert source == "x = (max_v - min_v - 1)"  # original unchanged
        assert fixed  == "x = (max_v - min_v)"

    def test_raises_if_pattern_missing(self):
        with pytest.raises(ValueError, match="not found"):
            _apply_fix("def foo(): pass", "(max_v - min_v - 1)", "(max_v - min_v)")

    def test_only_first_occurrence_replaced(self):
        source = "(max_v - min_v - 1) and (max_v - min_v - 1)"
        fixed = _apply_fix(source, "(max_v - min_v - 1)", "(max_v - min_v)")
        assert fixed.count("(max_v - min_v - 1)") == 1  # second still present


class TestFindRegisteredFix:
    def test_finds_data_processor_fix(self):
        source = DATA_PROCESSOR.read_text(encoding="utf-8")
        result = _find_registered_fix("data_processor.py", source)
        assert result is not None
        search, replace, desc = result
        assert search  == "(max_v - min_v - 1)"
        assert replace == "(max_v - min_v)"
        assert desc

    def test_no_match_unknown_file(self):
        assert _find_registered_fix("unknown.py", "def foo(): pass") is None

    def test_no_match_fixed_source(self):
        """If the fix has already been applied, the pattern is gone → no match."""
        source = DATA_PROCESSOR.read_text(encoding="utf-8").replace(
            "(max_v - min_v - 1)", "(max_v - min_v)"
        )
        assert _find_registered_fix("data_processor.py", source) is None


# ---------------------------------------------------------------------------
# Full verification workflow — verifier unit tests
# ---------------------------------------------------------------------------

class TestVerifyFix:

    def test_file_restored_after_verification(self):
        """The original buggy source must be present both before and after the run."""
        assert _source_is_buggy(), "Precondition: bug must be present"
        original = DATA_PROCESSOR.read_text(encoding="utf-8")

        verify_fix(".", "demo_repo/data_processor.py")

        restored = DATA_PROCESSOR.read_text(encoding="utf-8")
        assert restored == original, "File was NOT restored after verification!"

    def test_verified_is_true(self):
        """The full sequence must produce verified=True."""
        result = verify_fix(".", "demo_repo/data_processor.py")
        assert result.verified is True, (
            f"Expected verified=True. Failure reason: {result.failure_reason}"
        )

    def test_before_is_fail(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        assert result.before.test_result == "FAIL", (
            f"Expected FAIL before fix, got: {result.before.test_result}\n"
            f"Output:\n{result.before.output}"
        )

    def test_after_is_pass(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        assert result.after.test_result == "PASS", (
            f"Expected PASS after fix, got: {result.after.test_result}\n"
            f"Output:\n{result.after.output}"
        )

    def test_regression_suite_passes(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        assert result.regression_suite.test_result == "PASS", (
            f"Regression suite: {result.regression_suite.tests_failed} test(s) failed\n"
            f"Output:\n{result.regression_suite.output}"
        )

    def test_counts_populated(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        # Before: regression file has 5 failing tests
        assert result.before.tests_failed >= 1
        # After: regression file should pass all tests
        assert result.after.tests_passed >= 1
        assert result.after.tests_failed == 0

    def test_output_strings_not_empty(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        assert result.before.output.strip()
        assert result.after.output.strip()
        assert result.regression_suite.output.strip()

    def test_to_dict_shape(self):
        result = verify_fix(".", "demo_repo/data_processor.py")
        d = result.to_dict()
        for key in ("file", "fix_description", "before", "after", "regression_suite",
                    "verified", "failure_reason", "disclaimer"):
            assert key in d, f"Missing key: {key}"
        for section in ("before", "after"):
            for sub in ("test_result", "output", "tests_passed", "tests_failed"):
                assert sub in d[section], f"Missing {section}.{sub}"
        for sub in ("result", "output", "tests_passed", "tests_failed"):
            assert sub in d["regression_suite"], f"Missing regression_suite.{sub}"

    def test_disclaimer_wording(self):
        """Must NOT say 'AI' proved the fix."""
        result = verify_fix(".", "demo_repo/data_processor.py")
        d = result.to_dict()
        assert "AI proved" not in d["disclaimer"]
        assert "independently verified" in d["disclaimer"].lower()

    def test_missing_file_returns_error(self):
        result = verify_fix(".", "demo_repo/does_not_exist.py")
        assert result.verified is False
        assert result.failure_reason

    def test_no_registered_fix_returns_error(self):
        """utils.py has no registered fix — should not crash."""
        result = verify_fix(".", "demo_repo/utils.py")
        assert result.verified is False
        assert "No registered fix" in result.failure_reason

    def test_file_always_restored_even_on_weird_input(self):
        """Even when no fix found, the file must not be modified."""
        original = DATA_PROCESSOR.read_text(encoding="utf-8")
        verify_fix(".", "demo_repo/utils.py")  # wrong file but same repo
        assert DATA_PROCESSOR.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# POST /verify-fix endpoint tests
# ---------------------------------------------------------------------------

class TestVerifyFixEndpoint:

    def test_known_bug_file_verified(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["verified"] is True
        assert data["before"]["test_result"]  == "FAIL"
        assert data["after"]["test_result"]   == "PASS"
        assert data["regression_suite"]["result"] == "PASS"

    def test_response_shape(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        d = res.json()
        for key in ("file", "fix_description", "before", "after",
                    "regression_suite", "verified", "failure_reason", "disclaimer"):
            assert key in d

    def test_disclaimer_no_ai_claim(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        disclaimer = res.json()["disclaimer"]
        assert "AI proved" not in disclaimer
        assert "independently verified" in disclaimer.lower()

    def test_unverifiable_file_returns_200_verified_false(self):
        """utils.py has no registered fix — verified should be False, not a 500."""
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "utils.py",
        })
        assert res.status_code == 200
        assert res.json()["verified"] is False

    def test_missing_file_returns_200_verified_false(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "no_such_file.py",
        })
        assert res.status_code == 200
        assert res.json()["verified"] is False

    def test_empty_repo_path_returns_400(self):
        res = client.post("/verify-fix", json={
            "repo_path": "",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 400

    def test_empty_file_path_returns_400(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "",
        })
        assert res.status_code == 400

    def test_bad_repo_path_returns_404(self):
        res = client.post("/verify-fix", json={
            "repo_path": "/no/such/repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 404

    def test_file_still_buggy_after_endpoint(self):
        """The endpoint must never permanently fix the file."""
        client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert _source_is_buggy(), "Bug was permanently fixed — file not restored!"

    def test_phase1_scan_still_works(self):
        """Phase 1 regression: /scan must still return valid results."""
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["files_scanned"] > 0
        assert all(0 <= f["risk_score"] <= 100 for f in data["files"])

    def test_phase3_investigate_still_works(self):
        """Phase 3 regression: /investigate must still work."""
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert res.json()["problem"]
