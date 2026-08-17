"""Source adapters package."""

from worker.adapters.base import (
    NormalizedSource,
    Provenance,
    RawSource,
    SourceAdapter,
    SourceRef,
)
from worker.adapters.institutional import (
    CongressionalRecordAdapter,
    SECFilingAdapter,
)
from worker.adapters.podcast import PodcastRSSAdapter
from worker.adapters.youtube import YouTubeAdapter

__all__ = [
    "CongressionalRecordAdapter",
    "NormalizedSource",
    "PodcastRSSAdapter",
    "Provenance",
    "RawSource",
    "SECFilingAdapter",
    "SourceAdapter",
    "SourceRef",
    "YouTubeAdapter",
]
