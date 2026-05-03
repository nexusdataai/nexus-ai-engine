"""Contract-tier fixtures.

Contract tests run the same assertions against every adapter
implementation the engine supports. Today that's only the in-memory
engine (the real adapter-layer lands in Phase 3 of the extraction
plan). When Phase 3 ships DynamoDB / S3 / filesystem adapters, extend
the `adapter_factories` list below with the new factories and every
test in this tier picks them up automatically.

Each test receives an `adapter` fixture that yields a fresh, isolated
adapter instance. The `adapter_name` fixture is the factory key
(useful for error messages and for skipping adapter-specific tests).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from nexus_ai_engine.execution import InMemoryEngine
from tests.fixtures.steps import register_all


def _in_memory_factory() -> Any:
    """Fresh in-memory engine with deterministic step tools registered."""
    engine = InMemoryEngine()
    register_all(engine)
    return engine


# Registry of adapter factories, keyed by a short name. Phase 3 extends:
#   adapter_factories = {
#       "in_memory": _in_memory_factory,
#       "moto_ddb":  _moto_ddb_factory,
#       "fs":        _fs_factory,
#   }
adapter_factories: dict[str, Callable[[], Any]] = {
    "in_memory": _in_memory_factory,
}


@pytest.fixture(params=list(adapter_factories.keys()))
def adapter_name(request) -> str:
    return request.param


@pytest.fixture
def adapter(adapter_name: str) -> Any:
    return adapter_factories[adapter_name]()
