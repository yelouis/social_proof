"""Voice enrollment reference store and embedding extraction.

Implements design_source_acquisition.md §5.4 and agent_execution_guide.md §17 (I0.1).
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import torchaudio
from sklearn.cluster import DBSCAN

_DEFAULT_SPEAKER_CLASSIFIER: Any | None = None


def get_default_speaker_classifier() -> Any:
    """Lazy-loads SpeechBrain ECAPA-TDNN speaker classifier."""
    global _DEFAULT_SPEAKER_CLASSIFIER
    if _DEFAULT_SPEAKER_CLASSIFIER is None:
        from speechbrain.inference.speaker import EncoderClassifier

        _DEFAULT_SPEAKER_CLASSIFIER = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb"
        )
    return _DEFAULT_SPEAKER_CLASSIFIER


def extract_voice_embedding(
    audio_path: str | Path,
    start_s: float = 0.0,
    dur_s: float | None = None,
    extractor: Callable[[Any], np.ndarray] | None = None,
) -> list[float]:
    """Extracts a 192-dim normalized speaker voice embedding from audio."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    wav, sr = torchaudio.load(str(path))
    start_sample = int(start_s * sr)
    if dur_s is not None:
        num_samples = int(dur_s * sr)
        slice_wav = wav[:, start_sample : start_sample + num_samples]
    else:
        slice_wav = wav[:, start_sample:]

    if extractor is not None:
        vec = extractor(slice_wav)
    else:
        classifier = get_default_speaker_classifier()
        emb_tensor = classifier.encode_batch(slice_wav)
        vec = emb_tensor.squeeze().detach().cpu().numpy()

    vec = np.array(vec, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec.tolist()]


def verify_mutual_distinguishability(
    embeddings: dict[str, list[float]],
    t_low: float = 0.50,
) -> dict[tuple[str, str], float]:
    """Computes pairwise cosine similarities across subjects and asserts all cross-subject

    pairs sit strictly below T_low (Parameter 004). (Assertion c for I0.1)
    """
    subjects = list(embeddings.keys())
    results: dict[tuple[str, str], float] = {}

    for i in range(len(subjects)):
        for j in range(i + 1, len(subjects)):
            s1, s2 = subjects[i], subjects[j]
            v1 = np.array(embeddings[s1], dtype=np.float32)
            v2 = np.array(embeddings[s2], dtype=np.float32)
            norm1 = float(np.linalg.norm(v1))
            norm2 = float(np.linalg.norm(v2))
            sim = float(np.dot(v1, v2) / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
            results[(s1, s2)] = sim

            if sim >= t_low:
                raise AssertionError(
                    f"Mutual distinguishability failure between '{s1}' and '{s2}': "
                    f"cosine similarity {sim:.4f} >= T_low ({t_low:.4f}). "
                    f"Voice enrollment samples are too close; attribution will be confused."
                )

    return results


def verify_single_speaker(
    audio_path: str | Path,
    start_s: float = 0.0,
    dur_s: float | None = None,
    window_s: float = 3.0,
    hop_s: float = 1.5,
    t_low: float = 0.50,
    extractor: Callable[[Any], np.ndarray] | None = None,
) -> bool:
    """Runs windowed diarization over sample and asserts exactly one speaker cluster exists."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    wav, sr = torchaudio.load(str(path))
    start_sample = int(start_s * sr)
    if dur_s is not None:
        num_samples = int(dur_s * sr)
        slice_wav = wav[:, start_sample : start_sample + num_samples]
    else:
        slice_wav = wav[:, start_sample:]

    total_len_s = slice_wav.shape[1] / sr
    windows: list[np.ndarray] = []
    t = 0.0
    while t + window_s <= total_len_s:
        s_idx = int(t * sr)
        e_idx = int((t + window_s) * sr)
        w = slice_wav[:, s_idx:e_idx]
        if extractor is not None:
            emb = extractor(w)
        else:
            classifier = get_default_speaker_classifier()
            emb = classifier.encode_batch(w).squeeze().detach().cpu().numpy()
        emb = np.array(emb, dtype=np.float32)
        norm = float(np.linalg.norm(emb))
        if norm > 0:
            emb = emb / norm
        windows.append(emb)
        t += hop_s

    if len(windows) < 2:
        # Sample too short for windowed clustering; single speaker by definition
        return True

    n_windows = len(windows)
    dist_mat = np.zeros((n_windows, n_windows), dtype=np.float64)
    for i in range(n_windows):
        for j in range(n_windows):
            dot = float(np.dot(windows[i], windows[j]))
            dist_mat[i, j] = max(0.0, 1.0 - dot)

    eps = max(0.1, 1.0 - t_low)
    clustering = DBSCAN(eps=eps, min_samples=2, metric="precomputed").fit(dist_mat)
    unique_clusters = set(clustering.labels_) - {-1}
    if len(unique_clusters) != 1:
        raise AssertionError(
            f"Sample {audio_path} failed single-speaker check: "
            f"found {len(unique_clusters)} clusters (labels: {clustering.labels_.tolist()})."
        )
    return True


class VoiceEnrollmentStore:
    """Stores reference voice embeddings for enrolled subjects."""

    def __init__(self, base_dir: str | Path = ".cache/enrollments") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_enrollment(
        self,
        subject_id: str,
        embedding: list[float] | np.ndarray,
        source_id: str,
        verified_by: str = "curator",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Saves a verified reference voice embedding and returns its artifact hash."""
        vec = np.array(embedding, dtype=np.float32)
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        data = {
            "subject_id": subject_id,
            "source_id": source_id,
            "verified_by": verified_by,
            "embedding": vec.tolist(),
            "metadata": metadata or {},
        }
        serialized = json.dumps(data, sort_keys=True).encode("utf-8")
        enrollment_ref = hashlib.sha256(serialized).hexdigest()

        file_path = self.base_dir / f"enroll_{enrollment_ref}.json"
        file_path.write_bytes(serialized)
        return enrollment_ref

    def get_enrollment(self, enrollment_ref: str) -> dict[str, Any] | None:
        file_path = self.base_dir / f"enroll_{enrollment_ref}.json"
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data  # type: ignore[no-any-return]
