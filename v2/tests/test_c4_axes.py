"""Tests for Item C4: Score every candidate on the eight axes, and report the episode.

Verifies:
1. score_axes.md prompt template exists, substitutes placeholders, and loads live from Markdown.
2. Step 1 Verify: Changing one anchor word in design_claim_axes.md changes the sent prompt.
3. Pass 1 prompt hash remains unchanged (503a35f05563); Pass 2 prompt hash is recorded.
4. Step 2 Verify: scoring_model_id is present and strictly distinct from model_id.
5. Step 3 & Assertion (c): Mechanical proxies match exact E287 measured counts:
   - Unresolved referents: 6 of 111 (5.4%) on known turns (t0010, t0072, t0111, t0172, t0238, t0359).
   - Compound claims > 35 words: 3 of 111 (2.7%) on known turns (t0016, t0255, t0389).
   - Near-verbatim quotes: 39 of 111 (35.1%).
6. Parse axes verdict handles clean JSON and marks unparseable/out-of-range output.
7. Step 4 Verify: Episode report separates Speaker and Extraction panels; NO composite scalar score.
8. Every 0-score is resolvable by turn id.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from v2.src.extract import (
    DEFAULT_AXES_PATH,
    DEFAULT_EXTRACTION_DIR,
    DEFAULT_PROMPT_CLAIM_PATH,
    DEFAULT_PROMPT_SCORE_AXES_PATH,
    EXTRACTION_PANEL_AXES,
    SPEAKER_PANEL_AXES,
    build_score_axes_prompt,
    compute_mechanical_proxies,
    generate_episode_axes_report,
    load_axes,
    load_prompt_template,
    parse_axes_verdict,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_score_axes_prompt_template_exists_and_substitutes() -> None:
    """v2/prompts/score_axes.md must exist and declare required placeholders."""
    assert DEFAULT_PROMPT_SCORE_AXES_PATH.exists(), f"Missing {DEFAULT_PROMPT_SCORE_AXES_PATH}"

    template = load_prompt_template(DEFAULT_PROMPT_SCORE_AXES_PATH)
    for placeholder in ["{axes}", "{turn_id}", "{speaker}", "{turn_text}", "{quote}", "{claim}"]:
        assert placeholder in template, f"Missing placeholder {placeholder} in {DEFAULT_PROMPT_SCORE_AXES_PATH}"

    target_turn = {
        "turn_id": "test_t001",
        "speaker_label": "David Friedberg",
        "text": "Much of academic science enforces conformity.",
    }
    quote = "academic science enforces conformity"
    claim = "Academic science enforces conformity around mainstream theories."
    axes_text = "MOCK_AXES_RUBRIC_SPECIFICATION"

    built = build_score_axes_prompt(
        axes_text=axes_text,
        target_turn=target_turn,
        quote=quote,
        claim=claim,
    )

    assert "MOCK_AXES_RUBRIC_SPECIFICATION" in built
    assert "test_t001" in built
    assert "David Friedberg" in built
    assert "Much of academic science enforces conformity." in built
    assert quote in built
    assert claim in built


def test_step1_verify_axes_anchor_change_changes_sent_prompt(tmp_path: Path) -> None:
    """Step 1 Verify: Changing one anchor word in design_claim_axes.md changes the sent prompt.

    Guarantees that prompt loading is live from Markdown and not overridden/hardcoded in Python.
    """
    original_axes = load_axes(DEFAULT_AXES_PATH)
    assert "epistemic commitment" in original_axes.lower()

    # Create mutated axes text with one modified anchor word
    mutated_axes = original_axes.replace("epistemic commitment", "NOVEL_UNIQUE_ANCHOR_WORD")
    assert "NOVEL_UNIQUE_ANCHOR_WORD" in mutated_axes

    mutated_axes_file = tmp_path / "design_claim_axes_mutated.md"
    mutated_axes_file.write_text(mutated_axes, encoding="utf-8")

    turn = {"turn_id": "t_verify", "speaker_label": "Jason", "text": "Some text"}
    prompt_orig = build_score_axes_prompt(
        axes_text=load_axes(DEFAULT_AXES_PATH),
        target_turn=turn,
        quote="quote",
        claim="claim",
    )
    prompt_mutated = build_score_axes_prompt(
        axes_text=load_axes(mutated_axes_file),
        target_turn=turn,
        quote="quote",
        claim="claim",
    )

    assert prompt_orig != prompt_mutated
    assert "NOVEL_UNIQUE_ANCHOR_WORD" in prompt_mutated
    assert "NOVEL_UNIQUE_ANCHOR_WORD" not in prompt_orig


def test_pass1_prompt_hash_unchanged_and_pass2_recorded() -> None:
    """Pass 1 prompt hash must remain pinned to 503a35f05563 (C3 fix); Pass 2 hash recorded."""
    pass1_content = DEFAULT_PROMPT_CLAIM_PATH.read_text(encoding="utf-8")
    pass1_hash = hashlib.sha256(pass1_content.encode("utf-8")).hexdigest()
    assert pass1_hash[:12] == "503a35f05563", f"Pass 1 prompt hash modified: {pass1_hash[:12]}"

    pass2_content = DEFAULT_PROMPT_SCORE_AXES_PATH.read_text(encoding="utf-8")
    pass2_hash = hashlib.sha256(pass2_content.encode("utf-8")).hexdigest()
    assert len(pass2_hash) == 64
    assert pass2_hash[:12] != pass1_hash[:12]


def test_step2_verify_scoring_model_id_distinct_from_model_id() -> None:
    """Step 2 Verify: scoring_model_id must differ from model_id (independent scoring model)."""
    extractor_model = "mlx-community/gemma-4-31b-it-4bit"
    scoring_model = "mlx-community/GLM-4-32B-0414-4bit"

    # Must pass when distinct
    report = generate_episode_axes_report(
        scored_claims=[],
        total_turns=405,
        model_id=extractor_model,
        scoring_model_id=scoring_model,
    )
    assert report["provenance"]["model_id"] == extractor_model
    assert report["provenance"]["scoring_model_id"] == scoring_model
    assert report["provenance"]["model_id"] != report["provenance"]["scoring_model_id"]

    # Must raise when identical (self-assessment prohibited on Extraction panel)
    with pytest.raises(ValueError, match="independent model distinct from the extractor"):
        generate_episode_axes_report(
            scored_claims=[],
            total_turns=405,
            model_id=extractor_model,
            scoring_model_id=extractor_model,
        )


def test_mechanical_proxies_exact_e287_counts() -> None:
    """Step 3 & Assertion (c): Verify exact counts of the 3 mechanical proxies on E287's 111 claims:

    - Unresolved referents: 6 of 111 (5.4%) (t0010, t0072, t0111, t0172, t0238, t0359).
    - Compound claims > 35 words: 3 of 111 (2.7%) (t0016, t0255, t0389).
    - Near-verbatim quotes: 39 of 111 (35.1%).
    """
    gemma_b6_file = DEFAULT_EXTRACTION_DIR / "b6_extraction_mlx-community_gemma-4-31b-it-4bit_00251a80c868f535.json"
    assert gemma_b6_file.exists(), f"Missing Gemma B6 artifact: {gemma_b6_file}"

    with open(gemma_b6_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    claims = [v for v in data["verdicts"] if v.get("verdict") == "claim"]
    assert len(claims) == 111, f"Expected 111 claims from Gemma-4-31B, got {len(claims)}"

    proxies = compute_mechanical_proxies(claims)
    assert proxies["total_claims"] == 111

    # 1. Unresolved referents
    ref_res = proxies["unresolved_referents"]
    assert ref_res["count"] == 6, f"Expected 6 unresolved referents, got {ref_res['count']}"
    assert ref_res["rate_pct"] == 5.4
    expected_ref_tids = {
        "00251a80c868f535_t0010",
        "00251a80c868f535_t0072",
        "00251a80c868f535_t0111",
        "00251a80c868f535_t0172",
        "00251a80c868f535_t0238",
        "00251a80c868f535_t0359",
    }
    assert set(ref_res["turn_ids"]) == expected_ref_tids

    # 2. Compound claims > 35 words
    comp_res = proxies["compound_claims"]
    assert comp_res["count"] == 3, f"Expected 3 compound claims > 35w, got {comp_res['count']}"
    assert comp_res["rate_pct"] == 2.7
    expected_comp_tids = {
        "00251a80c868f535_t0016",
        "00251a80c868f535_t0255",
        "00251a80c868f535_t0389",
    }
    assert set(comp_res["turn_ids"]) == expected_comp_tids

    # 3. Near-verbatim quotes
    verb_res = proxies["near_verbatim_quotes"]
    assert verb_res["count"] == 39, f"Expected 39 near-verbatim quotes, got {verb_res['count']}"
    assert verb_res["rate_pct"] == 35.1


def test_parse_axes_verdict_valid_and_unparseable() -> None:
    """Verify parse_axes_verdict correctly parses 8 integer axes and rejects malformed outputs."""
    valid_raw = """
    ```json
    {
      "turn_id": "test_t001",
      "voice": 2,
      "voice_reason": "Asserted directly in own voice.",
      "target": 2,
      "target_reason": "About the tech industry.",
      "propositionality": 2,
      "propositionality_reason": "Clear predicate.",
      "contestability": 1,
      "contestability_reason": "Mildly contestable.",
      "typing": 2,
      "typing_reason": "Position.",
      "decontextualisation": 2,
      "decontextualisation_reason": "Fully resolved.",
      "fidelity": 2,
      "fidelity_reason": "Strictly entailed.",
      "granularity": 2,
      "granularity_reason": "Atomic claim."
    }
    ```
    """
    parsed = parse_axes_verdict(valid_raw, "test_t001")
    assert parsed["parse_status"] == "ok"
    assert parsed["scores"]["voice"] == 2
    assert parsed["scores"]["contestability"] == 1
    assert len(parsed["scores"]) == 8
    assert len(parsed["reasons"]) == 8

    # Missing an axis
    missing_raw = """{"voice": 2, "target": 2}"""
    parsed_missing = parse_axes_verdict(missing_raw, "test_t001")
    assert parsed_missing["parse_status"] == "unparseable"

    # Out of range integer (3 instead of 0, 1, 2)
    invalid_range_raw = valid_raw.replace('"voice": 2', '"voice": 3')
    parsed_range = parse_axes_verdict(invalid_range_raw, "test_t001")
    assert parsed_range["parse_status"] == "unparseable"

    # Non-json text
    parsed_text = parse_axes_verdict("This is not json", "test_t001")
    assert parsed_text["parse_status"] == "unparseable"


def test_step4_verify_no_composite_score_and_separate_panels() -> None:
    """Step 4 Verify: Speaker panel and Extraction panel reported separately; NO composite scalar score."""
    mock_scored = [
        {
            "turn_id": "t01",
            "scores": {
                "voice": 2,
                "target": 2,
                "propositionality": 2,
                "contestability": 2,
                "typing": 2,
                "decontextualisation": 0,
                "fidelity": 2,
                "granularity": 2,
            },
        },
        {
            "turn_id": "t02",
            "scores": {
                "voice": 1,
                "target": 2,
                "propositionality": 1,
                "contestability": 1,
                "typing": 1,
                "decontextualisation": 2,
                "fidelity": 1,
                "granularity": 1,
            },
        },
    ]

    report = generate_episode_axes_report(
        scored_claims=mock_scored,
        total_turns=10,
        model_id="mlx-community/gemma-4-31b-it-4bit",
        scoring_model_id="mlx-community/GLM-4-32B-0414-4bit",
    )

    # Separation of panels
    assert "speaker_panel" in report
    assert "extraction_panel" in report
    assert set(report["speaker_panel"].keys()) == set(SPEAKER_PANEL_AXES)
    assert set(report["extraction_panel"].keys()) == set(EXTRACTION_PANEL_AXES)

    # NO composite scalar score
    assert "composite_score" not in report
    assert "composite_quality" not in report
    assert "quality_score" not in report

    # Every 0-score resolvable by turn id
    decontext_zeros = report["extraction_panel"]["decontextualisation"]["zero_scores_turn_ids"]
    assert decontext_zeros == ["t01"]


def test_step5_verify_review_page_renders_quality_profile() -> None:
    """Step 5 Verify: review page renders quality profile with density, 8 axes, proxies, and provenance."""
    from v2.src.review import render_review_html

    mock_report = {
        "episode": {
            "source_id": "00251a80c868f535",
            "total_turns": 405,
            "claims_found": 111,
            "density_pct": 27.4,
        },
        "speaker_panel": {
            ax: {
                "axis": ax,
                "mean": 1.8,
                "counts": {"0": 2, "1": 15, "2": 94},
                "percentages": {"0": 1.8, "1": 13.5, "2": 84.7},
                "zero_scores_count": 2,
                "zero_scores_turn_ids": ["00251a80c868f535_t0022", "00251a80c868f535_t0050"],
                "has_zero_variance": False,
            }
            for ax in ["voice", "target", "propositionality", "contestability", "typing"]
        },
        "extraction_panel": {
            ax: {
                "axis": ax,
                "mean": 1.9,
                "counts": {"0": 6, "1": 5, "2": 100},
                "percentages": {"0": 5.4, "1": 4.5, "2": 90.1},
                "zero_scores_count": 6,
                "zero_scores_turn_ids": ["00251a80c868f535_t0010"],
                "has_zero_variance": False,
            }
            for ax in ["decontextualisation", "fidelity", "granularity"]
        },
        "cross_checks": {
            "decontextualisation": {
                "proxy_unresolved_referents_count": 6,
                "overlap_count": 6,
                "overlap_rate_pct": 100.0,
            },
            "granularity": {
                "proxy_compound_claims_count": 3,
                "overlap_count": 3,
                "overlap_rate_pct": 100.0,
            },
            "fidelity": {
                "near_verbatim_quotes_count": 39,
            },
        },
        "provenance": {
            "model_id": "mlx-community/gemma-4-31b-it-4bit",
            "scoring_model_id": "mlx-community/GLM-4-32B-0414-4bit",
            "rubric_commit": "c4deadbeef01",
            "axes_commit": "c4axesfeed02",
        },
    }

    mock_turn = {
        "turn_id": "00251a80c868f535_t0007",
        "index": 7,
        "speaker_label": "Jason Calacanis",
        "timestamp_str": "00:01:23 - 00:01:30",
        "text": "He is a heterodox thinker in science",
        "model_verdict": "claim",
        "model_claim": "Eric Weinstein is a heterodox thinker in science",
        "model_quote": "He is a heterodox thinker in science",
        "model_type": "position",
        "axes_scores": {
            "voice": 1,
            "target": 2,
            "propositionality": 2,
            "contestability": 1,
            "typing": 2,
            "decontextualisation": 0,
            "fidelity": 2,
            "granularity": 2,
        },
        "axes_reasons": {
            "voice_reason": "Distanced by pronoun",
            "decontextualisation_reason": "Unresolved referent He",
        },
    }

    page_data = {
        "source_id": "00251a80c868f535",
        "title": "All-In Podcast E287",
        "turns": [mock_turn],
        "has_gold": False,
        "has_extraction": True,
        "has_scored_axes": True,
        "axes_report": mock_report,
        "model_provenance": {
            "model_id": "mlx-community/gemma-4-31b-it-4bit",
            "scoring_model_id": "mlx-community/GLM-4-32B-0414-4bit",
            "quantisation": "4bit",
            "runtime": "mlx_lm",
            "prompt_version": "b3_gemma",
            "rubric_commit": "c4deadbeef01",
            "axes_commit": "c4axesfeed02",
        },
    }

    rendered_html = render_review_html(page_data)

    # Verify Quality Profile Card rendered
    assert "claim-quality-profile" in rendered_html
    assert "Claim Quality Across Eight Axes" in rendered_html

    # Density headline: 111 claims (27.4% of 405 turns)
    assert "111" in rendered_html
    assert "27.4%" in rendered_html

    # 8 axis rows present
    for ax in ["voice", "target", "propositionality", "contestability", "typing", "decontextualisation", "fidelity", "granularity"]:
        assert ax.capitalize() in rendered_html

    # 0-scores listed with clickable turn ids
    assert "#00251a80c868f535_t0010" in rendered_html
    assert "#00251a80c868f535_t0022" in rendered_html

    # Mechanical proxy cross-checks
    assert "Unresolved referents:" in rendered_html
    assert "6 of 111" in rendered_html
    assert "Compound claims &gt; 35w:" in rendered_html
    assert "3 of 111" in rendered_html
    assert "Near-verbatim quotes:" in rendered_html
    assert "39 of 111" in rendered_html

    # Provenance banner shows both models
    assert "gemma-4-31b-it-4bit" in rendered_html
    assert "GLM-4-32B-0414-4bit" in rendered_html
    assert "Scoring Model:" in rendered_html
    assert "Axes Commit:" in rendered_html

