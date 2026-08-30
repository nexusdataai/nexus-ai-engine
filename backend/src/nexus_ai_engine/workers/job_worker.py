"""Redis Streams job worker — consumes queue and runs transformation / DSL jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from uuid import UUID

from loguru import logger

from nexus_ai_engine.config import config_from_environment, set_config
from nexus_ai_engine.events.sse_manager import sse_manager
from nexus_ai_engine.execution.transformation_job_executor import TransformationJobExecutor
from nexus_ai_engine.services.job_queue_service import (
    ActiveJobGuard,
    QueuedJob,
    ack_job,
    claim_job,
    ensure_consumer_group,
    get_active_job_count,
    get_pending_count,
    get_queue_depth,
    make_consumer_name,
    reclaim_stale_jobs,
)

WORKER_HEALTH_PORT = int(os.getenv("JOB_WORKER_HEALTH_PORT", "8081"))
_shutdown = threading.Event()
_consumer_name: Optional[str] = None
_runtime_service = None


def _get_runtime_service():
    global _runtime_service
    if _runtime_service is None:
        from nexus_ai_engine.adapters.dynamodb.execution_repo import DynamoDBExecutionRepository
        from nexus_ai_engine.execution.runtime_service import ExecutionRuntimeService
        from nexus_ai_engine.executor.admission import AdmissionController

        repo = DynamoDBExecutionRepository()
        _runtime_service = ExecutionRuntimeService(
            repository=repo,
            admission=AdmissionController(repository=repo),
        )
    return _runtime_service


class _HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/live", "/liveness"):
            body = json.dumps({"alive": True, "service": "job-worker"}).encode()
            self.send_response(200)
        elif path in ("/ready", "/readiness", "/health"):
            try:
                from nexus_ai_engine.services.job_queue_service import _client

                _client().ping()
                body = json.dumps(
                    {
                        "ready": True,
                        "queue_depth": get_queue_depth(),
                        "pending": get_pending_count(),
                        "active_jobs": get_active_job_count(),
                    }
                ).encode()
                self.send_response(200)
            except Exception as exc:
                body = json.dumps({"ready": False, "error": str(exc)}).encode()
                self.send_response(503)
        elif path == "/metrics":
            body = json.dumps(
                {
                    "job_queue_depth": get_queue_depth(),
                    "job_queue_pending": get_pending_count(),
                    "job_worker_active": get_active_job_count(),
                }
            ).encode()
            self.send_response(200)
        else:
            self.send_response(404)
            body = b"not found"
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_health_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", WORKER_HEALTH_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, name="job-worker-health", daemon=True)
    thread.start()
    logger.info("Job worker health server on :{}", WORKER_HEALTH_PORT)
    return server


def _run_dsl_job(job: QueuedJob) -> None:
    runtime = _get_runtime_service()
    asyncio.run(runtime.run_to_completion(UUID(job.job_id)))


def _process_job(job: QueuedJob, executor: TransformationJobExecutor) -> None:
    logger.info(
        "Worker executing {} job {} journey={} stage={}",
        job.job_kind,
        job.job_id,
        job.journey_id,
        job.stage_id,
    )
    should_ack = True
    try:
        with ActiveJobGuard():
            if job.job_kind == "dsl_execution":
                _run_dsl_job(job)
            else:
                executor.execute_job(job.journey_id, job.job_id)
    except RuntimeError as exc:
        if "capacity" in str(exc).lower():
            logger.warning("Job {} deferred: {}", job.job_id, exc)
            should_ack = False
            time.sleep(2)
            return
        executor.fail_job(job.journey_id, job.job_id, str(exc))
        raise
    except Exception as exc:
        if job.job_kind == "transformation" and job.journey_id:
            try:
                executor.fail_job(job.journey_id, job.job_id, str(exc))
            except Exception:
                pass
        raise
    finally:
        if should_ack:
            ack_job(job.stream_id)
            if job.job_kind == "transformation":
                sse_manager.cleanup_job_sync(job.job_id)


def worker_loop() -> None:
    global _consumer_name
    _consumer_name = make_consumer_name("ai-engine-worker")
    ensure_consumer_group()
    sse_manager.enable_redis_bridge(publish_only=True)
    executor = TransformationJobExecutor()
    logger.info("Job worker started as {}", _consumer_name)

    while not _shutdown.is_set():
        try:
            for reclaimed in reclaim_stale_jobs(_consumer_name):
                if _shutdown.is_set():
                    break
                _process_job(reclaimed, executor)

            job = claim_job(_consumer_name, block_ms=2000)
            if job is None:
                continue
            _process_job(job, executor)
        except Exception as exc:
            logger.exception("Job worker loop error: {}", exc)
            time.sleep(1)


def _handle_signal(signum, frame):  # noqa: ARG001
    logger.info("Job worker received signal {}, shutting down", signum)
    _shutdown.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    set_config(config_from_environment())

    register_demo = os.getenv("REGISTER_DEMO_STAGES", "true").lower() not in (
        "0", "false", "no", "off", ""
    )
    if register_demo:
        try:
            from nexus_ai_engine.stages import register_demo_stages

            registered = register_demo_stages()
            logger.info("Registered {} demo stages in worker: {}", len(registered), ", ".join(registered))
        except Exception as exc:
            logger.exception("Demo stage registration failed: {}", exc)

    health_server = _start_health_server()
    try:
        worker_loop()
    finally:
        health_server.shutdown()
        logger.info("Job worker stopped")


if __name__ == "__main__":
    main()
