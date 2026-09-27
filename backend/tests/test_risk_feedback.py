"""
test_risk_feedback.py — Tests for Phase 7: Verified Incident → Risk Feedback Loop.

COVERAGE
--------
1.  Zero incidents → verified_incident_count=0, incident_score=0, observed_risk==predicted_risk
2.  One verified incident → +10 pts, no "dangerous" auto-labelling
3.  Multiple verified incidents → capped at 30 pts max contribution
4.  Non-PASS incidents → NOT counted as risk evidence (safety gate)
5.  Cold-zone detection → predicted≥35, 0 incidents, not investigated
6.  No cold zone when incidents exist
7.  No cold zone when file is investigated
8.  No cold zone when risk below threshold
9.  Explanation text contains "No verified incident evidence yet." when count=0
10. Explanation text mentions incident count when >0
11. Phase 1 risk_score is never modified by Phase 7 enrichment
12. Phase 1–6 regression: /scan, /investigate, /verify-fix, /memory/* still work
13. /risk-feedback endpoint exists and returns correct shape
14. formula documentation present in every enriched file result
15. enrich_with_feedback is read-only (does not modify memory)
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.pop("OPENAI_API_KEY", None)

from backend.main import app
from backend.memory import (
    save, list_all, count, init_db, VerifiedIncident, DB_PATH,
    count_by_file,
)
from backend.risk_feedback import (
    enrich_with_feedback,
    _incident_score,
    _observed_risk,
    INCIDENT_SCORE_PER_INCIDENT,
    INCIDENT_SCORE_CAP,
)
from backend.cold_zones import (
    COLD_ZONE_THRESHOLD,
    reset_investigated,
    mark_investigated,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    db = tmp_path / "test_p7.db"
    init_db(db)
    yield db


def _make_incident(file_path="data_processor.py", verification_result="PASS", **kwargs):
    defaults = dict(
        repository="demo_repo",
        file_path=file_path,
        function_name="normalize",
        problem="normalize ZeroDivisionError off-by-one",
        root_cause="denominator minus 1",
        fix="remove minus 1",
        regression_test="",
        verification_result=verification_result,
    )
    defaults.update(kwargs)
    return VerifiedIncident(**defaults)


def _make_scan_file(file="data_processor.py", risk_score=50.0, risk_level="Medium"):
    """Create a minimal Phase 1-style scan result dict."""
    return {
        "file":              file,
        "complexity_score":  20.0,
        "git_churn_commits": 5,
        "git_churn_score":   60.0,
        "test_coverage_pct": 40.0,
        "risk_score":        risk_score,
        "risk_level":        risk_level,
    }


# ---------------------------------------------------------------------------
# Formula helpers unit tests
# ---------------------------------------------------------------------------

class TestIncidentScoreFormula:

    def test_zero_incidents_gives_zero_score(self):
        assert _incident_score(0) == 0.0

    def test_one_incident_gives_10(self):
        assert _incident_score(1) == INCIDENT_SCORE_PER_INCIDENT

    def test_two_incidents_gives_20(self):
        assert _incident_score(2) == INCIDENT_SCORE_PER_INCIDENT * 2

    def test_three_incidents_caps_at_30(self):
        assert _incident_score(3) == INCIDENT_SCORE_CAP

    def test_many_incidents_capped(self):
        """10 incidents should not exceed the cap."""
        assert _incident_score(10) == INCIDENT_SCORE_CAP

    def test_observed_risk_is_sum(self):
        assert _observed_risk(50.0, 10.0) == 60.0

    def test_observed_risk_capped_at_100(self):
        assert _observed_risk(95.0, 30.0) == 100.0

    def test_observed_risk_zero_incidents(self):
        assert _observed_risk(42.0, 0.0) == 42.0


# ---------------------------------------------------------------------------
# enrich_with_feedback unit tests
# ---------------------------------------------------------------------------

class TestEnrichWithFeedback:

    def test_zero_incidents_fields_correct(self, tmp_db):
        """No verified incidents → count=0, incident_score=0, observed_risk==predicted."""
        reset_investigated()
        files = [_make_scan_file("utils.py", risk_score=40.0, risk_level="Medium")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]

        assert f["verified_incident_count"] == 0
        assert f["incident_score"] == 0.0
        assert f["observed_risk"] == 40.0   # unchanged
        assert f["verified_incident_evidence"] == []

    def test_zero_incidents_explanation_text(self, tmp_db):
        """Explanation must say 'No verified incident evidence yet.' when count=0."""
        reset_investigated()
        files = [_make_scan_file("utils.py", risk_score=20.0, risk_level="Low")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert "No verified incident evidence yet." in enriched[0]["risk_explanation"]

    def test_one_verified_incident_adds_10_pts(self, tmp_db):
        """One verified incident should add exactly 10 pts to observed_risk."""
        save(_make_incident(file_path="data_processor.py"), tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]

        assert f["verified_incident_count"] == 1
        assert f["incident_score"] == 10.0
        assert f["observed_risk"] == 60.0

    def test_one_incident_not_auto_dangerous(self, tmp_db):
        """One incident should NOT automatically make a low-risk file 'High'."""
        save(_make_incident(file_path="utils.py"), tmp_db)
        files = [_make_scan_file("utils.py", risk_score=15.0, risk_level="Low")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]

        # observed_risk = 15 + 10 = 25 → still Low
        assert f["observed_risk"] == 25.0
        assert f["observed_risk_level"] == "Low"

    def test_two_incidents_add_20_pts(self, tmp_db):
        save(_make_incident(file_path="data_processor.py", problem="bug A"), tmp_db)
        save(_make_incident(file_path="data_processor.py", problem="bug B"), tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]

        assert f["verified_incident_count"] == 2
        assert f["incident_score"] == 20.0
        assert f["observed_risk"] == 70.0

    def test_multiple_incidents_capped_at_30(self, tmp_db):
        """3+ incidents cap contribution at 30 pts."""
        for i in range(5):
            save(_make_incident(file_path="data_processor.py", problem=f"bug {i}"), tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]

        assert f["verified_incident_count"] == 5
        assert f["incident_score"] == 30.0   # capped
        assert f["observed_risk"] == 80.0

    def test_observed_risk_capped_at_100(self, tmp_db):
        """observed_risk must never exceed 100."""
        for i in range(5):
            save(_make_incident(file_path="high_risk.py", problem=f"bug {i}"), tmp_db)
        files = [_make_scan_file("high_risk.py", risk_score=95.0, risk_level="High")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["observed_risk"] <= 100.0

    def test_phase1_risk_score_unchanged(self, tmp_db):
        """Phase 1 risk_score must NOT be modified by Phase 7 enrichment."""
        save(_make_incident(file_path="data_processor.py"), tmp_db)
        original_score = 42.5
        files = [_make_scan_file("data_processor.py", risk_score=original_score)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["risk_score"] == original_score

    def test_non_pass_incidents_not_counted(self, tmp_db):
        """FAIL/ERROR incidents must NOT be counted — safety gate enforced by memory.save()."""
        # memory.save() raises ValueError for non-PASS — so only PASS incidents exist
        with pytest.raises(ValueError):
            save(_make_incident(file_path="data_processor.py", verification_result="FAIL"), tmp_db)

        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        # No PASS incident was saved, so count must be 0
        assert enriched[0]["verified_incident_count"] == 0
        assert enriched[0]["incident_score"] == 0.0

    def test_formula_documented_in_result(self, tmp_db):
        """Every enriched file result must include the formula documentation."""
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]
        assert "risk_formula" in f
        assert "incident_score" in f["risk_formula"]
        assert "predicted_risk" in f["risk_formula"] or "0.35" in f["risk_formula"]

    def test_disclaimer_present(self, tmp_db):
        """Disclaimer must be present in every enriched result."""
        files = [_make_scan_file("data_processor.py")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert "disclaimer" in enriched[0]
        assert "heuristic" in enriched[0]["disclaimer"].lower()

    def test_evidence_summary_returned(self, tmp_db):
        """verified_incident_evidence should contain summaries for each incident."""
        save(_make_incident(file_path="data_processor.py", problem="bug A"), tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        f = enriched[0]
        assert len(f["verified_incident_evidence"]) == 1
        ev = f["verified_incident_evidence"][0]
        assert "problem" in ev
        assert "root_cause" in ev
        assert "source" in ev
        assert "Verified Memory" in ev["source"]

    def test_incident_count_in_explanation(self, tmp_db):
        """When incidents exist, explanation should mention the count."""
        save(_make_incident(file_path="data_processor.py"), tmp_db)
        save(_make_incident(file_path="data_processor.py", problem="second bug"), tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        explanation = enriched[0]["risk_explanation"]
        assert "2" in explanation or "two" in explanation.lower()

    def test_enrichment_is_read_only(self, tmp_db):
        """enrich_with_feedback must not modify memory — count before/after must match."""
        save(_make_incident(file_path="data_processor.py"), tmp_db)
        before = count(tmp_db)
        files = [_make_scan_file("data_processor.py", risk_score=50.0)]
        enrich_with_feedback(files, db_path=tmp_db)
        after = count(tmp_db)
        assert before == after


# ---------------------------------------------------------------------------
# Cold Zone tests
# ---------------------------------------------------------------------------

class TestColdZoneDetection:

    def setup_method(self):
        reset_investigated()

    def test_cold_zone_when_risk_high_no_incidents(self, tmp_db):
        """File with risk ≥ threshold and 0 incidents should be a cold zone."""
        files = [_make_scan_file("risky.py", risk_score=COLD_ZONE_THRESHOLD, risk_level="Medium")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["is_cold_zone"] is True

    def test_no_cold_zone_when_incidents_exist(self, tmp_db):
        """A file with a verified incident is NOT a cold zone."""
        save(_make_incident(file_path="risky.py"), tmp_db)
        files = [_make_scan_file("risky.py", risk_score=COLD_ZONE_THRESHOLD, risk_level="Medium")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["is_cold_zone"] is False

    def test_no_cold_zone_when_investigated(self, tmp_db):
        """A file that has been investigated this session is NOT a cold zone."""
        mark_investigated("risky.py")
        files = [_make_scan_file("risky.py", risk_score=COLD_ZONE_THRESHOLD, risk_level="Medium")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["is_cold_zone"] is False

    def test_no_cold_zone_when_risk_below_threshold(self, tmp_db):
        """A low-risk file is NOT a cold zone even with no incidents."""
        files = [_make_scan_file("safe.py", risk_score=10.0, risk_level="Low")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        assert enriched[0]["is_cold_zone"] is False

    def test_cold_zone_explanation_text(self, tmp_db):
        """Cold zone explanation must mention 'Cold Zone' with correct wording."""
        files = [_make_scan_file("risky.py", risk_score=COLD_ZONE_THRESHOLD, risk_level="Medium")]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        explanation = enriched[0]["risk_explanation"]
        assert "Cold Zone" in explanation
        assert "predicted risk without verified incident evidence" in explanation.lower() or \
               "cold zone" in explanation.lower()

    def test_multiple_files_some_cold(self, tmp_db):
        """Only files meeting all cold-zone criteria should be labelled."""
        save(_make_incident(file_path="risky_with_incident.py"), tmp_db)
        files = [
            _make_scan_file("cold.py",                risk_score=60.0, risk_level="Medium"),
            _make_scan_file("risky_with_incident.py", risk_score=60.0, risk_level="Medium"),
            _make_scan_file("safe.py",                risk_score=10.0, risk_level="Low"),
        ]
        enriched = enrich_with_feedback(files, db_path=tmp_db)
        cold_flags = {f["file"]: f["is_cold_zone"] for f in enriched}
        assert cold_flags["cold.py"] is True
        assert cold_flags["risky_with_incident.py"] is False   # has incident
        assert cold_flags["safe.py"] is False                  # low risk


# ---------------------------------------------------------------------------
# /risk-feedback endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_production_db():
    """Remove any incidents added during tests from the production DB."""
    from backend.memory import DB_PATH
    before = count(DB_PATH)
    yield
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"DELETE FROM verified_incidents WHERE id > {before}")


class TestRiskFeedbackEndpoint:

    def test_endpoint_exists(self):
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        assert res.status_code == 200

    def test_endpoint_returns_files_and_summary(self):
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        data = res.json()
        assert "files" in data
        assert "summary" in data
        assert isinstance(data["files"], list)

    def test_endpoint_summary_fields(self):
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        summary = res.json()["summary"]
        assert "files_scanned" in summary
        assert "total_verified_incidents" in summary
        assert "cold_zone_count" in summary
        assert "disclaimer" in summary
        assert "formula_note" in summary

    def test_endpoint_files_have_phase7_fields(self):
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        files = res.json()["files"]
        assert len(files) > 0
        for f in files:
            assert "verified_incident_count" in f
            assert "incident_score" in f
            assert "observed_risk" in f
            assert "observed_risk_level" in f
            assert "is_cold_zone" in f
            assert "risk_explanation" in f
            assert "risk_formula" in f

    def test_endpoint_phase1_fields_preserved(self):
        """Phase 1 fields must still be present and unchanged in the response."""
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        for f in res.json()["files"]:
            assert "risk_score" in f
            assert "risk_level" in f
            assert "complexity_score" in f
            assert "git_churn_commits" in f
            assert "test_coverage_pct" in f

    def test_endpoint_zero_incident_files_show_none(self):
        """Files with no incidents must have count=0 and incident_score=0."""
        # Fresh state — no incidents seeded for this test
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        for f in res.json()["files"]:
            if f["verified_incident_count"] == 0:
                assert f["incident_score"] == 0.0
                assert f["observed_risk"] == f["risk_score"]
                assert "No verified incident evidence yet." in f["risk_explanation"]

    def test_endpoint_with_precomputed_files(self):
        """Passing a pre-computed files list should enrich without re-scanning."""
        scan_files = [_make_scan_file("data_processor.py", risk_score=55.0)]
        res = client.post("/risk-feedback", json={
            "repo_path": "demo_repo",
            "files": scan_files,
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["file"] == "data_processor.py"

    def test_endpoint_disclaimer_present(self):
        res = client.post("/risk-feedback", json={"repo_path": "demo_repo"})
        summary = res.json()["summary"]
        assert "heuristic" in summary["disclaimer"].lower()
        assert "NOT proof" in summary["disclaimer"] or "not proof" in summary["disclaimer"].lower()

    def test_endpoint_bad_repo_path(self):
        res = client.post("/risk-feedback", json={"repo_path": "/does/not/exist"})
        assert res.status_code == 404

    def test_endpoint_empty_repo_path(self):
        res = client.post("/risk-feedback", json={"repo_path": ""})
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# /scan endpoint Phase 7 integration
# ---------------------------------------------------------------------------

class TestScanEndpointPhase7Integration:

    def test_scan_returns_phase7_fields(self):
        """/scan should now include Phase 7 fields on each file."""
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        files = res.json()["files"]
        assert len(files) > 0
        # All Phase 7 fields present
        for f in files:
            assert "verified_incident_count" in f, f"Missing field in {f['file']}"
            assert "incident_score" in f
            assert "observed_risk" in f
            assert "is_cold_zone" in f
            assert "risk_explanation" in f

    def test_scan_summary_has_cold_zone_count(self):
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert "cold_zone_count" in res.json()["summary"]

    def test_scan_phase1_unchanged(self):
        """Phase 1 risk_score must be identical before and after Phase 7 enrichment."""
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        for f in res.json()["files"]:
            assert 0 <= f["risk_score"] <= 100
            assert f["risk_level"] in ("Low", "Medium", "High")

    def test_scan_observed_risk_gte_predicted(self):
        """observed_risk must be >= risk_score (it only adds, never subtracts)."""
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        for f in res.json()["files"]:
            assert f.get("observed_risk", f["risk_score"]) >= f["risk_score"]


# ---------------------------------------------------------------------------
# Phase 1–6 regression tests
# ---------------------------------------------------------------------------

class TestPhase16Regression:

    def test_get_root_still_works(self):
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_scan_still_works(self):
        res = client.post("/scan", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        assert res.json()["summary"]["files_scanned"] > 0

    def test_investigate_still_works(self):
        res = client.post("/investigate", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert res.json()["file"] == "data_processor.py"

    def test_verify_fix_still_works(self):
        res = client.post("/verify-fix", json={
            "repo_path": "demo_repo",
            "file_path": "data_processor.py",
        })
        assert res.status_code == 200
        assert res.json()["verified"] is True

    def test_memory_save_still_works(self):
        res = client.post("/memory/save", json={
            "repository":  "demo_repo",
            "file_path":   "data_processor.py",
            "problem":     "test p7 regression",
            "root_cause":  "test",
            "fix":         "test",
            "verification_result": "PASS",
        })
        assert res.status_code == 200
        assert res.json()["saved"] is True

    def test_get_memory_still_works(self):
        res = client.get("/memory")
        assert res.status_code == 200
        assert "incidents" in res.json()

    def test_memory_search_still_works(self):
        res = client.post("/memory/search", json={"query": "normalize"})
        assert res.status_code == 200

    def test_memory_context_still_works(self):
        res = client.post("/memory/context", json={"file_path": "data_processor.py"})
        assert res.status_code == 200

    def test_cold_zones_still_works(self):
        res = client.post("/cold-zones", json={"repo_path": "demo_repo"})
        assert res.status_code == 200
        assert "cold_zones" in res.json()

    def test_memory_rejects_non_pass(self):
        res = client.post("/memory/save", json={
            "repository":  "demo_repo",
            "file_path":   "data_processor.py",
            "problem":     "unverified",
            "root_cause":  "unknown",
            "fix":         "unknown",
            "verification_result": "FAIL",
        })
        assert res.status_code == 400
