"""Structural invariants of the package."""

from __future__ import annotations

import importlib
from pathlib import Path

import nexus_ai_engine


EXPECTED_SUBMODULES = [
    "adapters",
    "contracts",
    "events",
    "execution",
    "models",
    "server",
    "server.routers",
    "services",
    "stages",
    "testing",
]


def test_all_declared_submodules_importable() -> None:
    for name in EXPECTED_SUBMODULES:
        importlib.import_module(f"nexus_ai_engine.{name}")


def test_version_matches_pyproject() -> None:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    repo_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    declared_version = pyproject["project"]["version"]
    assert nexus_ai_engine.__version__ == declared_version, (
        f"Version drift: nexus_ai_engine.__version__={nexus_ai_engine.__version__!r} "
        f"but pyproject [project].version={declared_version!r}"
    )


def test_public_server_symbol() -> None:
    from nexus_ai_engine.server import create_app

    assert callable(create_app)


def test_public_testing_symbols() -> None:
    from nexus_ai_engine.testing import (  # noqa: F401
        JourneyRunResult,
        JourneyYAMLRunner,
        TestHttpClient,
        TestMCPClient,
        make_test_app,
        make_test_engine,
        make_test_mcp_server,
    )
