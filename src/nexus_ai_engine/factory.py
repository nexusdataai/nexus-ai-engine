"""Composition root for the Nexus AI Engine.

``build_engine(config)`` returns the live ``InMemoryEngine`` pre-populated
with demo data. The embedded UI, CLI, and tests all wire against the same
object. When the DynamoDB adapter lands in phase 10 this factory can swap
the concrete engine class based on ``EngineConfig``.
"""

from __future__ import annotations

from .config import EngineConfig
from .execution import InMemoryEngine, seed


def build_engine(config: EngineConfig | None = None, *, seed_demo: bool = True) -> InMemoryEngine:
    """Assemble and return the engine.

    Args:
        config: EngineConfig (currently advisory — the in-memory engine does
            not require AWS settings).
        seed_demo: If True, populate the engine with the standard demo set
            (5 journeys + historical jobs + schedules + prompts) so a
            first-time port-forward shows something useful.
    """
    engine = InMemoryEngine()
    if seed_demo:
        seed(engine)
    return engine
