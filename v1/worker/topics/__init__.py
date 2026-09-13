"""Topic model and resolution subsystem.

Implements design_topic_model.md and agent_execution_guide.md §19 (P3).
"""

from worker.topics.cluster import TopicClusterer
from worker.topics.drift import TopicDriftGuard
from worker.topics.resolve import TopicResolver, compute_resolution_key

__all__ = [
    "TopicClusterer",
    "TopicDriftGuard",
    "TopicResolver",
    "compute_resolution_key",
]
