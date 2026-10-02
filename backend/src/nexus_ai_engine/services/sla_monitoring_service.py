"""Infra SLA monitoring — five pillars with snapshot fallback store."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from typing import Any, Deque, Dict, List, Optional, Tuple

from loguru import logger

from .sla_scoring_utils import (
    build_pillar,
    score_higher_is_better,
    score_lower_is_better,
    status_from_score,
)

try:
    import boto3
    from boto3.dynamodb.conditions import Key

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    Key = None  # type: ignore

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

PILLAR_IDS = ("performance", "availability", "reliability", "security", "compliance")
REDIS_SNAPSHOT_KEY = "ai-engine:sla-snapshots"
MEMORY_SNAPSHOT_LIMIT = 288


class SlaMonitoringService:
    INTERVAL_SECONDS = 300

    PERFORMANCE_APP_WEIGHT = 0.55
    PERFORMANCE_DATA_WEIGHT = 0.45
    AVAILABILITY_APP_WEIGHT = 0.50
    AVAILABILITY_DATA_WEIGHT = 0.50
    RELIABILITY_APP_WEIGHT = 0.40
    RELIABILITY_DATA_WEIGHT = 0.60
    SECURITY_APP_WEIGHT = 0.35
    SECURITY_DATA_WEIGHT = 0.65
    COMPLIANCE_APP_WEIGHT = 0.25
    COMPLIANCE_DATA_WEIGHT = 0.75

    def __init__(self) -> None:
        self._ddb = None
        self._table = None
        self._table_name: Optional[str] = None
        self._table_ready = False
        self._task: Optional[asyncio.Task] = None
        self._cache: Dict[int, Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl = 60
        self._engine: Any = None
        self._memory: Deque[Dict[str, Any]] = deque(maxlen=MEMORY_SNAPSHOT_LIMIT)
        self._memory_lock = Lock()

    def bind_engine(self, engine: Any) -> None:
        self._engine = engine

    def _ensure_table(self) -> None:
        if self._table is not None and self._table_ready:
            return
        if not BOTO3_AVAILABLE:
            return
        try:
            from ..config import get_config

            env = get_config().environment
            region = get_config().aws_region
        except Exception:
            env = os.getenv("ENVIRONMENT", "dev")
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

        self._table_name = f"ai-engine-{env}-sla-snapshots"
        self._ddb = boto3.resource("dynamodb", region_name=region)
        try:
            self._ddb.meta.client.describe_table(TableName=self._table_name)
        except Exception:
            try:
                self._ddb.create_table(
                    TableName=self._table_name,
                    KeySchema=[
                        {"AttributeName": "PK", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "PK", "AttributeType": "S"},
                        {"AttributeName": "SK", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                waiter = self._ddb.meta.client.get_waiter("table_exists")
                waiter.wait(TableName=self._table_name, WaiterConfig={"Delay": 2, "MaxAttempts": 10})
                logger.info("Created SLA snapshots table: {}", self._table_name)
            except Exception as exc:
                logger.warning("Could not create SLA snapshots table: {}", exc)
                self._table = None
                self._table_ready = False
                return

        self._table = self._ddb.Table(self._table_name)
        self._table_ready = True

    async def start_periodic(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info("SLA monitoring recorder started (interval={}s)", self.INTERVAL_SECONDS)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.collect_and_record(window_hours=1)
            except Exception as exc:
                logger.debug("SLA monitoring loop error: {}", exc)
            await asyncio.sleep(self.INTERVAL_SECONDS)

    async def collect_and_record(self, window_hours: int = 1) -> Dict[str, Any]:
        snapshot = await self.compute_snapshot(window_hours=window_hours)
        await asyncio.to_thread(self._write_snapshot, snapshot)
        try:
            from .app_trends_service import record_queue_snapshot

            await asyncio.to_thread(record_queue_snapshot)
        except Exception:
            pass
        try:
            from .resource_monitoring_service import record_resource_snapshot

            await asyncio.to_thread(record_resource_snapshot)
        except Exception:
            pass
        try:
            from .data_store_monitoring_service import record_data_store_snapshots

            await asyncio.to_thread(record_data_store_snapshots)
        except Exception:
            pass
        self._cache[window_hours] = (time.time(), snapshot)
        return snapshot

    async def get_summary(self, window_hours: int = 1) -> Dict[str, Any]:
        cached = self._cache.get(window_hours)
        if cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        latest = await asyncio.to_thread(self._read_latest_snapshot, window_hours)
        if latest:
            self._cache[window_hours] = (time.time(), latest)
            return latest

        return await self.collect_and_record(window_hours=window_hours)

    async def get_timeline(self, hours: int = 24) -> Dict[str, Any]:
        points = await asyncio.to_thread(self._read_timeline, hours)
        return {"hours": hours, "points": points}

    async def get_pillar_detail(self, pillar: str, window_hours: int = 1) -> Dict[str, Any]:
        pillar = pillar.lower()
        if pillar not in PILLAR_IDS:
            return {"pillar": pillar, "error": f"Unknown pillar: {pillar}"}

        snapshot = await self.compute_snapshot(window_hours=window_hours)
        detail = (snapshot.get("pillars") or {}).get(pillar)
        if not detail:
            return {"pillar": pillar, "error": "No data"}

        timeline = await asyncio.to_thread(self._pillar_timeline, pillar, 24)
        return {
            "pillar": pillar,
            "window_hours": window_hours,
            "timestamp": snapshot.get("timestamp"),
            "timeline": timeline,
            **detail,
        }

    async def compute_snapshot(self, window_hours: int = 1) -> Dict[str, Any]:
        redis_ms, redis_ok = await asyncio.to_thread(self._redis_ping)
        perf, avail, reli, sec, comp = await asyncio.gather(
            self._compute_performance(window_hours, redis_ms=redis_ms),
            self._compute_availability(window_hours, redis_ok=redis_ok),
            self._compute_reliability(window_hours),
            self._compute_security(window_hours),
            self._compute_compliance(window_hours),
        )
        pillars = {
            "performance": perf,
            "availability": avail,
            "reliability": reli,
            "security": sec,
            "compliance": comp,
        }
        scores = [p.get("score") for p in pillars.values() if p.get("score") is not None]
        overall = round(sum(scores) / len(scores), 1) if scores else None
        statuses = [p.get("status") for p in pillars.values() if p.get("status")]
        return {
            "window_hours": window_hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_score": overall,
            "overall_status": self._worst_status(statuses),
            "pillars": pillars,
        }

    @staticmethod
    def _worst_status(statuses: List[str]) -> str:
        if "critical" in statuses:
            return "critical"
        if "warning" in statuses:
            return "warning"
        if statuses:
            return "healthy"
        return "unknown"

    async def _compute_performance(
        self, window_hours: int, *, redis_ms: Optional[float]
    ) -> Dict[str, Any]:
        audit, cpu, mem, ddb_latency, s3_ms = await asyncio.gather(
            asyncio.to_thread(self._request_stats, window_hours),
            asyncio.to_thread(self._system_cpu),
            asyncio.to_thread(self._system_memory),
            asyncio.to_thread(self._dynamodb_probe_ms),
            asyncio.to_thread(self._s3_probe_ms),
        )
        p95 = audit.get("p95_duration_ms")
        p99 = audit.get("p99_duration_ms")
        error_rate_pct = (audit.get("error_rate_5xx") or 0) * 100
        rps = audit.get("requests_per_second") or 0

        app_components = [
            {
                "id": "api_latency_p95",
                "label": "API latency (p95)",
                "value": p95,
                "unit": "ms",
                "weight": 0.30,
                "score": score_lower_is_better(p95, target=500, warning=2000, critical=5000),
            },
            {
                "id": "api_latency_p99",
                "label": "API latency (p99)",
                "value": p99,
                "unit": "ms",
                "weight": 0.10,
                "score": score_lower_is_better(p99, target=800, warning=3000, critical=8000),
            },
            {
                "id": "api_error_rate",
                "label": "HTTP 5xx rate",
                "value": round(error_rate_pct, 2),
                "unit": "%",
                "weight": 0.20,
                "score": score_lower_is_better(error_rate_pct, target=0.1, warning=1.0, critical=5.0),
            },
            {
                "id": "backend_pod_cpu",
                "label": "API pod CPU",
                "value": cpu,
                "unit": "%",
                "weight": 0.25,
                "score": score_lower_is_better(cpu, target=70, warning=85, critical=95),
            },
            {
                "id": "backend_pod_memory",
                "label": "API pod memory",
                "value": mem,
                "unit": "%",
                "weight": 0.10,
                "score": score_lower_is_better(mem, target=75, warning=90, critical=98),
            },
            {
                "id": "throughput_rps",
                "label": "Throughput",
                "value": round(float(rps), 2),
                "unit": "req/s",
                "weight": 0.05,
                "score": 100.0 if float(rps) > 0 else 90.0,
            },
        ]
        data_components = [
            {
                "id": "dynamodb_read_latency",
                "label": "DynamoDB read latency",
                "value": ddb_latency,
                "unit": "ms",
                "weight": 0.35,
                "score": score_lower_is_better(ddb_latency, target=20, warning=50, critical=200),
            },
            {
                "id": "redis_ping",
                "label": "Redis PING",
                "value": redis_ms,
                "unit": "ms",
                "weight": 0.35,
                "score": score_lower_is_better(redis_ms, target=5, warning=20, critical=100)
                if redis_ms is not None
                else None,
            },
            {
                "id": "minio_head_bucket",
                "label": "MinIO/S3 HeadBucket",
                "value": s3_ms,
                "unit": "ms",
                "weight": 0.30,
                "score": score_lower_is_better(s3_ms, target=200, warning=1000, critical=5000)
                if s3_ms is not None
                else None,
            },
        ]
        summary_metrics = [
            {
                "label": "API p95",
                "value": f"{int(p95)}ms" if p95 is not None else "—",
                "status": status_from_score(app_components[0].get("score")),
            },
            {
                "label": "Error rate",
                "value": f"{error_rate_pct:.2f}%",
                "status": status_from_score(app_components[2].get("score")),
            },
            {"label": "Throughput", "value": f"{float(rps):.1f} req/s", "status": "healthy"},
            {
                "label": "CPU",
                "value": f"{cpu:.1f}%" if cpu is not None else "—",
                "status": status_from_score(app_components[3].get("score")),
            },
        ]
        return build_pillar(
            app_components=app_components,
            data_components=data_components,
            app_weight=self.PERFORMANCE_APP_WEIGHT,
            data_weight=self.PERFORMANCE_DATA_WEIGHT,
            summary_metrics=summary_metrics,
        )

    async def _compute_availability(
        self, window_hours: int, *, redis_ok: Optional[bool]
    ) -> Dict[str, Any]:
        uptime_pct, cpu, mem, ddb_ok, s3_ok, ready_ratio = await asyncio.gather(
            asyncio.to_thread(self._health_uptime_pct, window_hours),
            asyncio.to_thread(self._system_cpu),
            asyncio.to_thread(self._system_memory),
            asyncio.to_thread(self._dynamodb_reachable),
            asyncio.to_thread(self._s3_reachable),
            asyncio.to_thread(self._ready_ratio),
        )
        app_components = [
            {
                "id": "health_probe_success",
                "label": "Health probe success",
                "value": uptime_pct,
                "unit": "%",
                "weight": 0.25,
                "score": score_higher_is_better(uptime_pct, target=99.9, warning=99.0, critical=95.0),
            },
            {
                "id": "backend_ready_ratio",
                "label": "Ready ratio",
                "value": ready_ratio,
                "unit": "%",
                "weight": 0.25,
                "score": score_higher_is_better(ready_ratio, target=100, warning=99, critical=50),
            },
            {
                "id": "backend_pod_cpu_avail",
                "label": "API CPU headroom",
                "value": cpu,
                "unit": "%",
                "weight": 0.25,
                "score": score_lower_is_better(cpu, target=85, warning=95, critical=99),
            },
            {
                "id": "backend_pod_memory_avail",
                "label": "API memory headroom",
                "value": mem,
                "unit": "%",
                "weight": 0.25,
                "score": score_lower_is_better(mem, target=90, warning=97, critical=99),
            },
        ]
        data_components = [
            {
                "id": "dynamodb_reachable",
                "label": "DynamoDB reachable",
                "value": 100.0 if ddb_ok else 0.0,
                "unit": "%",
                "weight": 0.40,
                "score": 100.0 if ddb_ok else 0.0,
            },
            {
                "id": "redis_reachable",
                "label": "Redis reachable",
                "value": 100.0 if redis_ok else (0.0 if redis_ok is False else None),
                "unit": "%",
                "weight": 0.30,
                "score": 100.0 if redis_ok else (None if redis_ok is None else 0.0),
            },
            {
                "id": "s3_minio_reachable",
                "label": "S3/MinIO reachable",
                "value": 100.0 if s3_ok else (0.0 if s3_ok is False else None),
                "unit": "%",
                "weight": 0.30,
                "score": 100.0 if s3_ok else (None if s3_ok is None else 0.0),
            },
        ]
        pillar = build_pillar(
            app_components=app_components,
            data_components=data_components,
            app_weight=self.AVAILABILITY_APP_WEIGHT,
            data_weight=self.AVAILABILITY_DATA_WEIGHT,
            summary_metrics=[
                {
                    "label": "Uptime",
                    "value": f"{uptime_pct:.1f}%" if uptime_pct is not None else "—",
                    "status": status_from_score(app_components[0].get("score")),
                },
                {
                    "label": "Ready ratio",
                    "value": f"{ready_ratio:.0f}%" if ready_ratio is not None else "—",
                    "status": status_from_score(app_components[1].get("score")),
                },
                {
                    "label": "Memory",
                    "value": f"{mem:.1f}%" if mem is not None else "—",
                    "status": status_from_score(app_components[3].get("score")),
                },
                {
                    "label": "CPU",
                    "value": f"{cpu:.1f}%" if cpu is not None else "—",
                    "status": status_from_score(app_components[2].get("score")),
                },
            ],
        )
        if uptime_pct is not None:
            pillar["uptime_pct"] = round(uptime_pct, 2)
        return pillar

    async def _compute_reliability(self, window_hours: int) -> Dict[str, Any]:
        rel_hours = max(window_hours, 24)
        jobs, audit, restarts, queue_lag = await asyncio.gather(
            self._job_metrics(rel_hours),
            asyncio.to_thread(self._request_stats, rel_hours),
            asyncio.to_thread(self._pod_restart_count),
            asyncio.to_thread(self._queue_lag_ratio_pct),
        )
        throughput = jobs.get("throughput") or {}
        succeeded = int(throughput.get("succeeded") or 0)
        failed = int(throughput.get("failed") or 0)
        total = succeeded + failed
        success_rate = (succeeded / total * 100) if total > 0 else 100.0
        error_5xx_pct = (audit.get("error_rate_5xx") or 0) * 100

        app_components = [
            {
                "id": "job_success_rate",
                "label": "Job success rate",
                "value": round(success_rate, 2),
                "unit": "%",
                "weight": 0.35,
                "score": score_higher_is_better(success_rate, target=99, warning=95, critical=90),
            },
            {
                "id": "backend_5xx_rate",
                "label": "Backend 5xx rate",
                "value": round(error_5xx_pct, 2),
                "unit": "%",
                "weight": 0.25,
                "score": score_lower_is_better(error_5xx_pct, target=0.1, warning=1.0, critical=5.0),
            },
            {
                "id": "pod_crashloop_events",
                "label": "Pod restart events",
                "value": restarts,
                "unit": "count",
                "weight": 0.25,
                "score": score_lower_is_better(restarts, target=0, warning=2, critical=5),
            },
            {
                "id": "queue_lag_health",
                "label": "Queue lag vs 2-wave horizon",
                "value": queue_lag,
                "unit": "%",
                "weight": 0.15,
                "score": score_lower_is_better(queue_lag, target=50, warning=100, critical=200)
                if queue_lag is not None
                else None,
            },
        ]
        data_components = [
            {
                "id": "pipeline_completion",
                "label": "Pipeline completion",
                "value": round(success_rate, 2),
                "unit": "%",
                "weight": 1.0,
                "score": score_higher_is_better(success_rate, target=99, warning=95, critical=90),
            },
        ]
        return build_pillar(
            app_components=app_components,
            data_components=data_components,
            app_weight=self.RELIABILITY_APP_WEIGHT,
            data_weight=self.RELIABILITY_DATA_WEIGHT,
            summary_metrics=[
                {
                    "label": "Success Rate",
                    "value": f"{success_rate:.1f}%",
                    "status": status_from_score(app_components[0].get("score")),
                },
                {"label": "Failed Jobs (24h)", "value": str(failed), "status": status_from_score(app_components[0].get("score"))},
                {"label": "Total Jobs (24h)", "value": str(total), "status": "healthy"},
                {
                    "label": "5xx Rate",
                    "value": f"{error_5xx_pct:.2f}%",
                    "status": status_from_score(app_components[1].get("score")),
                },
            ],
        )

    async def _compute_security(self, _window_hours: int) -> Dict[str, Any]:
        auth_method = self._auth_method()
        tls_enabled, tls_score = self._tls_status()
        debug_disabled = os.getenv("DEBUG", "false").lower() not in ("1", "true", "yes")
        app_components = [
            {
                "id": "auth_method",
                "label": "Auth method",
                "value": 100.0 if auth_method in ("Local", "OIDC") else None,
                "unit": "%",
                "weight": 0.25,
                "score": 100.0 if auth_method in ("Local", "OIDC") else None,
            },
            {
                "id": "failed_auth_rate",
                "label": "Failed auth rate",
                "value": None,
                "unit": "%",
                "weight": 0.20,
                "score": None,
            },
            {
                "id": "tls_enabled",
                "label": "TLS termination",
                "value": tls_score,
                "unit": "%",
                "weight": 0.30,
                "score": tls_score,
            },
            {
                "id": "api_key_protection",
                "label": "Debug disabled",
                "value": 100.0 if debug_disabled else 0.0,
                "unit": "%",
                "weight": 0.25,
                "score": 100.0 if debug_disabled else 30.0,
            },
        ]
        data_components = [
            {
                "id": "encryption_at_rest",
                "label": "Encryption at rest",
                "value": 100.0,
                "unit": "%",
                "weight": 1.0,
                "score": 100.0,
            },
        ]
        return build_pillar(
            app_components=app_components,
            data_components=data_components,
            app_weight=self.SECURITY_APP_WEIGHT,
            data_weight=self.SECURITY_DATA_WEIGHT,
            summary_metrics=[
                {"label": "Auth Method", "value": auth_method, "status": "healthy"},
                {
                    "label": "TLS",
                    "value": "Enabled" if tls_enabled else "Partial",
                    "status": status_from_score(tls_score),
                },
                {"label": "Failed Auth", "value": "n/a", "status": "unknown"},
                {
                    "label": "Debug",
                    "value": "Disabled" if debug_disabled else "Enabled",
                    "status": "healthy" if debug_disabled else "warning",
                },
            ],
        )

    async def _compute_compliance(self, _window_hours: int) -> Dict[str, Any]:
        retention_keep = self._retention_keep()
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "local"
        audit_partial = True
        app_components = [
            {
                "id": "audit_log",
                "label": "Audit log",
                "value": 70.0 if audit_partial else 100.0,
                "unit": "%",
                "weight": 0.35,
                "score": 70.0 if audit_partial else 100.0,
            },
            {
                "id": "rbac_enforced",
                "label": "RBAC",
                "value": None,
                "unit": "%",
                "weight": 0.25,
                "score": None,
            },
        ]
        data_components = [
            {
                "id": "data_retention",
                "label": "Job archival retention",
                "value": float(retention_keep),
                "unit": "count",
                "weight": 0.50,
                "score": 100.0 if retention_keep >= 1000 else 80.0,
            },
            {
                "id": "region",
                "label": "AWS region",
                "value": 100.0,
                "unit": "%",
                "weight": 0.50,
                "score": 100.0,
            },
        ]
        return build_pillar(
            app_components=app_components,
            data_components=data_components,
            app_weight=self.COMPLIANCE_APP_WEIGHT,
            data_weight=self.COMPLIANCE_DATA_WEIGHT,
            summary_metrics=[
                {"label": "Audit log", "value": "Partial", "status": "warning"},
                {"label": "Retention", "value": f"keep-{retention_keep}", "status": "healthy"},
                {"label": "Region", "value": region, "status": "healthy"},
                {"label": "RBAC", "value": "Not configured", "status": "unknown"},
            ],
        )

    def _request_stats(self, window_hours: int) -> Dict[str, Any]:
        from ..server.request_metrics import get_request_metrics_store

        return get_request_metrics_store().stats(window_hours=window_hours)

    def _system_cpu(self) -> Optional[float]:
        if not PSUTIL_AVAILABLE:
            return None
        try:
            return float(psutil.cpu_percent(interval=0.05))
        except Exception:
            return None

    def _system_memory(self) -> Optional[float]:
        if not PSUTIL_AVAILABLE:
            return None
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            return None

    def _dynamodb_probe_ms(self) -> Optional[float]:
        try:
            from ..config import get_config

            cfg = get_config()
            table = cfg.dynamodb_transformation_table
            if not table:
                return None
            start = time.perf_counter()
            import boto3 as _boto3

            client = _boto3.client("dynamodb", region_name=cfg.aws_region)
            client.describe_table(TableName=table)
            return round((time.perf_counter() - start) * 1000, 1)
        except Exception as exc:
            logger.debug("DynamoDB probe failed: {}", exc)
            return None

    def _dynamodb_reachable(self) -> bool:
        return self._dynamodb_probe_ms() is not None

    def _redis_ping(self) -> Tuple[Optional[float], Optional[bool]]:
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return None, None
            start = time.perf_counter()
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            ok = bool(client.ping())
            ms = round((time.perf_counter() - start) * 1000, 1)
            return (ms, True) if ok else (101.0, False)
        except Exception as exc:
            logger.debug("Redis ping failed: {}", exc)
            return 101.0, False

    def _s3_probe_ms(self) -> Optional[float]:
        try:
            from ..config import get_config

            cfg = get_config()
            bucket = cfg.s3_journey_logs_bucket or cfg.s3_journey_reports_bucket
            if not bucket:
                return None
            try:
                from ..adapters.aws.client_manager import create_aws_client

                client = create_aws_client("s3")
            except Exception:
                import boto3 as _boto3

                client = _boto3.client("s3", region_name=cfg.aws_region)
            start = time.perf_counter()
            client.head_bucket(Bucket=bucket)
            return round((time.perf_counter() - start) * 1000, 1)
        except Exception as exc:
            logger.debug("S3/MinIO probe failed: {}", exc)
            return None

    def _s3_reachable(self) -> Optional[bool]:
        try:
            from ..config import get_config

            if not (get_config().s3_journey_logs_bucket or get_config().s3_journey_reports_bucket):
                return None
        except Exception:
            return None
        return self._s3_probe_ms() is not None

    def _health_uptime_pct(self, _window_hours: int) -> float:
        return 100.0

    def _ready_ratio(self) -> Optional[float]:
        try:
            from .worker_management_service import get_worker_management_service

            svc = get_worker_management_service()
            worker = svc._deployment_status()
            desired = int(worker.get("desired") or 0)
            ready = int(worker.get("ready") or 0)
            api_desired, api_ready = self._api_deployment_ready()
            total_desired = desired + api_desired
            total_ready = ready + api_ready
            if total_desired <= 0:
                return 100.0
            return round(100.0 * total_ready / total_desired, 1)
        except Exception:
            return 100.0

    def _api_deployment_ready(self) -> Tuple[int, int]:
        try:
            from .worker_management_service import get_worker_management_service

            svc = get_worker_management_service()
            if not svc.k8s_available or svc._apps_api is None:
                return 1, 1
            from kubernetes import client

            name = f"{os.getenv('CAPABILITY_NAME', 'ai-engine')}-{os.getenv('ENVIRONMENT', 'dev')}-api"
            ns = os.getenv("KUBERNETES_NAMESPACE") or os.getenv("POD_NAMESPACE") or f"{os.getenv('CAPABILITY_NAME', 'ai-engine')}-{os.getenv('ENVIRONMENT', 'dev')}"
            dep = svc._apps_api.read_namespaced_deployment(name=name, namespace=ns)
            status = dep.status or client.V1DeploymentStatus()
            spec = dep.spec or client.V1DeploymentSpec()
            return int(spec.replicas or 0), int(status.ready_replicas or 0)
        except Exception:
            return 1, 1

    def _pod_restart_count(self) -> Optional[float]:
        try:
            from .worker_management_service import get_worker_management_service

            pods = get_worker_management_service()._list_worker_pods()
            return float(sum(int(p.get("restarts") or 0) for p in pods))
        except Exception:
            return None

    def _queue_lag_ratio_pct(self) -> Optional[float]:
        try:
            from .job_execution_config_service import get_job_execution_config
            from .job_queue_service import get_waiting_count
            from .worker_management_service import two_wave_lag_count

            waiting = get_waiting_count()
            horizon = two_wave_lag_count(get_job_execution_config().get_worker_threads())
            return round(100.0 * waiting / max(horizon, 1), 1)
        except Exception:
            return None

    async def _job_metrics(self, hours: int) -> Dict[str, Any]:
        runtime = getattr(self._engine, "execution_runtime", None)
        if runtime is None:
            return {"throughput": {"submitted": 0, "succeeded": 0, "failed": 0}}
        try:
            from ..fleet.service import FleetMonitorService

            return await FleetMonitorService(runtime=runtime).metrics(window=f"{hours}h")
        except Exception as exc:
            logger.debug("Fleet job metrics failed: {}", exc)
            return {"throughput": {"submitted": 0, "succeeded": 0, "failed": 0}}

    @staticmethod
    def _auth_method() -> str:
        if os.getenv("OIDC_ISSUER") or os.getenv("COGNITO_USER_POOL_ID"):
            return "OIDC"
        return "Local"

    @staticmethod
    def _tls_status() -> Tuple[bool, float]:
        env = os.getenv("ENVIRONMENT", "dev")
        tls_flag = os.getenv("TLS", os.getenv("HTTPS", "false")).lower() in ("1", "true", "yes")
        enabled = env == "prod" or tls_flag
        return enabled, 100.0 if enabled else 90.0

    @staticmethod
    def _retention_keep() -> int:
        try:
            from ..stages.job_archival import archive_limits

            keep, _ = archive_limits()
            return keep
        except Exception:
            return int(os.getenv("JOB_ARCHIVE_KEEP", "1000"))

    def _write_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._write_memory(snapshot)
        self._write_redis(snapshot)
        try:
            self._ensure_table()
            if self._table is None:
                return
            now = datetime.now(timezone.utc)
            item = {
                "PK": f"sla#{now.strftime('%Y-%m-%d')}",
                "SK": now.isoformat(),
                "timestamp": now.isoformat(),
                "window_hours": snapshot.get("window_hours", 1),
                "overall_score": self._convert_floats(snapshot.get("overall_score")),
                "overall_status": snapshot.get("overall_status", "unknown"),
                "pillars": self._convert_floats(snapshot.get("pillars", {})),
                "ttl": int((now + timedelta(days=30)).timestamp()),
            }
            self._table.put_item(Item=item)
        except Exception as exc:
            logger.warning("SLA snapshot write failed: {}", exc)

    def _write_memory(self, snapshot: Dict[str, Any]) -> None:
        with self._memory_lock:
            self._memory.append(dict(snapshot))

    def _write_redis(self, snapshot: Dict[str, Any]) -> None:
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            client.lpush(REDIS_SNAPSHOT_KEY, json.dumps(snapshot, default=str))
            client.ltrim(REDIS_SNAPSHOT_KEY, 0, MEMORY_SNAPSHOT_LIMIT - 1)
        except Exception as exc:
            logger.debug("SLA Redis snapshot write skipped: {}", exc)

    def _read_latest_snapshot(self, window_hours: int = 1) -> Optional[Dict[str, Any]]:
        snap = self._read_latest_dynamo(window_hours)
        if snap:
            return snap
        snap = self._read_latest_redis(window_hours)
        if snap:
            return snap
        return self._read_latest_memory(window_hours)

    def _read_latest_dynamo(self, window_hours: int) -> Optional[Dict[str, Any]]:
        try:
            self._ensure_table()
            if self._table is None:
                return None
            now = datetime.now(timezone.utc)
            for day_offset in range(2):
                date_key = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                resp = self._table.query(
                    KeyConditionExpression=Key("PK").eq(f"sla#{date_key}"),
                    ScanIndexForward=False,
                    Limit=5,
                )
                for item in resp.get("Items") or []:
                    snap = self._deserialize_snapshot(item)
                    if int(snap.get("window_hours") or 1) == window_hours:
                        return snap
                if resp.get("Items"):
                    return self._deserialize_snapshot(resp["Items"][0])
            return None
        except Exception as exc:
            logger.debug("SLA snapshot read failed: {}", exc)
            return None

    def _read_latest_redis(self, window_hours: int) -> Optional[Dict[str, Any]]:
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return None
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            raw_items = client.lrange(REDIS_SNAPSHOT_KEY, 0, 20)
            for raw in raw_items:
                snap = json.loads(raw)
                if int(snap.get("window_hours") or 1) == window_hours:
                    return snap
            if raw_items:
                return json.loads(raw_items[0])
            return None
        except Exception:
            return None

    def _read_latest_memory(self, window_hours: int) -> Optional[Dict[str, Any]]:
        with self._memory_lock:
            for snap in reversed(self._memory):
                if int(snap.get("window_hours") or 1) == window_hours:
                    return snap
            return self._memory[-1] if self._memory else None

    def _read_timeline(self, hours: int) -> List[Dict[str, Any]]:
        points = self._timeline_from_dynamo(hours)
        if points:
            return points
        points = self._timeline_from_redis(hours)
        if points:
            return points
        return self._timeline_from_memory(hours)

    def _timeline_from_dynamo(self, hours: int) -> List[Dict[str, Any]]:
        try:
            self._ensure_table()
            if self._table is None:
                return []
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=hours)
            points: List[Dict[str, Any]] = []
            days = max(1, (hours // 24) + 1)
            for day_offset in range(days + 1):
                date_key = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
                resp = self._table.query(
                    KeyConditionExpression=Key("PK").eq(f"sla#{date_key}"),
                    ScanIndexForward=True,
                )
                for item in resp.get("Items") or []:
                    ts = item.get("timestamp") or item.get("SK", "")
                    if ts < cutoff.isoformat():
                        continue
                    points.append(self._timeline_point(self._deserialize_snapshot(item), ts))
            points.sort(key=lambda p: p["timestamp"])
            return points
        except Exception as exc:
            logger.debug("SLA timeline read failed: {}", exc)
            return []

    def _timeline_from_redis(self, hours: int) -> List[Dict[str, Any]]:
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return []
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            points = []
            for raw in client.lrange(REDIS_SNAPSHOT_KEY, 0, MEMORY_SNAPSHOT_LIMIT):
                snap = json.loads(raw)
                ts = snap.get("timestamp") or ""
                if ts < cutoff:
                    continue
                points.append(self._timeline_point(snap, ts))
            points.sort(key=lambda p: p["timestamp"])
            return points
        except Exception:
            return []

    def _timeline_from_memory(self, hours: int) -> List[Dict[str, Any]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._memory_lock:
            points = [
                self._timeline_point(snap, snap.get("timestamp") or "")
                for snap in self._memory
                if (snap.get("timestamp") or "") >= cutoff
            ]
        points.sort(key=lambda p: p["timestamp"])
        return points

    def _pillar_timeline(self, pillar: str, hours: int) -> List[Dict[str, Any]]:
        timeline = self._read_timeline(hours)
        return [
            {
                "timestamp": p["timestamp"],
                "score": (p.get("pillars") or {}).get(pillar),
                "status": status_from_score((p.get("pillars") or {}).get(pillar)),
            }
            for p in timeline
        ]

    @staticmethod
    def _timeline_point(snap: Dict[str, Any], ts: str) -> Dict[str, Any]:
        pillar_scores = {
            name: (snap.get("pillars") or {}).get(name, {}).get("score")
            for name in PILLAR_IDS
        }
        return {
            "timestamp": ts,
            "overall_score": snap.get("overall_score"),
            "overall_status": snap.get("overall_status"),
            "pillars": pillar_scores,
        }

    def _deserialize_snapshot(self, item: Dict[str, Any]) -> Dict[str, Any]:
        pillars = item.get("pillars") or {}
        if isinstance(pillars, dict):
            pillars = self._floatify(pillars)
        overall = item.get("overall_score")
        if isinstance(overall, Decimal):
            overall = float(overall)
        return {
            "window_hours": int(item.get("window_hours") or 1),
            "timestamp": item.get("timestamp") or item.get("SK"),
            "overall_score": overall,
            "overall_status": item.get("overall_status", "unknown"),
            "pillars": pillars,
        }

    @staticmethod
    def _convert_floats(obj: Any) -> Any:
        if isinstance(obj, float):
            return Decimal(str(round(obj, 4)))
        if isinstance(obj, dict):
            return {k: SlaMonitoringService._convert_floats(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SlaMonitoringService._convert_floats(i) for i in obj]
        return obj

    @staticmethod
    def _floatify(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: SlaMonitoringService._floatify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SlaMonitoringService._floatify(i) for i in obj]
        return obj


_service: Optional[SlaMonitoringService] = None


def get_sla_monitoring_service() -> SlaMonitoringService:
    global _service
    if _service is None:
        _service = SlaMonitoringService()
    return _service
