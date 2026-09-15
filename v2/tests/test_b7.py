"""Tests for B7: Make the review page report what actually ran.

Validates:
- Assertion (c): The provenance line is driven entirely by the artifact: editing
  runtime, quantisation or prompt_version in an extraction file changes what renders,
  and deleting a key renders 'unknown'.
- Gold gate percentages on the page equal the fixture's gate_failure_rates exactly to two decimals.
- Footer renders server HEAD commit hash and mtime of every artifact read.
- Falsification: Pointing at the falsification artifact (393 claims, 12 exclusions) renders
  Gate 1 as 2.96%, visibly different from the rubric artifact's 100.0%.
"""

from __future__ import annotations

import json
from pathlib import Path

from v2.src.review import (
    REFERENCE_EPISODE,
    load_episode_data,
    render_review_html,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = ROOT_DIR / "artifacts" / "transcripts"
GOLD_DIR = ROOT_DIR / "fixtures" / "gold"
EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"


def test_assertion_c_provenance_driven_entirely_by_artifact(tmp_path: Path) -> None:
    """Assertion (c) verbatim:

    'the provenance line is driven entirely by the artifact: editing runtime, quantisation
    or prompt_version in an extraction file changes what renders, and deleting a key renders unknown.'
    """
    # Load original rubric artifact
    orig_path = EXTRACTION_DIR / f"rubric_extraction_{REFERENCE_EPISODE}.json"
    with open(orig_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Edit runtime, quantisation, prompt_version, rubric_commit in a copy
    custom_path = tmp_path / "custom_extraction.json"
    data["runtime"] = "ollama"
    data["quantisation"] = "Q4_K_M"
    data["prompt_version"] = "custom_prompt_v2"
    data["rubric_commit"] = "feed123"

    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    loaded = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=tmp_path,
        extraction_file=custom_path,
    )
    assert loaded["model_provenance"]["runtime"] == "ollama"
    assert loaded["model_provenance"]["quantisation"] == "Q4_K_M"
    assert loaded["model_provenance"]["prompt_version"] == "custom_prompt_v2"
    assert loaded["model_provenance"]["rubric_commit"] == "feed123"

    html = render_review_html(loaded)
    assert "ollama" in html
    assert "Q4_K_M" in html
    assert "custom_prompt_v2" in html
    assert "feed123" in html

    # Confirm old constants do not render when overridden
    assert "mlx_lm" not in html
    assert "rubric_prompt_v1" not in html

    # 2. Delete runtime key from copy -> must render 'unknown', not 'mlx_lm'
    del data["runtime"]
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    loaded_del_runtime = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=tmp_path,
        extraction_file=custom_path,
    )
    assert loaded_del_runtime["model_provenance"]["runtime"] is None

    html_del_runtime = render_review_html(loaded_del_runtime)
    assert '<span class="prov-k">Runtime:</span> <span class="prov-v">unknown</span>' in html_del_runtime
    assert "mlx_lm" not in html_del_runtime

    # 3. Delete quantisation, prompt_version, rubric_commit -> all must render 'unknown'
    del data["quantisation"]
    del data["prompt_version"]
    del data["rubric_commit"]
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    loaded_del_all = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=tmp_path,
        extraction_file=custom_path,
    )
    html_del_all = render_review_html(loaded_del_all)
    assert '<span class="prov-k">Quant:</span> <span class="prov-v">unknown</span>' in html_del_all
    assert '<span class="prov-k">Prompt:</span> <span class="prov-v">unknown</span>' in html_del_all
    assert '<span class="prov-k">Rubric Commit:</span> <span class="prov-v font-mono">unknown</span>' in html_del_all
    assert "4-bit" not in html_del_all


def test_gold_gate_percentages_equal_fixture_exact() -> None:
    """Gap 2 & Verify step: Assert in a test that review.py's gold percentages equal

    the fixture's recorded gate_failure_rates to two decimals.
    """
    gold_fixture_path = GOLD_DIR / f"{REFERENCE_EPISODE}.json"
    with open(gold_fixture_path, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    expected_rates = fixture_data["gate_failure_rates"]
    assert expected_rates == {
        "gate_1": 74.57,
        "gate_2": 1.98,
        "gate_3": 1.48,
        "gate_4": 13.83,
    }

    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    actual_gold_pcts = data["gate_distributions"]["gold"]["percentages"]

    for gate, exp_rate in expected_rates.items():
        act_rate = actual_gold_pcts[gate]
        assert act_rate == exp_rate, (
            f"Gate {gate} mismatch: review.py computed {act_rate}%, "
            f"fixture specifies {exp_rate}%"
        )

    # Verify they also render onto the page
    html = render_review_html(data)
    assert "74.57%" in html
    assert "1.98%" in html
    assert "1.48%" in html
    assert "13.83%" in html


def test_footer_renders_head_hash_and_artifact_mtimes() -> None:
    """Gap 3 & Validation: HEAD hash and artifact mtimes render in the footer."""
    data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
    )

    # Artifacts read list
    artifacts_read = data.get("artifacts_read", [])
    assert len(artifacts_read) >= 3  # transcript, gold, extraction
    names = [a["name"] for a in artifacts_read]
    assert f"{REFERENCE_EPISODE}.json" in names
    assert f"rubric_extraction_{REFERENCE_EPISODE}.json" in names
    for a in artifacts_read:
        assert "mtime" in a
        assert len(a["mtime"]) > 0

    # Renders into footer HTML
    test_head = "a1b2c3d"
    html = render_review_html(data, server_head=test_head)

    assert '<footer class="site-footer">' in html
    assert f'Server HEAD: <span class="font-mono">{test_head}</span>' in html
    assert "Artifacts read:" in html
    assert f"{REFERENCE_EPISODE}.json" in html
    assert f"rubric_extraction_{REFERENCE_EPISODE}.json" in html


def test_falsify_gate_percentage_denominator_divergence() -> None:
    """Falsify verbatim:

    'Point the page at the falsification artifact (393 claims, 12 exclusions) and confirm
    its gate percentages differ visibly from the rubric artifact's. If both still render
    gate_1 100%, the denominator is unchanged and nothing has been fixed.'
    """
    rubric_file = EXTRACTION_DIR / f"rubric_extraction_{REFERENCE_EPISODE}.json"
    falsify_file = EXTRACTION_DIR / f"falsification_extraction_{REFERENCE_EPISODE}.json"

    rubric_data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
        extraction_file=rubric_file,
    )

    falsify_data = load_episode_data(
        source_id=REFERENCE_EPISODE,
        transcript_dir=TRANSCRIPT_DIR,
        gold_dir=GOLD_DIR,
        extraction_dir=EXTRACTION_DIR,
        extraction_file=falsify_file,
    )

    rubric_m_pcts = rubric_data["gate_distributions"]["model"]["percentages"]
    falsify_m_pcts = falsify_data["gate_distributions"]["model"]["percentages"]

    # Rubric: 405 exclusions / 405 turns = 100.0%
    assert rubric_m_pcts["gate_1"] == 100.0

    # Falsification: 12 exclusions / 405 turns = 2.96%
    assert falsify_m_pcts["gate_1"] == 2.96

    # Visibly distinct: differ by over 97 percentage points
    assert abs(rubric_m_pcts["gate_1"] - falsify_m_pcts["gate_1"]) > 90.0

    # Test rendered HTML
    rubric_html = render_review_html(rubric_data)
    falsify_html = render_review_html(falsify_data)

    assert "100.0%" in rubric_html
    assert "3.0%" in falsify_html or "2.96%" in falsify_html
    # In falsification HTML, Gate 1 is 12 (3.0%)
    assert "12 <span class='pct'>(3.0%)</span>" in falsify_html
