"""Contract-tier fixtures: parametrized across adapter implementations.

Test classes in ``tests/contract/`` inherit from the abstract bases in
``tests/contract/base.py`` and run once per registered adapter. Adding a new
adapter in a later phase is just a matter of adding a constructor here.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(params=["memory"], ids=["memory"])
def journey_repository(request: pytest.FixtureRequest) -> Any:
    """Return a JourneyRepository implementation.

    Phase 3+ adds ``"dynamodb"`` as an additional param that uses the
    moto-backed DynamoDB adapter.
    """
    if request.param == "memory":
        pytest.skip("In-memory journey repository lands in phase 3.")
    raise AssertionError(f"Unknown journey_repository param: {request.param}")


@pytest.fixture(params=["memory"], ids=["memory"])
def job_repository(request: pytest.FixtureRequest) -> Any:
    if request.param == "memory":
        pytest.skip("In-memory job repository lands in phase 3.")
    raise AssertionError(f"Unknown job_repository param: {request.param}")


@pytest.fixture(params=["memory"], ids=["memory"])
def prompt_repository(request: pytest.FixtureRequest) -> Any:
    if request.param == "memory":
        pytest.skip("In-memory prompt repository lands in phase 3.")
    raise AssertionError(f"Unknown prompt_repository param: {request.param}")
