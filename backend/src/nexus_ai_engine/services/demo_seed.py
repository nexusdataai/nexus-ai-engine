"""Seed demo journeys into a persisted (DynamoDB) store for local dev."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Set

from ..models.journey_model import JourneyAction, JourneyActionRequest
from ..stages import DEMO_JOURNEYS

if TYPE_CHECKING:
    from .journey_service import JourneyService

logger = logging.getLogger(__name__)


def _existing_journey_names(existing: Any) -> Set[str]:
    names: Set[str] = set()
    items = existing
    if isinstance(items, dict):
        items = items.get("journeys") or items.get("items") or items.get("data") or []
    if not isinstance(items, list):
        return names
    for row in items:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("journey_name")
        if name:
            names.add(str(name))
    return names


async def _create_demo_journey(journey_service: JourneyService, journey: Dict[str, Any]) -> bool:
    stages = [
        {
            "stageId": stage["stage_id"],
            "name": stage["name"],
            "description": stage.get("description", ""),
            "order": stage.get("order", index),
        }
        for index, stage in enumerate(journey["stages"], start=1)
    ]
    response = await journey_service.create_journey(
        JourneyActionRequest(
            action=JourneyAction.CREATE,
            journey_data={
                "name": journey["name"],
                "description": journey.get("description"),
                "odaComponentType": journey["odaComponentType"],
                "priority": journey.get("priority", "medium"),
                "stages": stages,
            },
        )
    )
    if response.status == "success":
        return True
    logger.error(
        "Failed to seed journey %r: %s",
        journey["name"],
        response.error or response.message,
    )
    return False


async def seed_demo_journeys_if_empty(journey_service: JourneyService) -> int:
    """Create bundled demo journeys when the store is empty."""
    listing = await journey_service.list_journeys(
        JourneyActionRequest(action=JourneyAction.LIST)
    )
    if listing.status != "success":
        logger.warning("Skipping demo seed: list_journeys failed: %s", listing.error)
        return 0

    existing = listing.data or []
    if isinstance(existing, dict):
        existing = existing.get("journeys") or existing.get("items") or []
    if len(existing) > 0:
        return 0

    created = 0
    for journey in DEMO_JOURNEYS:
        if await _create_demo_journey(journey_service, journey):
            created += 1
    return created


JOB_ARCHIVAL_JOURNEY: Dict[str, Any] = {
    "name": "Job Archival",
    "description": "Archive older job executions from DynamoDB to S3, keeping the latest 1000 globally.",
    "odaComponentType": "data-pipeline",
    "priority": "low",
    "stages": [
        {
            "stage_id": "job_archival",
            "name": "Job Archival",
            "description": "Export older jobs to S3 and trim DynamoDB to the hot window.",
        }
    ],
}


async def seed_job_archival_journey(journey_service: JourneyService) -> int:
    """Create the Job Archival journey when it is missing (match by name)."""
    listing = await journey_service.list_journeys(
        JourneyActionRequest(action=JourneyAction.LIST)
    )
    if listing.status != "success":
        logger.warning("Skipping job-archival seed: list_journeys failed: %s", listing.error)
        return 0

    known = _existing_journey_names(listing.data or [])
    if JOB_ARCHIVAL_JOURNEY["name"] in known:
        return 0
    if await _create_demo_journey(journey_service, JOB_ARCHIVAL_JOURNEY):
        return 1
    return 0


async def seed_missing_demo_journeys(journey_service: JourneyService) -> int:
    """Create demo journeys that are not already present (match by name)."""
    listing = await journey_service.list_journeys(
        JourneyActionRequest(action=JourneyAction.LIST)
    )
    if listing.status != "success":
        logger.warning("Skipping demo seed: list_journeys failed: %s", listing.error)
        return 0

    known = _existing_journey_names(listing.data or [])
    created = 0
    for journey in DEMO_JOURNEYS:
        if journey["name"] in known:
            continue
        if await _create_demo_journey(journey_service, journey):
            created += 1
            known.add(journey["name"])
    return created
