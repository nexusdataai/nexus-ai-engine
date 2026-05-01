"""Unit tests for the error hierarchy."""

from __future__ import annotations

import pytest

from nexus_ai_engine.errors import (
    ConfigurationError,
    EngineError,
    JobCancelledError,
    RepositoryError,
    StageNotRegisteredError,
)


@pytest.mark.parametrize(
    "cls",
    [ConfigurationError, StageNotRegisteredError, JobCancelledError, RepositoryError],
)
def test_subclass_of_engine_error(cls: type[EngineError]) -> None:
    assert issubclass(cls, EngineError)


@pytest.mark.parametrize(
    "cls",
    [ConfigurationError, StageNotRegisteredError, JobCancelledError, RepositoryError],
)
def test_raisable_and_catchable_as_engine_error(cls: type[EngineError]) -> None:
    with pytest.raises(EngineError):
        raise cls("boom")


def test_engine_error_is_exception() -> None:
    assert issubclass(EngineError, Exception)
