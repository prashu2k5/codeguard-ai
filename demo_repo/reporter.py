# reporter.py — output formatting helpers (low complexity, barely tested)

from typing import List, Dict, Any


def format_table_row(file_result: Dict[str, Any]) -> str:
    """Format a single file result as a fixed-width table row."""
    name = file_result.get("file", "?")[:40].ljust(40)
    score = f"{file_result.get('risk_score', 0):.1f}".rjust(6)
    level = file_result.get("risk_level", "?").ljust(8)
    churn = str(file_result.get("git_churn", 0)).rjust(6)
    cov = f"{file_result.get('test_coverage', 0):.0f}%".rjust(6)
    return f"{name} {score} {level} {churn} {cov}"


def format_report(summary: Dict[str, Any], files: List[Dict[str, Any]]) -> str:
    """Render a plain-text report string for terminal output."""
    header = (
        f"{'FILE':<40} {'SCORE':>6} {'LEVEL':<8} {'CHURN':>6} {'COV':>6}\n"
        + "-" * 72
    )
    rows = [format_table_row(f) for f in files]
    body = "\n".join(rows)

    avg = summary.get("average_risk", 0)
    total = summary.get("total_files", 0)

    footer = (
        "-" * 72 + "\n"
        f"Files scanned: {total}   Average risk: {avg:.1f}"
    )
    return f"{header}\n{body}\n{footer}"


def to_badge(risk_level: str) -> str:
    """Return a simple ASCII badge for a risk level."""
    badges = {
        "Low": "[LOW   ]",
        "Medium": "[MEDIUM]",
        "High": "[HIGH  ]",
    }
    return badges.get(risk_level, "[?]")
