"""Unit tests for the build_engine scaffold."""

from __future__ import annotations

import pytest

from nexus_ai_engine.config import EngineConfig
from nexus_ai_engine.factory import build_engine


def test_build_engine_raises_not_implemented_with_descriptive_message() -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        build_engine(EngineConfig())
    assert "phases 3+" in str(exc_info.value)
