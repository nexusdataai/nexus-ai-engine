"""Abstract test base classes — every adapter for a port must pass these.

Populated per-phase as ports and adapters land. Structure is in place today
so phase 3+ commits only add tests, not harness.
"""

from __future__ import annotations

import pytest


class JourneyRepositoryContract:
    """Tests every JourneyRepository implementation must satisfy."""

    def test_create_and_get_roundtrip(self, journey_repository):
        pytest.skip("Activates in phase 3 alongside the JourneyRepository Protocol.")

    def test_list_pagination(self, journey_repository):
        pytest.skip("Activates in phase 3 alongside the JourneyRepository Protocol.")


class JobRepositoryContract:
    """Tests every JobRepository implementation must satisfy."""

    def test_put_get_roundtrip(self, job_repository):
        pytest.skip("Activates in phase 3 alongside the JobRepository Protocol.")

    def test_status_transitions(self, job_repository):
        pytest.skip("Activates in phase 3 alongside the JobRepository Protocol.")


class PromptRepositoryContract:
    """Tests every PromptRepository implementation must satisfy."""

    def test_config_roundtrip(self, prompt_repository):
        pytest.skip("Activates in phase 3 alongside the PromptRepository Protocol.")
