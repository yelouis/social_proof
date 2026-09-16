"""B6 re-run (Issue 043 = A): the three models named by the item, and nothing else.

B6's first pass produced numbers that were all correct and all reproducible while
running a 2B, a 9B and a 7B vision model instead of the three ~18 GB models the item
named -- and reused an earlier run as one of its three arms. Nothing in ruff, mypy,
pytest or the arithmetic could catch that, because the artifact records model_id and
nobody asserted on it (trap 86).

This file asserts the inputs. Do not edit it to make it pass. If a tag below cannot be
resolved or a conversion is broken, that is an escalation to v2/docs/ongoing_errors.md
section 1 with options -- not a substitution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
EXTRACTION_DIR = ROOT_DIR / "artifacts" / "extraction"
EPISODE = "00251a80c868f535"

# Verified to resolve on HuggingFace, 4 safetensor shards each, September 15 2026.
SPECIFIED_MODELS = {
    "mlx-community/gemma-4-31b-it-4bit": 18.4,
    "mlx-community/GLM-4-32B-0414-4bit": 18.3,
    "mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit": 17.8,
}

# Arms that already exist. A new arm equal to any of these is a reused run, not a
# measurement, and must be labelled as such rather than reported as throughput.
PRIOR_ELAPSED = {841.37, 845.33, 942.51, 784.89, 734.27, 393.83}


def _arms() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in EXTRACTION_DIR.glob(f"b6_extraction_*_{EPISODE}.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[str(d.get("model_id"))] = d
    return out


def test_the_three_specified_models_each_have_an_arm() -> None:
    """(c) inputs: the item named three models; these three must be the arms."""
    arms = _arms()
    missing = sorted(set(SPECIFIED_MODELS) - set(arms))
    assert not missing, f"no B6 arm for: {missing}"


def test_no_unspecified_model_is_reported_as_a_b6_arm() -> None:
    """A fourth arm from a model nobody chose makes the consensus table mean something else."""
    extra = sorted(set(_arms()) - set(SPECIFIED_MODELS))
    assert not extra, f"unspecified models present as B6 arms: {extra}"


def _specified_arms() -> dict[str, dict[str, Any]]:
    """The three named arms, or a failure naming which are missing.

    Every per-arm check goes through this. Iterating whatever happens to be on disk
    would pass vacuously once the old arms are cleared, and passes today against the
    wrong models -- which is the bug this file exists to catch.
    """
    arms = _arms()
    missing = sorted(set(SPECIFIED_MODELS) - set(arms))
    assert not missing, f"no B6 arm for: {missing}"
    return {m: arms[m] for m in SPECIFIED_MODELS}


def test_each_arm_covers_the_whole_episode_with_the_guard_on() -> None:
    for model_id, d in _specified_arms().items():
        assert d["total_turns"] == 405, f"{model_id}: {d['total_turns']} turns"
        assert len(d["verdicts"]) == 405, f"{model_id}: {len(d['verdicts'])} verdicts"
        assert d.get("validators_added") == 1, (
            f"{model_id}: ran without C2's quote guard; its numbers are not comparable"
        )
        assert d.get("provenance_source") == "recorded", f"{model_id}: provenance not recorded"


def test_every_arm_ran_rather_than_being_copied() -> None:
    """B6's first pass reported a copy of C1's artifact as one of its three arms."""
    seen: dict[str, str] = {}
    for model_id, d in _specified_arms().items():
        elapsed = float(d["elapsed_seconds"])
        assert elapsed not in PRIOR_ELAPSED, (
            f"{model_id}: elapsed_seconds {elapsed} matches an earlier artifact -- reused run"
        )
        h = hashlib.sha256(
            json.dumps(d["verdicts"], sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert h not in seen, f"{model_id} and {seen[h]} produced identical verdicts"
        seen[h] = model_id


def test_all_arms_used_a_byte_identical_prompt() -> None:
    """A prompt tuned per model makes the comparison meaningless."""
    hashes = {m: d.get("prompt_content_hash") or d.get("prompt_version") for m, d in _specified_arms().items()}
    assert len(set(hashes.values())) == 1, f"prompt differs across arms: {hashes}"


def test_self_agreement_was_measured_where_the_model_fires() -> None:
    """Agreement over turns a model almost never fires on measures the exclusion rate."""
    f = EXTRACTION_DIR / f"b6_self_agreement_{EPISODE}.json"
    assert f.exists(), "no self-agreement artifact; the falsification left nothing resolvable"
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d.get("population") == "gold_claim_turns", "self-agreement not run on claim-bearing turns"
    assert "agreement_overall" in d and "agreement_on_claim_bearing_turns" in d, (
        "both figures must be reported; when they diverge the overall one is the exclusion rate"
    )
    assert d.get("claim_bearing_turns_n") is not None


def test_small_denominators_are_reported_as_counts() -> None:
    """3 of 4 is not 75.00%, and it is certainly not a 5.75x boost."""
    f = EXTRACTION_DIR / f"b6_agreement_{EPISODE}.json"
    assert f.exists(), "no agreement artifact"
    d = json.loads(f.read_text(encoding="utf-8"))
    for rule in ("unanimous", "majority", "any_model"):
        block = d[rule]
        n = block["claims_count"]
        if n < 20:
            assert block.get("report_as") == "count", (
                f"{rule}: {n} predictions must be reported as a count, not a percentage"
            )
            assert "precision_pct" not in block or block.get("precision_pct") is None, (
                f"{rule}: precision_pct present with denominator {n}"
            )
