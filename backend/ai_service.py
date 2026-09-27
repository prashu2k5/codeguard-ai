"""
ai_service.py — AI investigation service for the Code Health scanner.

This module provides a single public function:

    investigate(file_path, source_code, bug_description) -> InvestigationResult

It tries the following in order:
  1. OpenAI (if OPENAI_API_KEY is set in the environment / .env file)
  2. Fallback heuristic analyser (always available — clearly labelled as fallback)

The rest of the application only imports `investigate` and never touches the
OpenAI client directly, keeping the AI logic encapsulated here.
"""

from __future__ import annotations

import os
import re
import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path

# Load .env file if python-dotenv is available (optional dependency)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class InvestigationResult:
    file: str
    problem: str
    root_cause: str
    evidence: str
    suggested_fix: str
    confidence: str
    is_fallback: bool = False  # True = heuristic fallback, not real AI

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "problem": self.problem,
            "root_cause": self.root_cause,
            "evidence": self.evidence,
            "suggested_fix": self.suggested_fix,
            "confidence": self.confidence,
            "mode": "fallback-heuristic" if self.is_fallback else "ai-assisted",
            "disclaimer": (
                "⚠ AI Investigation — Not Yet Verified. "
                "This analysis is an automated estimate and has not been "
                "confirmed by running tests or human review."
            ) if not self.is_fallback else (
                "⚠ Fallback Mode — No AI API key configured. "
                "This is a static heuristic analysis, NOT a real AI result. "
                "Set OPENAI_API_KEY in your .env file to enable AI investigation."
            ),
        }


# ---------------------------------------------------------------------------
# OpenAI investigation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert Python code reviewer performing a focused bug investigation.
You will be given a Python source file and an optional bug description.

Respond ONLY with a JSON object (no markdown fences) with exactly these keys:
  "problem"      – one sentence describing the observable bug or issue
  "root_cause"   – one or two sentences on the underlying code mistake
  "evidence"     – the exact line(s) of code that contain the bug, quoted verbatim
  "suggested_fix"– a concrete code snippet showing the corrected line(s)
  "confidence"   – one of: High / Medium / Low

Be concise and precise. Do not add extra keys.
"""


def _investigate_with_openai(
    file_path: str,
    source_code: str,
    bug_description: str,
) -> InvestigationResult:
    """Call the OpenAI Chat API and parse the structured response."""
    import json
    import openai  # type: ignore

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    user_content = f"File: {file_path}\n\n"
    if bug_description:
        user_content += f"Bug hint: {bug_description}\n\n"
    user_content += f"Source code:\n```python\n{source_code}\n```"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    # Strip accidental markdown fences if the model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    return InvestigationResult(
        file=file_path,
        problem=data.get("problem", "Unknown problem"),
        root_cause=data.get("root_cause", "Unknown root cause"),
        evidence=data.get("evidence", ""),
        suggested_fix=data.get("suggested_fix", ""),
        confidence=data.get("confidence", "Low"),
        is_fallback=False,
    )


# ---------------------------------------------------------------------------
# Fallback heuristic analyser
# ---------------------------------------------------------------------------

# Known bug patterns: (regex_on_source, problem, root_cause, evidence_pattern, fix)
_PATTERNS = [
    (
        r"/\s*\(\s*max_v\s*-\s*min_v\s*-\s*1\s*\)",
        "normalize() produces wrong results and raises ZeroDivisionError when max - min == 1.",
        "The denominator `(max_v - min_v - 1)` subtracts 1 from the true range. "
        "For any input where max − min equals 1 this causes division by zero; "
        "for all other inputs the scaled values are inflated beyond [0, 1].",
        "(v - min_v) / (max_v - min_v - 1)",
        "Change the denominator to `(max_v - min_v)` (remove the `- 1`):\n"
        "    return [(v - min_v) / (max_v - min_v) for v in values]",
    ),
    (
        r"except\s+Exception\s*:",
        "Overly broad exception handler swallows all errors, hiding real failures.",
        "Catching the base `Exception` class prevents specific error types from "
        "propagating, making debugging very difficult.",
        "except Exception:",
        "Catch only the specific exception types you expect, e.g.:\n"
        "    except (ValueError, KeyError) as e:",
    ),
    (
        r"\brange\s*\(\s*1\s*,\s*len\s*\(",
        "Off-by-one: loop starts at index 1 instead of 0, silently skipping the first element.",
        "Using `range(1, len(x))` as an index skips element 0. "
        "This is almost always a bug when iterating over a list.",
        "range(1, len(",
        "Start the range at 0:\n    for i in range(len(x)):",
    ),
    (
        r"\bappend\b.*\binside\b.*\bloop\b|for\b.*\bappend\b.*\bfor\b",
        "Potential quadratic behaviour: list appended inside nested loop.",
        "Appending to a list inside a nested loop creates O(n²) behaviour "
        "that becomes very slow on large inputs.",
        "append() inside nested loop",
        "Consider using a list comprehension or pre-allocating the result list.",
    ),
]


def _fallback_investigate(
    file_path: str,
    source_code: str,
    bug_description: str,
) -> InvestigationResult:
    """
    Static heuristic fallback — used when no AI API key is configured.

    Scans the source for known bad patterns. Always clearly identified as
    fallback mode — NOT a real AI result.
    """
    for pattern, problem, root_cause, evidence_hint, fix in _PATTERNS:
        if re.search(pattern, source_code, re.IGNORECASE):
            # Find the matching line(s) for the evidence field
            evidence_lines = [
                f"  Line {i+1}: {line.rstrip()}"
                for i, line in enumerate(source_code.splitlines())
                if re.search(pattern, line, re.IGNORECASE)
            ]
            evidence = "\n".join(evidence_lines) if evidence_lines else evidence_hint

            return InvestigationResult(
                file=file_path,
                problem=problem,
                root_cause=root_cause,
                evidence=evidence,
                suggested_fix=fix,
                confidence="Medium",
                is_fallback=True,
            )

    # Generic fallback when no pattern matched
    try:
        tree = ast.parse(source_code)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        func_list = ", ".join(funcs[:5]) or "none found"
    except SyntaxError as e:
        return InvestigationResult(
            file=file_path,
            problem=f"Syntax error in file: {e}",
            root_cause="The file could not be parsed — it contains a syntax error.",
            evidence=str(e),
            suggested_fix="Fix the syntax error reported above.",
            confidence="High",
            is_fallback=True,
        )

    hint = f" Bug hint provided: {bug_description}." if bug_description else ""
    return InvestigationResult(
        file=file_path,
        problem=f"No known bug pattern automatically detected.{hint}",
        root_cause=(
            "The static heuristic scanner did not find a matching pattern. "
            "Configure OPENAI_API_KEY to enable full AI-powered investigation."
        ),
        evidence=f"Functions in file: {func_list}",
        suggested_fix=(
            "Review the functions manually or enable AI investigation "
            "by setting OPENAI_API_KEY in your .env file."
        ),
        confidence="Low",
        is_fallback=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def investigate(
    file_path: str,
    source_code: str,
    bug_description: str = "",
) -> InvestigationResult:
    """
    Investigate a Python source file for bugs.

    Tries OpenAI first; falls back to static heuristic analysis if
    OPENAI_API_KEY is not set or the API call fails.

    Parameters
    ----------
    file_path       : relative path of the file (used for labelling only)
    source_code     : full source text of the file
    bug_description : optional free-text hint from the user

    Returns
    -------
    InvestigationResult
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if api_key:
        try:
            return _investigate_with_openai(file_path, source_code, bug_description)
        except Exception as exc:
            # Log and fall through to heuristic fallback
            import traceback
            traceback.print_exc()
            print(f"[ai_service] OpenAI call failed ({exc}); using fallback.")

    return _fallback_investigate(file_path, source_code, bug_description)
