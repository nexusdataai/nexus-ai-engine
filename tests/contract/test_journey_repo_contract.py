"""Journey-repository contract: same shape across all adapters.

Every engine adapter must expose a journey-repository surface with
async CRUD semantics. These tests exercise that surface against every
adapter registered in conftest.py. Today: in-memory only. Phase 3:
DynamoDB + S3-backed + custom.
"""

from __future__ import annotations

from nexus_ai_engine.models import JourneyCreate, JourneyUpdate, Stage, Step


def _make_journey(name: str = "contract-journey") -> JourneyCreate:
    return JourneyCreate(
        name=name,
        stages=[
            Stage(
                id="stg", name="S", order=1,
                steps=[Step(id="s1", name="S1", order=1, type="tool", tool="noop")],
            )
        ],
    )


def test_adapter_exposes_journey_methods(adapter) -> None:
    for method in ("list_journeys", "get_journey", "create_journey",
                   "update_journey", "delete_journey", "clone_journey"):
        assert callable(getattr(adapter, method, None)), (
            f"{type(adapter).__name__} missing async method {method!r}"
        )


async def test_journey_round_trip(adapter) -> None:
    created = await adapter.create_journey(_make_journey("rt"))
    assert created.id
    fetched = await adapter.get_journey(created.id)
    assert fetched is not None and fetched.name == "rt"

    updated = await adapter.update_journey(created.id, JourneyUpdate(name="rt v2"))
    assert updated is not None and updated.name == "rt v2"

    assert await adapter.delete_journey(created.id) is True
    assert await adapter.get_journey(created.id) is None


async def test_list_journeys_returns_list(adapter) -> None:
    items = await adapter.list_journeys()
    assert isinstance(items, list)


async def test_get_unknown_returns_none_not_exception(adapter) -> None:
    # Contract: getters never raise on "not found"; they return None.
    assert await adapter.get_journey("JRN-DOES-NOT-EXIST") is None
    assert await adapter.update_journey("JRN-NOPE", JourneyUpdate(name="x")) is None
    assert await adapter.delete_journey("JRN-NOPE") is False
