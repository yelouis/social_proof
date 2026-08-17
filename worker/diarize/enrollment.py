"""Voice enrollment reference store and embedding extraction.

Implements design_source_acquisition.md §5.4 and agent_execution_guide.md §10 (U7).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


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
