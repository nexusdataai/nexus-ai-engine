"""Composition root for the Nexus AI Engine.

``build_engine`` will return a fully-wired ``Engine`` object with the services,
executor, scheduler and default adapters attached. The implementation is
deferred until Phases 3 and later; this module exists so host applications can
import a stable entry point from day one.
"""

from __future__ import annotations

from .config import EngineConfig


def build_engine(config: EngineConfig):  # pragma: no cover - stub
    """Assemble and return the engine.

    Not implemented yet — stub lives here so consumers can wire against a stable
    entry point. Will be completed as services and adapters land in later
    phases.
    """
    raise NotImplementedError(
        "build_engine is a scaffold placeholder. "
        "Full composition lands in phases 3+."
    )
