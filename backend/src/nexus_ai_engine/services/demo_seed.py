"""Seed demo journeys into a persisted (DynamoDB) store for local dev."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.journey_model import JourneyAction, JourneyActionRequest
from ..stages import DEMO_JOURNEYS

if TYPE_CHECKING:
    from .journey_service import JourneyService

logger = logging.getLogger(__name__)


async def seed_demo_journeys_if_empty(journey_service: JourneyService) -> int:
    """Create bundled demo journeys when the store is empty.

    Used for K3s local dev where ``build_engine`` wires DynamoDB (not
    ``InMemoryEngine``), so the in-process ``seed()`` path does not run.
    """
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
            created += 1
        else:
            logger.error(
                "Failed to seed journey %r: %s",
                journey["name"],
                response.error or response.message,
            )

    return created
