"""Unit tests for schedule request mapping and journey-level stage ids."""

from __future__ import annotations

from nexus_ai_engine.server.routers.legacy.schedule_api import map_schedule_updates
from nexus_ai_engine.services.scheduler_service import SchedulerService


def test_map_schedule_updates_snake_to_camel() -> None:
    mapped = map_schedule_updates(
        {"interval_minutes": 15, "enabled": False, "timezone": "UTC"}
    )
    assert mapped == {
        "intervalMinutes": 15,
        "enabled": False,
        "timezone": "UTC",
    }


def test_map_schedule_updates_ignores_unknown_passthrough() -> None:
    mapped = map_schedule_updates({"interval_minutes": 5})
    assert mapped["intervalMinutes"] == 5
    assert "interval_minutes" not in mapped


def test_empty_stage_id_is_journey_level() -> None:
    assert SchedulerService.normalize_stage_id(None) == ""
    assert SchedulerService.normalize_stage_id("") == ""
    assert SchedulerService.normalize_stage_id("  ") == ""
    assert SchedulerService.normalize_stage_id("journey") == ""
    assert SchedulerService.normalize_stage_id("JOURNEY") == ""


def test_stage_id_preserved_for_stage_schedules() -> None:
    assert SchedulerService.normalize_stage_id("order_to_cash") == "order_to_cash"
    assert SchedulerService.normalize_stage_id("job_archival") == "job_archival"


def test_journey_action_request_allows_empty_stage() -> None:
    from nexus_ai_engine.models.journey_model import JourneyActionRequest

    req = JourneyActionRequest(
        action="run_job",
        journey_id="JRN-1",
        stage_id=None,
        triggered_by="scheduler",
    )
    assert req.stage_id is None
    assert not SchedulerService.normalize_stage_id(req.stage_id)
