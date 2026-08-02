"""Temporal client helper to enqueue RunExecutionWorkflow."""

from __future__ import annotations

import os
from uuid import UUID


async def start_execution_workflow(execution_id: UUID) -> None:
    from nexus_ai_engine.workers.temporal.workflows import TEMPORAL_AVAILABLE

    if not TEMPORAL_AVAILABLE:
        return

    from temporalio.client import Client

    target = os.environ.get("TEMPORAL_TARGET", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "nexus-ai-execution")

    client = await Client.connect(target, namespace=namespace)
    from nexus_ai_engine.workers.temporal.workflows import RunExecutionWorkflow

    await client.start_workflow(
        RunExecutionWorkflow.run,
        str(execution_id),
        id=f"execution-{execution_id}",
        task_queue=task_queue,
    )
