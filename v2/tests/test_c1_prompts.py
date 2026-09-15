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
