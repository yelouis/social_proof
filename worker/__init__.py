"""Social Proof worker package."""

STUB_REGISTRY: dict[str, str] = {
    "worker.transcribe.engine": "MockTranscriptionEngine — real engine pending V3",
    "worker.diarize.attribution": "synthetic vectors — pyannote pending V4",
    "worker.extract.runtime": "no backend — Gemma pending V5",
}
