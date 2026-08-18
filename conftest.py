"""Root pytest configuration and session hooks."""

import pytest

from worker import STUB_REGISTRY


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Prints STUB_REGISTRY at the top of every pytest test run."""
    lines = ["STUB_REGISTRY (Simulated / Pending Externals):"]
    for module_path, reason in STUB_REGISTRY.items():
        lines.append(f"  - {module_path}: {reason}")
    return lines
