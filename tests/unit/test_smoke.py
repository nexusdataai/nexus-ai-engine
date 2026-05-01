"""Smoke tests — ensure the package imports and exposes its version."""

from __future__ import annotations

import nexus_ai_engine


def test_version_exposed() -> None:
    assert isinstance(nexus_ai_engine.__version__, str)
    assert nexus_ai_engine.__version__.startswith("0.1.")


def test_submodules_importable() -> None:
    import nexus_ai_engine.adapters  # noqa: F401
    import nexus_ai_engine.contracts  # noqa: F401
    import nexus_ai_engine.events  # noqa: F401
    import nexus_ai_engine.execution  # noqa: F401
    import nexus_ai_engine.models  # noqa: F401
    import nexus_ai_engine.services  # noqa: F401
    import nexus_ai_engine.stages  # noqa: F401
