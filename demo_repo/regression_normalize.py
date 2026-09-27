"""
regression_normalize.py — Regression test for the normalize() off-by-one bug.

This file is the INDEPENDENT regression test used by the Phase 4 verifier.

It is designed to:
  - FAIL against the buggy code:   (max_v - min_v - 1)
  - PASS against the correct code: (max_v - min_v)

Run directly:
    pytest demo_repo/regression_normalize.py -v

Do NOT add extra imports or side effects — the verifier runs this file in
isolation against both the broken and fixed versions of data_processor.py.
"""

import pytest
from demo_repo.data_processor import normalize


class TestNormalizeRegression:
    """Regression tests for normalize() — documents the expected contract."""

    def test_basic_range(self):
        """
        Given [0, 50, 100], the normalised result must be [0.0, 0.5, 1.0].

        Buggy behaviour: denominator is (100 - 0 - 1) = 99 instead of 100,
        producing [0.0, 0.5050…, 1.0101…].
        """
        result = normalize([0.0, 50.0, 100.0])
        assert result == pytest.approx([0.0, 0.5, 1.0]), (
            f"normalize([0, 50, 100]) returned {result}, expected [0.0, 0.5, 1.0]. "
            "Check for off-by-one in the denominator."
        )

    def test_unit_range_no_zero_division(self):
        """
        Given [0.0, 1.0], must NOT raise ZeroDivisionError.

        Buggy behaviour: denominator is (1 - 0 - 1) = 0 → ZeroDivisionError.
        """
        result = normalize([0.0, 1.0])
        assert result == pytest.approx([0.0, 1.0]), (
            f"normalize([0.0, 1.0]) returned {result}, expected [0.0, 1.0]."
        )

    def test_two_element_result(self):
        """normalize([10.0, 20.0]) must return [0.0, 1.0]."""
        result = normalize([10.0, 20.0])
        assert result == pytest.approx([0.0, 1.0])

    def test_all_output_in_unit_range(self):
        """Every output value must be in [0.0, 1.0]."""
        values = [3.0, 7.0, 15.0, 22.0, 50.0]
        result = normalize(values)
        for v in result:
            assert 0.0 <= v <= 1.0, (
                f"Value {v} is outside [0, 1]. "
                "The denominator is likely wrong."
            )

    def test_min_is_zero_max_is_one(self):
        """First element must normalise to 0.0, last to 1.0."""
        values = [5.0, 10.0, 15.0]
        result = normalize(values)
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(1.0)

    # --- Edge cases that must pass regardless of the bug ---

    def test_empty_list(self):
        """normalize([]) must return []."""
        assert normalize([]) == []

    def test_all_same_values(self):
        """normalize([7, 7, 7]) must return [0, 0, 0] (no division needed)."""
        assert normalize([7.0, 7.0, 7.0]) == [0.0, 0.0, 0.0]

    def test_single_element(self):
        """normalize([42.0]) hits min==max branch — must return [0.0]."""
        assert normalize([42.0]) == [0.0]
