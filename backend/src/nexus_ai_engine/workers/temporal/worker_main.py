"""Temporal worker entrypoint for nexus-ai-engine execution workers."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

logger = logging.getLogger(__name__)


async def _run_temporal() -> None:
    from temporalio.client import Client
    from temporalio.worker import Worker

    from nexus_ai_engine.workers.temporal.workflows import RunExecutionWorkflow, executor_tick

    target = os.environ.get("TEMPORAL_TARGET", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "nexus-ai-execution")

    client = await Client.connect(target, namespace=namespace)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[RunExecutionWorkflow],
        activities=[executor_tick],
    )
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    logger.info("Temporal worker started queue=%s target=%s", task_queue, target)
    async with worker:
        await stop.wait()


def main() -> None:
    from nexus_ai_engine.workers.temporal.workflows import TEMPORAL_AVAILABLE

    if not TEMPORAL_AVAILABLE:
        raise SystemExit("temporalio is not installed; pip install nexus-ai-engine[temporal]")
    asyncio.run(_run_temporal())


if __name__ == "__main__":
    main()
