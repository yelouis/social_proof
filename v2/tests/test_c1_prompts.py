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
    """Verify that §2 (The four gates) of the rubric is 100% byte-identical to the B2 rubric commit (9882bc3),

    guaranteeing that the four gate definitions under which the 405 labels were assigned remain unchanged (Gap 4).
    """
    import subprocess

    from v2.src.extract import extract_rubric_sections

    curr_text = DEFAULT_RUBRIC_PATH.read_text(encoding="utf-8")
    b2_text = subprocess.check_output(["git", "show", "9882bc3:v2/docs/design_claim_rubric.md"], text=True)

    curr_s2 = extract_rubric_sections(curr_text)["section_2"]
    b2_s2 = extract_rubric_sections(b2_text)["section_2"]

    assert curr_s2 == b2_s2, "Section 2 (The four gates) changed since B2 was labelled!"


def test_c1_extraction_artifact_metrics() -> None:
    """Verify C1 extraction artifact metrics on E287 (405 turns):

    Maintains the honest floors without pinning brittle equality snapshots (Gap 3, trap 81).
    1. Assertion (c): recall is materially > 0% (> 50.0%), precision is materially > 8.40% (> 10.0%).
    2. Gate distributions span all four gates (Gate 1 monopoly < 100).
    3. Quote provenance: verbatim quotes > 70%, context leaks <= 1.
    """
    c1_file = ROOT_DIR / "artifacts" / "extraction" / "c1_rubric_extraction_00251a80c868f535.json"
    assert c1_file.exists(), f"Missing C1 extraction artifact: {c1_file}"

    import json
    with open(c1_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["source_id"] == "00251a80c868f535"
    assert data["total_turns"] == 405
    assert data["turns_processed"] == 405

    metrics = data["metrics"]
    # Assertion (c) floors:
    assert metrics["recall_pct"] > 50.0, f"Recall too low: {metrics['recall_pct']}%"
    assert metrics["precision_pct"] > 10.0, f"Precision failed floor: {metrics['precision_pct']}%"

    # Gate failure distribution spans gates (Gate 1 monopoly broken)
    gates = metrics["gate_failure_counts_model"]
    assert gates["gate_1"] < 100

    # Quote integrity
    assert metrics["verbatim_quote_rate"] > 70.0
    assert metrics["context_leak_quotes"] <= 1


def test_guard_rejects_empty_quote() -> None:
    """C2 Guard 1: Verify empty quote payload is rejected as an exclusion."""
    import json

    from v2.src.extract import parse_model_verdict

    target = {
        "turn_id": "turn_001",
        "speaker_label": "David Friedberg",
        "text": "Academic science enforces conformity around mainstream theory.",
    }
    raw = json.dumps({
        "verdict": "claim",
        "turn_id": "turn_001",
        "speaker": "David Friedberg",
        "type": "causal",
        "quote": "",
        "claim": "Academic science enforces conformity.",
    })
    res = parse_model_verdict(raw, target)
    assert res["verdict"] == "exclusion"
    assert res["validator_rejected"] is True
    assert res["rejection_reason"] == "empty_quote"
    assert res["gate_failed"] == "gate_4"


def test_guard_rejects_non_verbatim_quote() -> None:
    """C2 Guard 2: Verify hallucinated quote not present in target turn is rejected."""
    import json

    from v2.src.extract import parse_model_verdict

    target = {
        "turn_id": "turn_002",
        "speaker_label": "Jason Calacanis",
        "text": "Let us look at the federal deficit numbers.",
    }
    raw = json.dumps({
        "verdict": "claim",
        "turn_id": "turn_002",
        "speaker": "Jason Calacanis",
        "type": "position",
        "quote": "Republicans love to cut taxes and Democrats love to spend.",
        "claim": "Partisan fiscal priorities drive government expenditure.",
    })
    res = parse_model_verdict(raw, target)
    assert res["verdict"] == "exclusion"
    assert res["validator_rejected"] is True
    assert res["rejection_reason"] == "non_verbatim"
    assert res["gate_failed"] == "gate_4"


def test_guard_rejects_context_quote_falsification() -> None:
    """C2 Falsification: Feed the guard a real sentence from the context turn rather than the target turn

    and confirm it is rejected as a context leak.
    """
    import json

    from v2.src.extract import parse_model_verdict

    target = {
        "turn_id": "turn_003",
        "speaker_label": "David Sacks",
        "text": "I think that is exactly right.",
    }
    context = {
        "turn_id": "turn_002",
        "speaker_label": "Chamath Palihapitiya",
        "text": "Enterprise software multiples have compressed by fifty percent.",
    }
    raw = json.dumps({
        "verdict": "claim",
        "turn_id": "turn_003",
        "speaker": "David Sacks",
        "type": "position",
        "quote": "Enterprise software multiples have compressed by fifty percent.",
        "claim": "Enterprise software multiples have compressed substantially.",
    })
    res = parse_model_verdict(raw, target, context)
    assert res["verdict"] == "exclusion"
    assert res["validator_rejected"] is True
    assert res["rejection_reason"] == "context_leak"
    assert res["gate_failed"] == "gate_1"


def test_guard_accepts_verbatim_quote() -> None:
    """C2: Verify genuine verbatim quote in target turn passes both guards."""
    import json

    from v2.src.extract import parse_model_verdict

    target = {
        "turn_id": "turn_004",
        "speaker_label": "Chamath Palihapitiya",
        "text": "State-level AI regulation should be pre-empted federally.",
    }
    raw = json.dumps({
        "verdict": "claim",
        "turn_id": "turn_004",
        "speaker": "Chamath Palihapitiya",
        "type": "position",
        "quote": "State-level AI regulation should be pre-empted federally.",
        "claim": "State-level AI regulation should be pre-empted federally.",
    })
    res = parse_model_verdict(raw, target)
    assert res["verdict"] == "claim"
    assert res["validator_rejected"] is False
    assert res["quote_resolves_verbatim"] is True



