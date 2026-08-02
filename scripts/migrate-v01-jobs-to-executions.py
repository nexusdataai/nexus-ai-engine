#!/usr/bin/env python3
"""Migrate legacy v0.1 transformation jobs to v0.2 execution records (dry-run default)."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

import boto3

from nexus_ai_engine.adapters.dynamodb.execution_repo import DynamoDBExecutionRepository
from nexus_ai_engine.contracts.execution_state import ExecutionState, ExecutionStatus, NodeState, NodeStatus

logger = logging.getLogger(__name__)


def _map_status(raw: str | None) -> ExecutionStatus:
    mapping = {
        "pending": ExecutionStatus.PENDING,
        "running": ExecutionStatus.RUNNING,
        "succeeded": ExecutionStatus.SUCCEEDED,
        "failed": ExecutionStatus.FAILED,
        "cancelled": ExecutionStatus.CANCELLED,
    }
    return mapping.get((raw or "pending").lower(), ExecutionStatus.PENDING)


def migrate_jobs(
    *,
    journeys_table: str,
    executions_table: str,
    region: str,
    dry_run: bool,
    limit: int,
) -> dict:
    ddb = boto3.resource("dynamodb", region_name=region)
    journeys = ddb.Table(journeys_table)
    repo = DynamoDBExecutionRepository(table_name=executions_table, dynamodb=ddb)

    scanned = 0
    migrated = 0
    skipped = 0

    scan_kwargs = {
        "FilterExpression": "begins_with(SK, :job)",
        "ExpressionAttributeValues": {":job": "JOB#"},
    }
    while scanned < limit:
        resp = journeys.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            scanned += 1
            if scanned > limit:
                break
            job_id = item.get("job_id") or item.get("SK", "").replace("JOB#", "")
            journey_id = item.get("journey_id", "unknown")
            tenant_id = item.get("tenant_id") or str(uuid4())
            try:
                execution_id = UUID(str(job_id).replace("JOB-", "").replace("JOB", ""))
            except ValueError:
                execution_id = uuid4()

            state = ExecutionState(
                execution_id=execution_id,
                journey_id=journey_id,
                journey_version=int(item.get("journey_version", 1)),
                tenant_id=str(tenant_id),
                status=_map_status(item.get("status")),
                graph_snapshot_id=uuid4(),
                nodes={
                    "root": NodeState(node_id=uuid4(), step_id="legacy", status=NodeStatus.SUCCEEDED)
                },
                submitted_by=item.get("triggered_by", "migration"),
                trace_id=f"migrate:{job_id}",
                started_at=datetime.now(timezone.utc),
            )
            if dry_run:
                migrated += 1
                continue
            import asyncio

            async def _write():
                current = await repo.get_state(state.tenant_id, state.execution_id)
                if current:
                    return "skipped"
                await repo.put_state(state)
                return "migrated"

            result = asyncio.run(_write())
            if result == "skipped":
                skipped += 1
            else:
                migrated += 1
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    summary = {"scanned": scanned, "migrated": migrated, "skipped": skipped, "dry_run": dry_run}
    logger.info("Migration summary: %s", json.dumps(summary))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate v0.1 jobs to executions table")
    parser.add_argument("--journeys-table", required=True)
    parser.add_argument("--executions-table", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--execute", action="store_true", help="Perform writes (default dry-run)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    migrate_jobs(
        journeys_table=args.journeys_table,
        executions_table=args.executions_table,
        region=args.region,
        dry_run=not args.execute,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
