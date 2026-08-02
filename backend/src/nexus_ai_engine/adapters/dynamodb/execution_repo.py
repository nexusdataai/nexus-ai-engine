"""DynamoDB execution repository (spec 050) — CRUD, locks, admission counters."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from nexus_ai_engine.config import get_config
from nexus_ai_engine.contracts.execution_graph import ExecutionGraph
from nexus_ai_engine.contracts.execution_state import ExecutionState


class RevisionConflictError(Exception):
    """Optimistic concurrency failure."""

    def __init__(self, execution_id: UUID, expected: int, actual: int | None):
        self.execution_id = execution_id
        self.expected = expected
        self.actual = actual
        super().__init__(f"revision conflict for {execution_id}: expected {expected}, got {actual}")


class LockNotAcquiredError(Exception):
    pass


def _to_decimal(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(v) for v in obj]
    return obj


def _from_decimal(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _from_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_decimal(v) for v in obj]
    return obj


class DynamoDBExecutionRepository:
    """Persistence for ExecutionState + ExecutionGraph in ai-engine-executions-{env}."""

    def __init__(self, table_name: str | None = None, *, dynamodb: Any = None, region: str | None = None):
        config = get_config()
        self.table_name = table_name or config.dynamodb_executions_table
        if not self.table_name:
            raise ValueError("dynamodb_executions_table is not configured")
        region = region or config.aws_region
        self._ddb = dynamodb or boto3.resource("dynamodb", region_name=region)
        self._table = self._ddb.Table(self.table_name)

    @staticmethod
    def pk(tenant_id: str, execution_id: UUID) -> str:
        return f"TENANT#{tenant_id}#EXEC#{execution_id}"

    @staticmethod
    def counter_pk() -> str:
        return "COUNTER#global"

    @staticmethod
    def lock_pk(execution_id: UUID) -> str:
        return f"LOCK#EXEC#{execution_id}"

    async def _run(self, fn):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn)

    async def put_state(self, state: ExecutionState, *, expected_revision: int | None = None) -> None:
        started = state.started_at or datetime.now(timezone.utc)
        item = {
            "PK": self.pk(state.tenant_id, state.execution_id),
            "SK": "STATE#current",
            "entity_type": "execution_state",
            "tenant_id": state.tenant_id,
            "journey_id": state.journey_id,
            "status": state.status.value,
            "started_at": started.isoformat(),
            "revision": state.revision,
            "payload": _to_decimal(state.model_dump(mode="json")),
        }

        def _put():
            kwargs: dict[str, Any] = {"Item": item}
            if expected_revision is not None:
                kwargs["ConditionExpression"] = "revision = :exp OR attribute_not_exists(PK)"
                kwargs["ExpressionAttributeValues"] = {":exp": expected_revision}
            try:
                self._table.put_item(**kwargs)
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    existing = self._table.get_item(
                        Key={"PK": item["PK"], "SK": "STATE#current"}
                    ).get("Item")
                    actual = existing.get("revision") if existing else None
                    raise RevisionConflictError(state.execution_id, expected_revision, actual) from exc
                raise

        await self._run(_put)

    async def get_state(self, tenant_id: str, execution_id: UUID) -> ExecutionState | None:
        def _get():
            resp = self._table.get_item(
                Key={"PK": self.pk(tenant_id, execution_id), "SK": "STATE#current"}
            )
            return resp.get("Item")

        item = await self._run(_get)
        if not item:
            return None
        payload = _from_decimal(item.get("payload", {}))
        return ExecutionState.model_validate(payload)

    async def find_by_execution_id(self, execution_id: UUID) -> ExecutionState | None:
        needle = str(execution_id)

        def _scan():
            resp = self._table.scan(
                FilterExpression="entity_type = :et AND contains(PK, :eid)",
                ExpressionAttributeValues={
                    ":et": "execution_state",
                    ":eid": needle,
                },
            )
            for item in resp.get("Items", []):
                if item.get("SK") == "STATE#current":
                    return item
            return None

        item = await self._run(_scan)
        if not item:
            return None
        payload = _from_decimal(item.get("payload", {}))
        return ExecutionState.model_validate(payload)

    async def put_graph(self, tenant_id: str, execution_id: UUID, graph: ExecutionGraph) -> None:
        body = graph.model_dump(mode="json")
        raw = json.dumps(body)
        item = {
            "PK": self.pk(tenant_id, execution_id),
            "SK": "GRAPH#snapshot",
            "entity_type": "execution_graph",
            "payload": raw if len(raw) < 350_000 else raw[:350_000],
        }

        def _put():
            self._table.put_item(Item=item)

        await self._run(_put)

    async def get_graph(self, tenant_id: str, execution_id: UUID) -> ExecutionGraph | None:
        def _get():
            resp = self._table.get_item(
                Key={"PK": self.pk(tenant_id, execution_id), "SK": "GRAPH#snapshot"}
            )
            return resp.get("Item")

        item = await self._run(_get)
        if not item:
            return None
        payload = item.get("payload")
        if isinstance(payload, str):
            data = json.loads(payload)
        else:
            data = _from_decimal(payload)
        return ExecutionGraph.model_validate(data)

    async def acquire_lock(self, execution_id: UUID, worker_id: str, ttl_seconds: int = 120) -> bool:
        pk = self.lock_pk(execution_id)
        expires = int(time.time()) + ttl_seconds

        def _put():
            try:
                self._table.put_item(
                    Item={
                        "PK": pk,
                        "SK": "LOCK",
                        "ttl": expires,
                        "worker_id": worker_id,
                    },
                    ConditionExpression="attribute_not_exists(PK)",
                )
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return False
                raise

        return await self._run(_put)

    async def release_lock(self, execution_id: UUID, worker_id: str) -> None:
        def _delete():
            self._table.delete_item(
                Key={"PK": self.lock_pk(execution_id), "SK": "LOCK"},
                ConditionExpression="worker_id = :wid",
                ExpressionAttributeValues={":wid": worker_id},
            )

        await self._run(_delete)

    async def increment_running(self) -> int:
        def _inc():
            resp = self._table.update_item(
                Key={"PK": self.counter_pk(), "SK": "RUNNING"},
                UpdateExpression="ADD running :one",
                ExpressionAttributeValues={":one": 1},
                ReturnValues="UPDATED_NEW",
            )
            return int(resp["Attributes"].get("running", 0))

        return await self._run(_inc)

    async def decrement_running(self) -> int:
        def _dec():
            resp = self._table.update_item(
                Key={"PK": self.counter_pk(), "SK": "RUNNING"},
                UpdateExpression="ADD running :neg",
                ExpressionAttributeValues={":neg": -1},
                ReturnValues="UPDATED_NEW",
            )
            val = int(resp["Attributes"].get("running", 0))
            return max(val, 0)

        return await self._run(_dec)

    async def get_running_count(self) -> int:
        def _get():
            resp = self._table.get_item(Key={"PK": self.counter_pk(), "SK": "RUNNING"})
            item = resp.get("Item") or {}
            return int(item.get("running", 0))

        return await self._run(_get)

    _ACTIVE_STATUSES = frozenset(
        {"pending", "running", "awaiting_approval", "paused", "verifying"}
    )

    async def list_executions(
        self,
        tenant_id: str,
        *,
        journey_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionState]:
        if journey_id:
            items = await self._query_by_journey(journey_id, limit=limit * 3)
        elif tenant_id:
            items = await self._query_by_tenant(tenant_id, limit=limit * 3)
        else:
            items = await self._scan_states(limit=limit * 3)

        states: list[ExecutionState] = []
        for item in items:
            if item.get("SK") != "STATE#current":
                continue
            if tenant_id and item.get("tenant_id") != tenant_id:
                continue
            if status and item.get("status") != status:
                continue
            payload = _from_decimal(item.get("payload", {}))
            states.append(ExecutionState.model_validate(payload))
            if len(states) >= limit:
                break
        return states

    async def count_running_for_journey(self, journey_id: str) -> int:
        items = await self._query_by_journey(journey_id, limit=500)
        return sum(
            1
            for item in items
            if item.get("SK") == "STATE#current" and item.get("status") in self._ACTIVE_STATUSES
        )

    async def _query_by_journey(self, journey_id: str, *, limit: int) -> list[dict]:
        def _query():
            items: list[dict] = []
            kwargs: dict[str, Any] = {
                "IndexName": "GSI1",
                "KeyConditionExpression": "journey_id = :jid",
                "ExpressionAttributeValues": {":jid": journey_id},
            }
            while len(items) < limit:
                resp = self._table.query(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            return items[:limit]

        return await self._run(_query)

    async def _query_by_tenant(self, tenant_id: str, *, limit: int) -> list[dict]:
        def _query():
            items: list[dict] = []
            kwargs: dict[str, Any] = {
                "IndexName": "GSI2",
                "KeyConditionExpression": "tenant_id = :tid",
                "ExpressionAttributeValues": {":tid": tenant_id},
            }
            while len(items) < limit:
                resp = self._table.query(**kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            return items[:limit]

        return await self._run(_query)

    async def _scan_states(self, *, limit: int) -> list[dict]:
        def _scan():
            items: list[dict] = []
            scan_kwargs: dict[str, Any] = {
                "FilterExpression": "begins_with(SK, :sk)",
                "ExpressionAttributeValues": {":sk": "STATE#"},
            }
            while len(items) < limit:
                resp = self._table.scan(**scan_kwargs)
                items.extend(resp.get("Items", []))
                if "LastEvaluatedKey" not in resp:
                    break
                scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            return items[:limit]

        return await self._run(_scan)
