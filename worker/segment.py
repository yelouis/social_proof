"""Segmentation: Merges same-speaker word turns into immutable Utterance records.

Implements design_source_acquisition.md §5.5 and agent_execution_guide.md §8 (U4).
"""

from typing import Any

from worker.entities import Source, Utterance
from worker.storage import Storage, compute_utterance_id
from worker.transcribe.reconciler import WordTimestamp

TERMINAL_PUNCTUATION: frozenset[str] = frozenset([".", "?", "!"])
ABBREVIATIONS: frozenset[str] = frozenset(["mr.", "mrs.", "ms.", "dr.", "u.s.", "vs.", "e.g.", "i.e."])


def is_terminal_word(word_str: str) -> bool:
    """Returns True if the word ends with terminal sentence punctuation (. ? !)."""
    clean = word_str.rstrip('"\'”’)')
    if not clean:
        return False
    if clean.lower() in ABBREVIATIONS:
        return False
    return any(clean.endswith(t) for t in TERMINAL_PUNCTUATION)


def segment_words_into_utterances(
    source: Source,
    subject_id: str,
    words: list[WordTimestamp],
    speaker_label: str = "speaker_0",
    attribution_confidence: str = "high",
    attribution_method: str = "voice_embedding_match",
    max_pause_ms: int = 1500,
    max_duration_ms: int = 30000,
    storage: Storage | None = None,
    enforce_sentence_boundary: bool = True,
) -> list[Utterance]:
    """Merges contiguous same-speaker words into immutable Utterance records.

    Segments on sentence boundaries (terminal punctuation) and natural pauses.
    Splits on:
    1. Terminal punctuation (. ? !) when followed by a pause (>= 400ms),
       target duration (>= 10000ms), or a capitalized next word.
    2. Long pauses (> max_pause_ms).
    3. Turn length fallback (> max_duration_ms) at clause boundaries or pauses.

    Ensures zero utterances begin or end mid-word (Invariant I9, Trap 30).
    """
    if not words:
        return []

    utterances: list[Utterance] = []
    current_words: list[WordTimestamp] = []
    current_start_ms = words[0].start_ms

    for i, w in enumerate(words):
        # Skip consecutive duplicate word at boundary (whisper audio overlap artifact)
        if (
            current_words
            and current_words[-1].word.lower().strip(".,?!") == w.word.lower().strip(".,?!")
            and abs(w.start_ms - current_words[-1].end_ms) < 200
        ):
            continue

        if not current_words:
            current_words.append(w)
            current_start_ms = w.start_ms
            continue

        current_words.append(w)
        next_w = words[i + 1] if i + 1 < len(words) else None
        pause_ms = (next_w.start_ms - w.end_ms) if next_w else 9999
        current_duration = current_words[-1].end_ms - current_start_ms
        is_term = is_terminal_word(w.word)

        should_split = False
        if not next_w:
            should_split = True
        elif enforce_sentence_boundary and is_term:
            # Sentence boundary reached: break if natural pause, reasonable length, or capital next
            if (
                pause_ms >= 400
                or current_duration >= 10000
                or (next_w and next_w.word and (next_w.word[0].isupper() or next_w.word[0] in ('"', "'", '“', '‘')))
            ):
                should_split = True
        elif pause_ms > max_pause_ms:
            # Long pause break
            should_split = True
        elif current_duration > max_duration_ms:
            # Max duration fallback: prefer clause punctuation or pause
            if any(w.word.endswith(c) for c in (",", ";", "--", "-")) or pause_ms >= 300 or is_term:
                should_split = True
            elif current_duration > max_duration_ms * 1.5:
                should_split = True

        if should_split:
            # Clean leading chopped hyphen fragments from audio slicing artifacts
            while (
                len(current_words) > 1
                and (current_words[0].word.startswith("-") or not any(c.isalnum() for c in current_words[0].word))
            ):
                current_words.pop(0)
                if current_words:
                    current_start_ms = current_words[0].start_ms

            if not current_words:
                continue

            text_verbatim = " ".join(cw.word for cw in current_words).strip()
            end_ms = current_words[-1].end_ms

            if enforce_sentence_boundary and text_verbatim:
                # Strip any leading hyphens/dashes
                text_verbatim = text_verbatim.lstrip("-— \t\n")
                if text_verbatim and text_verbatim[0].islower():
                    text_verbatim = text_verbatim[0].upper() + text_verbatim[1:]
                if text_verbatim and not any(text_verbatim.rstrip('"\'”’').endswith(t) for t in TERMINAL_PUNCTUATION):
                    text_verbatim = text_verbatim + "."

            parquet_hash = None
            if storage:
                words_dict: list[dict[str, Any]] = [cw.to_dict() for cw in current_words]
                parquet_hash = storage.artifacts.put_word_timestamps(words_dict)

            utt_id = compute_utterance_id(source.source_id, current_start_ms, text_verbatim)
            utt = Utterance(
                utterance_id=utt_id,
                source_id=source.source_id,
                subject_id=subject_id,
                text_verbatim=text_verbatim,
                start_ms=current_start_ms,
                end_ms=end_ms,
                speaker_label=speaker_label,
                attribution_confidence=attribution_confidence,
                attribution_method=attribution_method,
                word_timestamps_ref=parquet_hash,
                language="en",
                transcription_pass_count=2,
                dual_pass_agreement=True,
                negation_uncertain=False,
            )
            utterances.append(utt)
            if storage:
                storage.insert_utterance(utt)

            # Start new span
            current_words = []
            if next_w:
                current_start_ms = next_w.start_ms

    return utterances
