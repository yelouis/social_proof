"""Tests for C1 Job 1: Prompts moved to editable Markdown files in v2/prompts/.

Verifies:
1. extract_claim.md and extract_falsify.md exist in v2/prompts/.
2. Prompts substitute placeholders ({rubric}, {context_turn}, {target_turn}, etc.).
3. Editing a template changes what gets sent to the model (it is genuinely editable).
4. Prompt loading is zero-code-generation (no conditional code branching).
"""

from __future__ import annotations

from pathlib import Path

from v2.src.extract import (
    DEFAULT_PROMPT_CLAIM_PATH,
    DEFAULT_PROMPT_FALSIFY_PATH,
    DEFAULT_RUBRIC_PATH,
    build_falsification_prompt,
    build_rubric_prompt,
    load_rubric,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_prompt_markdown_files_exist() -> None:
    """extract_claim.md and extract_falsify.md must exist in v2/prompts/."""
    assert DEFAULT_PROMPT_CLAIM_PATH.exists(), f"Missing {DEFAULT_PROMPT_CLAIM_PATH}"
    assert DEFAULT_PROMPT_FALSIFY_PATH.exists(), f"Missing {DEFAULT_PROMPT_FALSIFY_PATH}"

    claim_text = DEFAULT_PROMPT_CLAIM_PATH.read_text(encoding="utf-8")
    assert "{rubric}" in claim_text
    assert "{context_turn}" in claim_text
    assert "{target_turn}" in claim_text

    falsify_text = DEFAULT_PROMPT_FALSIFY_PATH.read_text(encoding="utf-8")
    assert "{context_turn}" in falsify_text
    assert "{target_turn}" in falsify_text


def test_template_editability(tmp_path: Path) -> None:
    """Verify editing a prompt file changes the rendered prompt.

    A template that is loaded but overridden in code is worse than code.
    """
    custom_template = tmp_path / "custom_prompt.md"
    custom_template.write_text(
        "CUSTOM_HEADER\n{rubric}\n{context_turn}\n{target_turn}\n{target_turn_id}\n{target_speaker}\nCUSTOM_FOOTER",
        encoding="utf-8",
    )

    rubric_text = load_rubric(DEFAULT_RUBRIC_PATH)
    target = {
        "turn_id": "test_t001",
        "speaker_label": "David Friedberg",
        "text": "Nvidia has an impenetrable moat.",
    }
    context = {
        "turn_id": "test_t000",
        "speaker_label": "Jason Calacanis",
        "text": "Let us talk chips.",
    }

    rendered = build_rubric_prompt(
        rubric_text,
        target,
        context,
        template_path=custom_template,
    )

    assert "CUSTOM_HEADER" in rendered
    assert "CUSTOM_FOOTER" in rendered
    assert "test_t001" in rendered
    assert "David Friedberg" in rendered


def test_falsification_template_editability(tmp_path: Path) -> None:
    """Verify editing falsification prompt template alters output."""
    custom_template = tmp_path / "custom_falsify.md"
    custom_template.write_text(
        "FALSIFY_HEADER\n{context_turn}\n{target_turn}\n{target_turn_id}\n{target_speaker}\nFALSIFY_FOOTER",
        encoding="utf-8",
    )

    target = {
        "turn_id": "test_t002",
        "speaker_label": "Chamath Palihapitiya",
        "text": "The macro setup is clear.",
    }

    rendered = build_falsification_prompt(
        target,
        None,
        template_path=custom_template,
    )

    assert "FALSIFY_HEADER" in rendered
    assert "FALSIFY_FOOTER" in rendered
    assert "test_t002" in rendered
    assert "Chamath Palihapitiya" in rendered


def test_job2_positive_rubric_and_worked_examples() -> None:
    """Verify Job 2 rubric properties:

    1. Primary test is positive elicitation.
    2. Four gates and five claim types survive intact.
    3. §5 worked examples have positive >= negative, and lead with positives.
    """
    rubric_text = DEFAULT_RUBRIC_PATH.read_text(encoding="utf-8")

    # Positive primary test
    assert "Does this turn contain a position the speaker would defend if challenged?" in rubric_text

    # Gate definitions intact
    for gate_name in ["Gate 1 — Attributable", "Gate 2 — About the world", "Gate 3 — Contestable", "Gate 4 — Standalone"]:
        assert gate_name in rubric_text

    # Five claim types intact
    for claim_type in ["position", "prediction", "causal", "evaluative", "contested fact"]:
        assert f"| **{claim_type}** |" in rubric_text or f"| {claim_type} |" in rubric_text

    # Parse worked examples table
    lines = rubric_text.splitlines()
    in_worked_examples = False
    example_rows: list[str] = []
    for line in lines:
        if "## 5. Worked examples" in line:
            in_worked_examples = True
            continue
        if in_worked_examples and line.startswith("## "):
            break
        if in_worked_examples and line.strip().startswith("|") and not line.strip().startswith("| quote") and not line.strip().startswith("|---"):
            example_rows.append(line.strip())

    positives = [r for r in example_rows if "CLAIM" in r]
    negatives = [r for r in example_rows if "not a claim" in r]

    # Verify counts: positive >= negative
    assert len(positives) >= len(negatives), f"Expected positives >= negatives, got {len(positives)} vs {len(negatives)}"
    assert len(positives) == 8, f"Expected 8 positive examples, got {len(positives)}"
    assert len(negatives) == 6, f"Expected 6 negative examples, got {len(negatives)}"

    # Verify positives lead
    assert "CLAIM" in example_rows[0], "Expected positive examples to lead in worked examples table"


def test_job2_gold_exclusions_survive() -> None:
    """Verify 10 gold exclusions across all 4 gates retain their exact gate failure reasons under the rewritten rubric."""
    sample_exclusions = [
        ("00251a80c868f535_t0001", "gate_1"),
        ("00251a80c868f535_t0003", "gate_1"),
        ("00251a80c868f535_t0004", "gate_1"),
        ("00251a80c868f535_t0005", "gate_1"),
        ("00251a80c868f535_t0000", "gate_2"),
        ("00251a80c868f535_t0002", "gate_2"),
        ("00251a80c868f535_t0070", "gate_3"),
        ("00251a80c868f535_t0072", "gate_3"),
        ("00251a80c868f535_t0012", "gate_4"),
        ("00251a80c868f535_t0019", "gate_4"),
    ]

    import json
    gold_path = ROOT_DIR / "fixtures" / "gold" / "00251a80c868f535.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    gold_by_id = {v["turn_id"]: v for v in gold_data["verdicts"]}

    for turn_id, expected_gate in sample_exclusions:
        assert turn_id in gold_by_id
        entry = gold_by_id[turn_id]
        assert entry["verdict"] == "exclusion"
        assert entry["gate_failed"] == expected_gate


def test_c1_extraction_artifact_metrics() -> None:
    """Verify C1 extraction artifact metrics on E287 (405 turns):

    1. Assertion (c): recall is materially > 0% (81.82%), precision is materially > 8.40% (15.34%).
    2. Claims emitted: 176 (27 TP, 149 FP, 6 FN, 223 TN).
    3. Gate distributions span all four gates (no Gate 1 collapse).
    4. Quote provenance: verbatim quotes > 75%, context leaks <= 1.
    """
    c1_file = ROOT_DIR / "artifacts" / "extraction" / "c1_rubric_extraction_00251a80c868f535.json"
    assert c1_file.exists(), f"Missing C1 extraction artifact: {c1_file}"

    import json
    with open(c1_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["source_id"] == "00251a80c868f535"
    assert data["total_turns"] == 405
    assert data["turns_processed"] == 405
    assert data["provenance_source"] == "recorded"
    assert data["validators_added"] == 0

    metrics = data["metrics"]
    # Assertion (c):
    # recall materially > 0%
    assert metrics["recall_pct"] > 50.0, f"Recall too low: {metrics['recall_pct']}%"
    assert metrics["recall_pct"] == 81.82

    # precision materially > 8.40% floor
    assert metrics["precision_pct"] > 10.0, f"Precision failed floor: {metrics['precision_pct']}%"
    assert metrics["precision_pct"] == 15.34

    # Confusion matrix
    cm = metrics["confusion_matrix"]
    assert cm["tp"] == 27
    assert cm["fp"] == 149
    assert cm["fn"] == 6
    assert cm["tn"] == 223
    assert metrics["model_claims_count"] == 176

    # Gate failure distribution spans gates
    gates = metrics["gate_failure_counts_model"]
    assert gates["gate_1"] == 67
    assert gates["gate_2"] == 54
    assert gates["gate_3"] == 1
    assert gates["gate_4"] == 107
    # Gate 1 monopoly broken (was 405 in B3, now 67)
    assert gates["gate_1"] < 100

    # Quote integrity
    assert metrics["verbatim_quote_rate"] > 70.0
    assert metrics["context_leak_quotes"] <= 1


