"""Property-tier fixtures — hypothesis settings profiles."""

from __future__ import annotations

try:
    from hypothesis import HealthCheck, Verbosity, settings
except ImportError:  # pragma: no cover
    settings = None  # type: ignore[assignment]


if settings is not None:
    settings.register_profile(
        "dev",
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    settings.register_profile("ci", max_examples=200, deadline=500)
    settings.register_profile(
        "thorough",
        max_examples=1000,
        deadline=None,
        verbosity=Verbosity.verbose,
    )

    import os

    _profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
    settings.load_profile(_profile)
