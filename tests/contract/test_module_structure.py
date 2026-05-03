"""Structural assertions about the contracts + adapters packages.

Placeholder suite: the contracts + adapters packages are stubs today
("Populated in Phase 3 of the extraction plan"). These tests document
the expected public surface at the import level and will tighten as
Phase 3 adds real Protocol classes + adapter implementations.

Tests kept deliberately permissive today (assert-imports-succeed +
smoke-check on a known non-empty test-support module) so they pass
against the current stubs AND against the future real implementation
without rewrite.
"""

from __future__ import annotations

import importlib


def test_contracts_package_imports_cleanly() -> None:
    module = importlib.import_module("nexus_ai_engine.contracts")
    assert module is not None


def test_adapters_package_imports_cleanly() -> None:
    module = importlib.import_module("nexus_ai_engine.adapters")
    assert module is not None


def test_testing_harness_exposes_expected_public_symbols() -> None:
    # Stable today: the harness is the reference "adapter" the rest
    # of the codebase trusts. Contract tests against future adapters
    # will compare their behavior to this one.
    testing = importlib.import_module("nexus_ai_engine.testing")
    for name in ("JourneyYAMLRunner", "TestHttpClient", "make_test_app", "make_test_engine"):
        assert hasattr(testing, name), f"nexus_ai_engine.testing missing {name!r}"
