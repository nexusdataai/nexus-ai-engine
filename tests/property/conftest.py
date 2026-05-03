"""Property-tier fixtures and hypothesis settings."""

from __future__ import annotations

from hypothesis import HealthCheck, settings

# Our state-machine tests launch jobs against an InMemoryEngine; those
# jobs can run across hypothesis example boundaries (the engine persists
# state for the whole machine). Disable the "function scope" health check
# which would otherwise flag the pytest fixture reuse.
settings.register_profile(
    "engine_state_machine",
    max_examples=30,
    stateful_step_count=20,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
)
settings.register_profile(
    "thorough",
    parent=settings.get_profile("engine_state_machine"),
    max_examples=200,
    stateful_step_count=50,
)
settings.load_profile("engine_state_machine")
