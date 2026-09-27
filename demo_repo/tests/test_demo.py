"""
Tests for the demo_repo package.

Coverage note: utils and risk_engine are well-tested here.
data_processor is partially covered.
reporter is intentionally undertested to show a test-gap signal.
"""

import pytest
from demo_repo.utils import add, subtract, multiply, greet
from demo_repo.data_processor import filter_even, filter_odd, normalize, group_by_key
from demo_repo.risk_engine import (
    classify_risk,
    score_item,
    rank_files,
    compute_portfolio_risk,
    detect_anomalies,
)


# ---------------------------------------------------------------------------
# utils — fully covered
# ---------------------------------------------------------------------------

class TestUtils:
    def test_add(self):
        assert add(2, 3) == 5

    def test_add_negative(self):
        assert add(-1, 1) == 0

    def test_subtract(self):
        assert subtract(5, 3) == 2

    def test_multiply(self):
        assert multiply(4, 3) == 12

    def test_greet_with_name(self):
        assert greet("Alice") == "Hello, Alice!"

    def test_greet_empty(self):
        assert greet("") == "Hello, stranger!"


# ---------------------------------------------------------------------------
# data_processor — partially covered (summarize is missing → shows gap)
# ---------------------------------------------------------------------------

class TestDataProcessor:
    def test_filter_even(self):
        assert filter_even([1, 2, 3, 4, 5]) == [2, 4]

    def test_filter_odd(self):
        assert filter_odd([1, 2, 3, 4, 5]) == [1, 3, 5]

    def test_normalize_basic(self):
        result = normalize([0.0, 50.0, 100.0])
        assert result == [0.0, 0.5, 1.0]

    def test_normalize_empty(self):
        assert normalize([]) == []

    def test_normalize_all_same(self):
        assert normalize([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]

    def test_group_by_key(self):
        records = [
            {"type": "A", "val": 1},
            {"type": "B", "val": 2},
            {"type": "A", "val": 3},
        ]
        grouped = group_by_key(records, "type")
        assert len(grouped["A"]) == 2
        assert len(grouped["B"]) == 1

    # NOTE: summarize() is NOT tested here — intentional gap for demo purposes.


# ---------------------------------------------------------------------------
# risk_engine — fully covered
# ---------------------------------------------------------------------------

class TestRiskEngine:
    def test_classify_low(self):
        assert classify_risk(0) == "Low"
        assert classify_risk(32) == "Low"

    def test_classify_medium(self):
        assert classify_risk(33) == "Medium"
        assert classify_risk(65) == "Medium"

    def test_classify_high(self):
        assert classify_risk(66) == "High"
        assert classify_risk(100) == "High"

    def test_score_item_basic(self):
        score = score_item(complexity=50, churn=50, coverage=50)
        # test_gap = 50, so: 0.35*50 + 0.35*50 + 0.30*50 = 50
        assert abs(score - 50.0) < 0.01

    def test_score_item_perfect_coverage(self):
        score = score_item(complexity=0, churn=0, coverage=100)
        assert score == 0.0

    def test_score_item_worst_case(self):
        score = score_item(complexity=100, churn=100, coverage=0)
        assert score == 100.0

    def test_score_item_clamped(self):
        # Even with extreme inputs the score stays in [0, 100]
        score = score_item(complexity=200, churn=200, coverage=-50)
        assert 0.0 <= score <= 100.0

    def test_score_item_custom_weights(self):
        weights = {"complexity": 1.0, "churn": 0.0, "test_gap": 0.0}
        score = score_item(complexity=60, churn=0, coverage=100, weights=weights)
        assert abs(score - 60.0) < 0.01

    def test_rank_files(self):
        files = [
            {"file": "a.py", "risk_score": 80},
            {"file": "b.py", "risk_score": 20},
            {"file": "c.py", "risk_score": 55},
        ]
        ranked = rank_files(files, top_n=2)
        assert ranked[0]["file"] == "a.py"
        assert ranked[1]["file"] == "c.py"

    def test_compute_portfolio_risk_empty(self):
        result = compute_portfolio_risk([])
        assert result["total_files"] == 0
        assert result["average_risk"] == 0.0

    def test_compute_portfolio_risk(self):
        files = [
            {"file": "a.py", "risk_score": 80, "risk_level": "High"},
            {"file": "b.py", "risk_score": 20, "risk_level": "Low"},
        ]
        result = compute_portfolio_risk(files)
        assert result["total_files"] == 2
        assert result["average_risk"] == 50.0
        assert result["distribution"]["High"] == 1
        assert result["distribution"]["Low"] == 1

    def test_detect_anomalies_not_enough(self):
        assert detect_anomalies([{"file": "a.py", "risk_score": 90}]) == []

    def test_detect_anomalies(self):
        files = [
            {"file": "normal.py", "risk_score": 10},
            {"file": "normal2.py", "risk_score": 12},
            {"file": "outlier.py", "risk_score": 95},
        ]
        anomalies = detect_anomalies(files, z_threshold=1.0)
        assert len(anomalies) == 1
        assert anomalies[0][0] == "outlier.py"
