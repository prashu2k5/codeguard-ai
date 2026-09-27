# risk_engine.py — high complexity, high churn
# This module went through many iterations as the scoring algorithm evolved.

from typing import List, Dict, Any, Optional, Tuple


def classify_risk(score: float) -> str:
    """Map a numeric score to Low / Medium / High."""
    if score < 33:
        return "Low"
    if score < 66:
        return "Medium"
    return "High"


def score_item(
    complexity: float,
    churn: float,
    coverage: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Compute a weighted risk score.

    Parameters
    ----------
    complexity : 0–100 normalised complexity value
    churn      : 0–100 normalised churn value
    coverage   : 0–100 test coverage percentage (higher is better)
    weights    : optional dict with keys 'complexity', 'churn', 'test_gap'

    Returns
    -------
    float between 0 and 100 (higher = riskier)
    """
    if weights is None:
        weights = {"complexity": 0.35, "churn": 0.35, "test_gap": 0.30}

    test_gap = 100.0 - coverage  # invert: low coverage → high gap

    raw = (
        weights["complexity"] * complexity
        + weights["churn"] * churn
        + weights["test_gap"] * test_gap
    )
    # clamp to [0, 100]
    return max(0.0, min(100.0, raw))


def rank_files(
    files: List[Dict[str, Any]], top_n: int = 3
) -> List[Dict[str, Any]]:
    """Return the top_n highest-risk files from a list of file result dicts."""
    sorted_files = sorted(files, key=lambda f: f.get("risk_score", 0), reverse=True)
    return sorted_files[:top_n]


def compute_portfolio_risk(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics for a scanned portfolio."""
    if not files:
        return {"total_files": 0, "average_risk": 0.0, "highest_risk_files": []}

    scores = [f.get("risk_score", 0.0) for f in files]
    average = sum(scores) / len(scores)

    high_risk = [f for f in files if f.get("risk_level") == "High"]
    medium_risk = [f for f in files if f.get("risk_level") == "Medium"]
    low_risk = [f for f in files if f.get("risk_level") == "Low"]

    distribution: Dict[str, int] = {
        "High": len(high_risk),
        "Medium": len(medium_risk),
        "Low": len(low_risk),
    }

    recommendations = []
    if high_risk:
        recommendations.append(
            f"{len(high_risk)} file(s) are high-risk — prioritise review and testing."
        )
    if medium_risk:
        recommendations.append(
            f"{len(medium_risk)} file(s) are medium-risk — consider adding tests."
        )
    if not high_risk and not medium_risk:
        recommendations.append("All files are low-risk. Good job!")

    return {
        "total_files": len(files),
        "average_risk": round(average, 2),
        "distribution": distribution,
        "highest_risk_files": rank_files(files),
        "recommendations": recommendations,
    }


def detect_anomalies(
    files: List[Dict[str, Any]],
    z_threshold: float = 1.5,
) -> List[Tuple[str, str]]:
    """
    Flag files whose risk score is more than z_threshold standard deviations
    above the mean. Returns a list of (file_path, reason) tuples.
    """
    if len(files) < 2:
        return []

    scores = [f.get("risk_score", 0.0) for f in files]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = variance ** 0.5

    if std == 0:
        return []

    anomalies: List[Tuple[str, str]] = []
    for f in files:
        z = (f.get("risk_score", 0.0) - mean) / std
        if z > z_threshold:
            anomalies.append(
                (
                    f.get("file", "unknown"),
                    f"Risk score {f['risk_score']:.1f} is {z:.1f}σ above the mean.",
                )
            )
    return anomalies

# iteration 1


# iteration 2


# iteration 3


# iteration 4


# iteration 5

