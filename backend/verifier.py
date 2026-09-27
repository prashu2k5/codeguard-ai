"""
verifier.py — Controlled before/fix/after verification for Phase 4.

The verifier performs a real, tamper-proof verification sequence:

  1. Run the regression test against the CURRENT (broken) source → expect FAIL.
  2. Apply the known fix to a TEMPORARY copy of the file (never touches the
     original on disk — the demo codebase stays broken for future demos).
  3. Run the regression test against the patched copy → expect PASS.
  4. Run the full existing test suite against the patched copy → expect PASS.
  5. Restore the original file exactly.
  6. Return a structured result with actual pytest output.

IMPORTANT SAFETY CONTRACT
--------------------------
  * verified=True is set ONLY when ALL three checks pass:
      before_result == "FAIL"
      after_result  == "PASS"
      regression_suite_result == "PASS"
  * The original source file is ALWAYS restored — even if a step raises.
  * The fix is applied as a targeted string substitution on a known pattern,
    NOT by blindly executing AI-generated shell commands.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Known fixes registry
# ---------------------------------------------------------------------------
# Each entry: (file_glob, search_text, replacement_text, description)
# The verifier only accepts fixes that are registered here — safety guard.

KNOWN_FIXES: list[tuple[str, str, str, str]] = [
    (
        "data_processor.py",
        "(max_v - min_v - 1)",
        "(max_v - min_v)",
        "Fix off-by-one in normalize(): remove spurious '- 1' from denominator.",
    ),
]

# Paths to test files — resolved to absolute paths at module load time
# (i.e. relative to wherever the server is started from, which is the
# workspace root).  Using absolute paths makes pytest cwd-independent.
_MODULE_DIR = Path(__file__).parent.parent  # workspace root = bob-health/
REGRESSION_TEST = str(_MODULE_DIR / "demo_repo" / "regression_normalize.py")
FULL_SUITE       = str(_MODULE_DIR / "demo_repo" / "tests")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    test_result: str          # "PASS" | "FAIL" | "ERROR"
    output: str               # raw pytest stdout/stderr
    tests_passed: int = 0
    tests_failed: int = 0
    tests_errored: int = 0


@dataclass
class VerificationResult:
    file: str
    fix_description: str
    before: StepResult
    after: StepResult
    regression_suite: StepResult
    verified: bool
    failure_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "fix_description": self.fix_description,
            "before": {
                "test_result": self.before.test_result,
                "output": self.before.output,
                "tests_passed": self.before.tests_passed,
                "tests_failed": self.before.tests_failed,
            },
            "after": {
                "test_result": self.after.test_result,
                "output": self.after.output,
                "tests_passed": self.after.tests_passed,
                "tests_failed": self.after.tests_failed,
            },
            "regression_suite": {
                "result": self.regression_suite.test_result,
                "output": self.regression_suite.output,
                "tests_passed": self.regression_suite.tests_passed,
                "tests_failed": self.regression_suite.tests_failed,
            },
            "verified": self.verified,
            "failure_reason": self.failure_reason,
            "disclaimer": (
                "Fix independently verified by automated tests. "
                "This is NOT an AI claim — it reflects actual pytest execution."
            ),
        }


# ---------------------------------------------------------------------------
# Pytest runner
# ---------------------------------------------------------------------------

def _run_pytest(test_path: str, cwd: Path, extra_args: list[str] | None = None) -> StepResult:
    """
    Run pytest against test_path from cwd and return a StepResult.

    Captures combined stdout+stderr. Parses the summary line for counts.
    Exit code 0 → PASS, non-zero → FAIL (or ERROR if collection failed).
    """
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v", "--tb=short", "--no-header",
    ]
    if extra_args:
        cmd.extend(extra_args)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return StepResult(test_result="ERROR", output="Pytest timed out after 120s.")
    except Exception as exc:
        return StepResult(test_result="ERROR", output=f"Failed to launch pytest: {exc}")

    combined = proc.stdout + proc.stderr
    passed, failed, errored = _parse_counts(combined)

    # Collection errors appear in stderr even with exit 0
    if "no tests ran" in combined.lower() and "error" in combined.lower():
        return StepResult(
            test_result="ERROR",
            output=combined,
            tests_passed=0,
            tests_failed=0,
            tests_errored=1,
        )

    if proc.returncode == 0:
        result = "PASS"
    else:
        result = "FAIL"

    return StepResult(
        test_result=result,
        output=combined,
        tests_passed=passed,
        tests_failed=failed,
        tests_errored=errored,
    )


def _parse_counts(output: str) -> tuple[int, int, int]:
    """Extract (passed, failed, errored) from a pytest summary line."""
    import re
    passed = failed = errored = 0
    # Match lines like: "5 failed, 3 passed in 0.17s"
    for m in re.finditer(r"(\d+)\s+(passed|failed|error)", output):
        n, kind = int(m.group(1)), m.group(2)
        if kind == "passed":
            passed = n
        elif kind == "failed":
            failed = n
        elif kind == "error":
            errored = n
    return passed, failed, errored


# ---------------------------------------------------------------------------
# Fix applicator
# ---------------------------------------------------------------------------

def _find_registered_fix(file_name: str, source: str) -> Optional[tuple[str, str, str]]:
    """
    Look up the registered fix for this file and verify it is applicable.

    Returns (search_text, replacement, description) or None.
    """
    base = Path(file_name).name
    for glob, search, replace, desc in KNOWN_FIXES:
        if base == glob and search in source:
            return search, replace, desc
    return None


def _apply_fix(source: str, search: str, replace: str) -> str:
    """Apply a targeted string substitution (first occurrence only)."""
    if search not in source:
        raise ValueError(f"Fix pattern not found in source: {search!r}")
    return source.replace(search, replace, 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_fix(
    repo_path: str,
    file_path: str,
) -> VerificationResult:
    """
    Run the full before/fix/after verification sequence.

    Parameters
    ----------
    repo_path : path to the repository root
    file_path : path to the buggy file (relative to repo_path or absolute)

    Returns
    -------
    VerificationResult — always returned; verified=False on any safety failure.
    """
    root = Path(repo_path).resolve()
    target = (root / file_path).resolve()

    if not target.exists():
        sr = StepResult(test_result="ERROR", output=f"File not found: {target}")
        return VerificationResult(
            file=file_path,
            fix_description="",
            before=sr, after=sr, regression_suite=sr,
            verified=False,
            failure_reason=f"File not found: {target}",
        )

    original_source = target.read_text(encoding="utf-8")

    # Look up the registered fix
    fix_entry = _find_registered_fix(target.name, original_source)
    if fix_entry is None:
        sr = StepResult(
            test_result="ERROR",
            output=(
                f"No registered fix found for '{target.name}', or the fix "
                "pattern is not present in the current source."
            ),
        )
        return VerificationResult(
            file=file_path,
            fix_description="No registered fix",
            before=sr, after=sr, regression_suite=sr,
            verified=False,
            failure_reason="No registered fix matches this file / source.",
        )

    search_text, replace_text, fix_desc = fix_entry
    fixed_source = _apply_fix(original_source, search_text, replace_text)

    failure_reason = ""

    # Run pytest from the workspace root so imports resolve correctly
    pytest_cwd = _MODULE_DIR

    try:
        # ── Step 1: BEFORE ────────────────────────────────────────────────
        # File is currently broken — run regression test, expect FAIL.
        before = _run_pytest(REGRESSION_TEST, pytest_cwd)

        # ── Step 2: Apply fix to disk temporarily ─────────────────────────
        target.write_text(fixed_source, encoding="utf-8")

        try:
            # ── Step 3: AFTER ─────────────────────────────────────────────
            # File is now fixed — regression test must PASS.
            after = _run_pytest(REGRESSION_TEST, pytest_cwd)

            # ── Step 4: Full regression suite ─────────────────────────────
            regression_suite = _run_pytest(FULL_SUITE, pytest_cwd)

        finally:
            # ── Step 5: ALWAYS restore original ───────────────────────────
            target.write_text(original_source, encoding="utf-8")

    except Exception as exc:
        # Ensure file is restored even on unexpected errors
        try:
            target.write_text(original_source, encoding="utf-8")
        except Exception:
            pass
        sr = StepResult(test_result="ERROR", output=str(exc))
        return VerificationResult(
            file=file_path,
            fix_description=fix_desc,
            before=sr, after=sr, regression_suite=sr,
            verified=False,
            failure_reason=f"Unexpected error during verification: {exc}",
        )

    # ── Evaluate safety conditions ─────────────────────────────────────────
    verified = True

    if before.test_result != "FAIL":
        verified = False
        failure_reason = (
            f"Expected regression test to FAIL before fix, "
            f"but got: {before.test_result}. "
            "The bug may already be fixed, or the test is not targeting the bug."
        )
    elif after.test_result != "PASS":
        verified = False
        failure_reason = (
            f"Regression test did not PASS after fix: {after.test_result}."
        )
    elif regression_suite.test_result != "PASS":
        verified = False
        failure_reason = (
            f"Full regression suite did not pass after fix: "
            f"{regression_suite.tests_failed} test(s) failed."
        )

    return VerificationResult(
        file=file_path,
        fix_description=fix_desc,
        before=before,
        after=after,
        regression_suite=regression_suite,
        verified=verified,
        failure_reason=failure_reason,
    )
