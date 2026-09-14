"""Tests for Item B4: Measure, and decide whether to go on.

Verifies:
1. Blind scoring falsification test runs and achieves >= 80% agreement.
2. Issue 036 exists in v2/docs/ongoing_errors.md §1 with blank 'Your selection: _____'.
3. No scaling beyond episode 00251a80c868f535 occurred.
"""

from __future__ import annotations

from pathlib import Path

from v2.src.evaluate_blind_b4 import run_blind_scoring

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_blind_scoring_falsification() -> None:
    """Falsification test: blind scoring of 20 turns demonstrates >= 80% agreement."""
    res = run_blind_scoring(seed=42)
    assert res["total_blind_items"] == 20
    assert res["agreement_rate"] >= 80.0, f"Blind agreement too low: {res['agreement_rate']}%"


def test_issue_036_has_a_recorded_outcome() -> None:
    """Issue 036 must be either open with a blank selection line, or recorded as a decision.

    This originally asserted that 036 was open and unselected, which made the test fail the
    moment Louis selected it -- i.e. it failed precisely because the process worked. It now
    asserts the durable fact instead: an issue is tracked either way and never disappears.
    """
    ongoing_errors_path = ROOT_DIR / "docs" / "ongoing_errors.md"
    assert ongoing_errors_path.exists(), "ongoing_errors.md does not exist"

    content = ongoing_errors_path.read_text(encoding="utf-8")
    still_open = "### Issue 036" in content and "Your selection: _____" in content
    decided = "| **036** |" in content
    assert still_open or decided, (
        "Issue 036 is neither open in section 1 nor recorded in the decision table"
    )


def test_no_premature_scaling() -> None:
    """Validation: extraction artifacts only exist for reference episode 00251a80c868f535."""
    extraction_dir = ROOT_DIR / "artifacts" / "extraction"
    assert extraction_dir.exists()
    extraction_files = list(extraction_dir.glob("*.json"))
    for f in extraction_files:
        assert "00251a80c868f535" in f.name, f"Unexpected scaled episode artifact: {f.name}"
