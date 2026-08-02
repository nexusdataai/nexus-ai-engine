"""Moto integration tests for DynamoDBExecutionRepository."""

from __future__ import annotations

from uuid import uuid4

import boto3
import moto
import pytest

from nexus_ai_engine.adapters.dynamodb.execution_repo import (
    DynamoDBExecutionRepository,
    RevisionConflictError,
)
from nexus_ai_engine.adapters.dynamodb.table_definitions import create_all_tables
from nexus_ai_engine.contracts.execution_state import ExecutionState, ExecutionStatus


def _sample_state(*, journey_id: str = "demo-journey") -> ExecutionState:
    eid = uuid4()
    tid = str(uuid4())
    return ExecutionState(
        execution_id=eid,
        journey_id=journey_id,
        journey_version=1,
        tenant_id=tid,
        status=ExecutionStatus.PENDING,
        graph_snapshot_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_put_get_state_roundtrip():
    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        names = create_all_tables(client, "test")
        repo = DynamoDBExecutionRepository(table_name=names["executions"])
        state = _sample_state()
        await repo.put_state(state)
        loaded = await repo.get_state(state.tenant_id, state.execution_id)
        assert loaded is not None
        assert loaded.execution_id == state.execution_id
        assert loaded.journey_id == state.journey_id


@pytest.mark.asyncio
async def test_revision_conflict():
    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        names = create_all_tables(client, "test")
        repo = DynamoDBExecutionRepository(table_name=names["executions"])
        state = _sample_state()
        await repo.put_state(state)
        state.revision = 99
        with pytest.raises(RevisionConflictError):
            await repo.put_state(state, expected_revision=2)


@pytest.mark.asyncio
async def test_lock_acquire_release():
    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        names = create_all_tables(client, "test")
        repo = DynamoDBExecutionRepository(table_name=names["executions"])
        eid = uuid4()
        assert await repo.acquire_lock(eid, "worker-a") is True
        assert await repo.acquire_lock(eid, "worker-b") is False
        await repo.release_lock(eid, "worker-a")
        assert await repo.acquire_lock(eid, "worker-b") is True


@pytest.mark.asyncio
async def test_list_and_count_by_journey():
    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        names = create_all_tables(client, "test")
        repo = DynamoDBExecutionRepository(table_name=names["executions"])
        s1 = _sample_state(journey_id="j-a")
        s2 = _sample_state(journey_id="j-a")
        s3 = _sample_state(journey_id="j-b")
        for s in (s1, s2, s3):
            await repo.put_state(s)
        listed = await repo.list_executions("", journey_id="j-a")
        assert len(listed) == 2
        assert await repo.count_running_for_journey("j-a") == 2
