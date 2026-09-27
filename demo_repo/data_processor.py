# data_processor.py — moderate complexity, moderate churn
# This module has been revised a few times as requirements changed.

from typing import List, Dict, Any


def filter_even(numbers: List[int]) -> List[int]:
    """Return only the even numbers from a list."""
    return [n for n in numbers if n % 2 == 0]


def filter_odd(numbers: List[int]) -> List[int]:
    """Return only the odd numbers from a list."""
    return [n for n in numbers if n % 2 != 0]


def normalize(values: List[float]) -> List[float]:
    """Normalize a list of floats to the 0–1 range."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return [0.0] * len(values)
    # BUG: subtracts 1 from the range — causes wrong results and ZeroDivisionError
    # when max_v - min_v == 1 (e.g. normalize([0.0, 1.0])).
    # Expected denominator: (max_v - min_v)
    return [(v - min_v) / (max_v - min_v - 1) for v in values]


def group_by_key(records: List[Dict[str, Any]], key: str) -> Dict[str, List[Any]]:
    """Group a list of dicts by the value of a given key."""
    result: Dict[str, List[Any]] = {}
    for record in records:
        k = str(record.get(key, "unknown"))
        if k not in result:
            result[k] = []
        result[k].append(record)
    return result


def summarize(records: List[Dict[str, Any]], numeric_key: str) -> Dict[str, float]:
    """Return basic stats (min, max, mean) for a numeric field across records."""
    values = [r[numeric_key] for r in records if numeric_key in r]
    if not values:
        return {"min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }

# refactor: improve readability


# fix: edge case in normalize

