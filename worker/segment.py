"""Segmentation: Merges same-speaker word turns into immutable Utterance records.

Implements design_source_acquisition.md §5.5 and agent_execution_guide.md §8 (U4).
"""

from typing import Any

from worker.entities import Source, Utterance
from worker.storage import Storage, compute_utterance_id
from worker.transcribe.reconciler import WordTimestamp


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
) -> list[Utterance]:
    """Merges contiguous same-speaker words into Utterance records.

    Splits on pauses > max_pause_ms or turn length > max_duration_ms.
    text_verbatim is immutable (Invariant I9).
    """
    if not words:
        return []

    utterances: list[Utterance] = []
    current_words: list[WordTimestamp] = []
    current_start_ms = words[0].start_ms

    for _i, w in enumerate(words):
        if not current_words:
            current_words.append(w)
            current_start_ms = w.start_ms
            continue

        prev_w = current_words[-1]
        pause = w.start_ms - prev_w.end_ms
        current_duration = w.end_ms - current_start_ms

        # Split condition: pause too long or utterance exceeds max duration
        if pause > max_pause_ms or current_duration > max_duration_ms:
            # Emit utterance
            text_verbatim = " ".join(cw.word for cw in current_words)
            end_ms = current_words[-1].end_ms

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
            current_words = [w]
            current_start_ms = w.start_ms
        else:
            current_words.append(w)

    # Emit final span
    if current_words:
        text_verbatim = " ".join(cw.word for cw in current_words)
        end_ms = current_words[-1].end_ms

        parquet_hash = None
        if storage:
            words_dict = [cw.to_dict() for cw in current_words]
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

    return utterances
