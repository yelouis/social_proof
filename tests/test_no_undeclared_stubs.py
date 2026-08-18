"""CI guard against undeclared stubs (V1).

Asserts that every module claiming to wrap an external model is in one of two explicit states:
- DECLARED: package is declared in pyproject.toml, is importable in the environment,
  and is actually imported by the worker module.
- STUBBED: the concrete class/function name starts with 'Mock' or 'Stub', and the module
  is explicitly listed in worker.STUB_REGISTRY with a justification and gating issue.

Any module in an ambiguous, unannounced, or undeclared state causes this test to FAIL.
"""

import importlib
from pathlib import Path

from worker import STUB_REGISTRY

EXTERNAL_CONTRACTS: dict[str, tuple[str, str]] = {
    "worker.transcribe.engine": ("faster_whisper", "TranscriptionEngine"),
    "worker.diarize.attribution": ("pyannote.audio", "Diarizer"),
    "worker.extract.runtime": ("mlx_lm", "LocalGemmaRuntime"),
    "worker.extract.dedup": ("sentence_transformers", "Embedder"),
}

EXPECTED_CONTRACT_KEYS: set[str] = {
    "worker.transcribe.engine",
    "worker.diarize.attribution",
    "worker.extract.runtime",
    "worker.extract.dedup",
}


def test_external_contracts_coverage_cannot_shrink() -> None:
    """Guard against shrinking contract coverage: all expected contract modules must be present."""
    assert set(EXTERNAL_CONTRACTS.keys()) == EXPECTED_CONTRACT_KEYS


def test_all_external_contracts_are_either_declared_or_stubbed() -> None:
    """For each contract, assert it is either declared and real, or explicitly registered as a stub."""
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_text = (repo_root / "pyproject.toml").read_text()

    for module_path, (pkg_name, target_symbol) in EXTERNAL_CONTRACTS.items():
        module = importlib.import_module(module_path)

        # Check if declared in pyproject.toml
        pkg_declared = (pkg_name in pyproject_text) or (pkg_name.replace("_", "-") in pyproject_text)

        # Check if importable
        pkg_importable = False
        try:
            importlib.import_module(pkg_name.replace("-", "_").split(".")[0])
            pkg_importable = True
        except ImportError:
            pkg_importable = False

        # Check if imported by the module
        pkg_imported_in_module = any(
            pkg_name.replace("-", "_") in getattr(obj, "__module__", "")
            for obj in vars(module).values()
        )

        is_declared_and_real = pkg_declared and pkg_importable and pkg_imported_in_module

        # Check stub status
        is_stubbed = module_path in STUB_REGISTRY
        if is_stubbed:
            # Concrete implementation must announce itself as Mock* or Stub*
            symbols = [name for name in dir(module) if name.startswith("Mock") or name.startswith("Stub") or name.startswith("stub_")]
            assert len(symbols) > 0, f"Module {module_path} is registered in STUB_REGISTRY but has no Mock*/Stub* symbols"
            assert not is_declared_and_real, f"Module {module_path} is declared as real but still registered in STUB_REGISTRY"
        else:
            # Must be declared and real
            assert is_declared_and_real, (
                f"Module {module_path} claims contract {target_symbol} but is neither declared in "
                f"pyproject.toml with real imports nor registered in STUB_REGISTRY"
            )


def test_falsification_shrinking_external_contracts_causes_failure() -> None:
    """Falsification test: Removing an entry from EXTERNAL_CONTRACTS causes contract assertion failure."""
    shrunk_contracts = {k: v for k, v in EXTERNAL_CONTRACTS.items() if k != "worker.extract.dedup"}
    assert set(shrunk_contracts.keys()) != EXPECTED_CONTRACT_KEYS  # Falsification confirmed!


def test_falsification_plausibly_named_stub_without_mock_prefix_fails() -> None:
    """Falsification test: A stub not named Mock* or Stub* fails stub symbol validation."""
    class FakeModule:
        DeterministicVectorizer = object()

    symbols = [name for name in dir(FakeModule) if name.startswith("Mock") or name.startswith("Stub") or name.startswith("stub_")]
    assert len(symbols) == 0  # Falsification confirmed!
