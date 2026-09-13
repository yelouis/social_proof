"""Item X4 Falsification.

Removes the decline branch (Prompt v1.8) and extracts from the same 20 descriptive utterances.
Asserts that frames reappear for them under v1.8, whereas under v1.9 they decline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_x4_step1 import HAND_PICKED_DESCRIPTIVE_UTTERANCES

from worker.extract.runtime import LocalGemmaRuntime


def run_falsification() -> None:
    print("=== ITEM X4 FALSIFICATION ===")
    print("Comparing extraction of 20 descriptive utterances:")
    print("  With decline branch (Prompt v1.9)")
    print("  Without decline branch (Prompt v1.8)\n")

    runtime_v19 = LocalGemmaRuntime(prompt_version="v1.9", load_live_backend=True)

    # Prompt v1.8: system prompt without Rule 0 decline branch
    # Read prompt v1.8 from git HEAD
    import subprocess

    v18_system_prompt = subprocess.check_output(
        ["git", "show", "HEAD:worker/extract/runtime.py"],
        text=True,
    )
    # Extract STABLE_SYSTEM_PROMPT from v1.8
    start_marker = 'STABLE_SYSTEM_PROMPT: str = """'
    end_marker = '""".strip()'
    start_idx = v18_system_prompt.find(start_marker) + len(start_marker)
    end_idx = v18_system_prompt.find(end_marker, start_idx)
    v18_prompt = v18_system_prompt[start_idx:end_idx].strip()

    backend = runtime_v19.backend

    print("Extracting 20 descriptive utterances...")
    v19_declined = 0
    v18_frames_reappeared = 0

    for idx, (uid, text) in enumerate(HAND_PICKED_DESCRIPTIVE_UTTERANCES, 1):
        # v1.9 extraction (with decline branch)
        stats_v19 = runtime_v19.generate_constrained(text, subject_context="Speaker: Host / Guest")
        has_claim_v19 = len(stats_v19.parsed_result.claims) > 0

        # v1.8 extraction (without decline branch)
        v18_full_prompt = (
            f"<start_of_turn>user\n{v18_prompt}\n\n"
            f"Subject context: Speaker: Host / Guest\n"
            f"Utterance: {text}\n"
            f"Extract structured claims in valid JSON format:\n<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
        raw_v18, _, _, _ = backend.generate(v18_full_prompt, max_tokens=256)
        import re

        json_match = re.search(r"\{.*\}", raw_v18, re.DOTALL)
        raw_json_v18 = json_match.group(0) if json_match else '{"claims": []}'
        try:
            from worker.extract.schema import ExtractionResult

            parsed_v18 = ExtractionResult.model_validate_json(raw_json_v18)
            has_claim_v18 = len(parsed_v18.claims) > 0
            v18_frame = parsed_v18.claims[0].position_frame if has_claim_v18 else None
        except Exception:
            has_claim_v18 = False
            v18_frame = None

        if not has_claim_v19:
            v19_declined += 1
        if has_claim_v18:
            v18_frames_reappeared += 1

        print(f"[{idx:02d}/20] {uid}:")
        print(
            f"   v1.9 (with decline)   : {'EMITTED claim' if has_claim_v19 else 'DECLINED (empty)'}"
        )
        print(
            f"   v1.8 (without decline): {'EMITTED claim: ' + str(v18_frame) if has_claim_v18 else 'DECLINED'}"
        )

    print("\n--- FALSIFICATION SUMMARY ---")
    print(
        f"Under Prompt v1.9 (with decline branch)   : {v19_declined}/20 declined ({v19_declined / 20 * 100:.1f}%)"
    )
    print(
        f"Under Prompt v1.8 (without decline branch): {v18_frames_reappeared}/20 emitted fabricated frames ({v18_frames_reappeared / 20 * 100:.1f}%)"
    )

    assert v19_declined >= 15, f"Expected at least 15/20 declined under v1.9, got {v19_declined}"
    assert v18_frames_reappeared >= 10, (
        f"Expected at least 10/20 frames reappeared under v1.8, got {v18_frames_reappeared}"
    )
    print(
        "\nFALSIFICATION TEST PASSED: Removing decline branch caused fabricated frames to reappear."
    )


if __name__ == "__main__":
    run_falsification()
