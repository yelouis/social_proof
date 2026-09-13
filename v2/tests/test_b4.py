"""Tests for Item B4: Measure, and decide whether to go on.

Verifies:
1. Blind scoring falsification test runs and achieves >= 80% agreement.
2. Issue 036 exists in v2/docs/ongoing_errors.md §1 with blank 'Your selection: _____'.
3. No scaling beyond episode 00251a80c868f535 occurred.
"""

from __future__ import annotations

import json
from pathlib import Path

from v2.src.evaluate_blind_b4 import run_blind_scoring

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_blind_scoring_falsification() -> None:
    """Falsification test: blind scoring of 20 turns demonstrates >= 80% agreement."""
    res = run_blind_scoring(seed=42)
    assert res["total_blind_items"] == 20
    assert res["agreement_rate"] >= 80.0, f"Blind agreement too low: {res['agreement_rate']}%"


def test_ongoing_errors_issue_036_filed_correctly() -> None:
    """Verifies that Issue 036 is filed in v2/docs/ongoing_errors.md with an unselected line."""
    ongoing_errors_path = ROOT_DIR / "docs" / "ongoing_errors.md"
    assert ongoing_errors_path.exists(), "ongoing_errors.md does not exist"

    content = ongoing_errors_path.read_text(encoding="utf-8")
    assert "### Issue 036" in content
    assert "Your selection: _____" in content
    # Standing constraint: Never fill in a 'Your selection: _____' line
    assert "Your selection: A" not in content
    assert "Your selection: B" not in content
    assert "Your selection: C" not in content


def test_no_premature_scaling() -> None:
    """Validation: extraction artifacts only exist for reference episode 00251a80c868f535."""
    extraction_dir = ROOT_DIR / "artifacts" / "extraction"
    assert extraction_dir.exists()
    extraction_files = list(extraction_dir.glob("*.json"))
    for f in extraction_files:
        assert "00251a80c868f535" in f.name, f"Unexpected scaled episode artifact: {f.name}"
