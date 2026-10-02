"""Infrastructure diagnostics for Operations → Diagnostics → Infra."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

from ..config import get_config
from ..stages.job_archival import ARCHIVE_TABLE_NAME, archive_bucket_name

_STARTED = time.time()
CATEGORIES = ("frontend", "backend", "dynamodb", "s3", "glue-athena", "redis")


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


class OverallStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    status: CheckStatus
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        row = {
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "message": self.message,
            "details": self.details,
        }
        if self.error:
            row["error"] = self.error
        return row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client(service: str):
    from ..adapters.aws.client_manager import AWSClientManager

    return AWSClientManager(region_name=None).create_client(service)


def _resource(service: str):
    from ..adapters.aws.client_manager import AWSClientManager

    return AWSClientManager(region_name=None).create_resource(service)


def _overall(checks: Dict[str, CheckResult]) -> OverallStatus:
    statuses = [c.status for c in checks.values()]
    if not statuses:
        return OverallStatus.DEGRADED
    if all(s in (CheckStatus.PASS, CheckStatus.SKIPPED) for s in statuses):
        return OverallStatus.HEALTHY
    if any(s == CheckStatus.FAIL for s in statuses):
        return OverallStatus.UNHEALTHY
    return OverallStatus.DEGRADED


def _pack(checks: Dict[str, CheckResult]) -> Dict[str, Any]:
    return {
        "status": _overall(checks).value,
        "timestamp": _now_iso(),
        "checks": {k: v.to_dict() for k, v in checks.items()},
    }


class InfraDiagnosticsService:
    def _frontend_base_url(self) -> str:
        cfg = get_config()
        cap = cfg.capability_name or os.getenv("CAPABILITY_NAME", "ai-engine")
        env = cfg.environment or os.getenv("ENVIRONMENT", "local")
        return os.getenv("FRONTEND_INTERNAL_URL") or f"http://{cap}-{env}-frontend-svc:8080"

    def _engine_tables(self) -> List[Tuple[str, Optional[str]]]:
        cfg = get_config()
        env = cfg.environment or os.getenv("ENVIRONMENT", "local")
        return [
            ("journeys", cfg.dynamodb_transformation_table),
            ("executions", cfg.dynamodb_executions_table),
            ("prompts", cfg.dynamodb_prompts_table),
            ("sla", f"ai-engine-{env}-sla-snapshots"),
        ]

    def _engine_buckets(self) -> List[Tuple[str, Optional[str]]]:
        cfg = get_config()
        return [
            ("logs", cfg.s3_journey_logs_bucket),
            ("reports", cfg.s3_journey_reports_bucket or archive_bucket_name(cfg)),
        ]

    async def run_all(self) -> Dict[str, Any]:
        checks: Dict[str, CheckResult] = {}
        for name, fn in self._all_checks():
            checks[name] = await self._run(fn)
        return _pack(checks)

    async def run_category(self, category: str) -> Dict[str, Any]:
        mapping = {
            "frontend": [
                ("frontend_serving", self.check_frontend_serving),
                ("frontend_backend_proxy", self.check_frontend_backend_proxy),
                ("frontend_config", self.check_frontend_config),
            ],
            "backend": [
                ("backend_uptime", self.check_backend_uptime),
                ("iam_identity", self.check_iam_identity),
                ("worker_pool", self.check_worker_pool),
                ("ssm_access", self.check_ssm_access),
                ("secrets_manager_access", self.check_secrets_manager_access),
            ],
            "dynamodb": [("dynamodb_tables", self.check_dynamodb_tables)],
            "s3": [("s3_buckets", self.check_s3_buckets)],
            "glue-athena": [
                ("glue_catalog", self.check_glue_catalog),
                ("athena_query", self.check_athena_workgroup),
            ],
            "redis": [
                ("redis_ping", self.check_redis_ping),
                ("redis_memory", self.check_redis_memory),
            ],
        }
        pairs = mapping.get(category)
        if not pairs:
            raise ValueError(f"Unknown category: {category}")
        checks = {name: await self._run(fn) for name, fn in pairs}
        return _pack(checks)

    def _all_checks(self) -> List[Tuple[str, Callable[[], CheckResult]]]:
        return [
            ("frontend_serving", self.check_frontend_serving),
            ("frontend_backend_proxy", self.check_frontend_backend_proxy),
            ("frontend_config", self.check_frontend_config),
            ("backend_uptime", self.check_backend_uptime),
            ("iam_identity", self.check_iam_identity),
            ("worker_pool", self.check_worker_pool),
            ("ssm_access", self.check_ssm_access),
            ("secrets_manager_access", self.check_secrets_manager_access),
            ("dynamodb_tables", self.check_dynamodb_tables),
            ("s3_buckets", self.check_s3_buckets),
            ("glue_catalog", self.check_glue_catalog),
            ("athena_query", self.check_athena_workgroup),
            ("redis_ping", self.check_redis_ping),
            ("redis_memory", self.check_redis_memory),
        ]

    async def _run(self, fn: Callable[[], CheckResult]) -> CheckResult:
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn), timeout=35)
        except asyncio.TimeoutError:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=35000, message="Check timed out after 35s", error="TimeoutError")
        except Exception as exc:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=0, message=f"Unexpected error: {exc}", error=str(exc))

    def check_frontend_serving(self) -> CheckResult:
        start = time.time()
        url = self._frontend_base_url()
        try:
            body = urllib.request.urlopen(urllib.request.Request(f"{url}/"), timeout=5).read().decode()[:500]
            html = "<html" in body.lower() or "<!doctype" in body.lower()
            return CheckResult(
                status=CheckStatus.PASS if html else CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message="Frontend serving HTML" if html else "Frontend responded but not HTML",
                details={"url": f"{url}/"},
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="Frontend not reachable",
                error=str(exc),
                details={"url": f"{url}/"},
            )

    def check_frontend_backend_proxy(self) -> CheckResult:
        start = time.time()
        url = f"{self._frontend_base_url()}/health"
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url), timeout=5)
            data = json.loads(resp.read().decode()[:800])
            ok = data.get("status") == "ok"
            return CheckResult(
                status=CheckStatus.PASS if ok else CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message="Frontend proxy to backend /health OK" if ok else "Proxy reached backend but status is not ok",
                details={"url": url, "http_status": resp.status, "backend_status": data.get("status")},
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="Backend proxy through frontend failed",
                error=str(exc),
            )

    def check_frontend_config(self) -> CheckResult:
        start = time.time()
        url = f"{self._frontend_base_url()}/config.json"
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url), timeout=5)
            body = resp.read().decode()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            stripped = body.lstrip()
            # Journey Studio is same-origin /api; nginx try_files falls back to index.html.
            if ctype.startswith("text/html") or stripped.startswith("<"):
                return CheckResult(
                    status=CheckStatus.PASS,
                    latency_ms=(time.time() - start) * 1000,
                    message="Runtime config.json not used (same-origin /api)",
                    details={"url": url, "served": False, "content_type": ctype or "html-fallback"},
                )
            data = json.loads(body)
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message="Frontend config.json valid",
                details={"keys": list(data.keys()) if isinstance(data, dict) else [], "served": True},
            )
        except json.JSONDecodeError:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=(time.time() - start) * 1000, message="config.json is not valid JSON")
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message="config.json not served (optional for this UI)",
                error=str(exc),
            )

    def check_backend_uptime(self) -> CheckResult:
        uptime_s = time.time() - _STARTED
        return CheckResult(
            status=CheckStatus.PASS,
            latency_ms=0,
            message=f"Backend running, uptime {int(uptime_s)}s",
            details={"uptime_seconds": round(uptime_s, 1), "python_version": platform.python_version()},
        )

    def check_iam_identity(self) -> CheckResult:
        start = time.time()
        try:
            cfg = get_config()
            identity = _client("sts").get_caller_identity()
            arn = identity.get("Arn", "")
            expected = f"{cfg.capability_name}-{cfg.environment}"
            match = expected in arn
            return CheckResult(
                status=CheckStatus.PASS if match else CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message=f"IAM identity: {arn}" if match else f"STS reachable (ARN does not include {expected})",
                details={"arn": arn, "account": identity.get("Account"), "expected_pattern": expected, "match": match},
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="Failed to get IAM identity",
                error=str(exc),
            )

    def check_worker_pool(self) -> CheckResult:
        start = time.time()
        try:
            from .worker_management_service import get_worker_management_service

            stats = get_worker_management_service().get_summary()
            ready = int((stats.get("deployment") or {}).get("ready") or 0)
            consumers = int(stats.get("consumers") or 0)
            ok = ready > 0 or consumers > 0
            return CheckResult(
                status=CheckStatus.PASS if ok else CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message=f"Workers ready={ready}, consumers={consumers}",
                details=stats,
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="Failed to check job workers",
                error=str(exc),
            )

    def check_ssm_access(self) -> CheckResult:
        start = time.time()
        cfg = get_config()
        prefix = os.getenv("SSM_PARAMETER_PREFIX") or f"/ai-engine/{cfg.environment}/"
        try:
            ssm = _client("ssm")
            resp = ssm.get_parameters_by_path(Path=prefix, MaxResults=1)
            count = len(resp.get("Parameters") or [])
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message=f"SSM reachable under {prefix} ({count} param shown)",
                details={"prefix": prefix, "count": count},
            )
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") if hasattr(exc, "response") else ""
            if code in ("ParameterNotFound", "AccessDeniedException"):
                return CheckResult(
                    status=CheckStatus.WARNING,
                    latency_ms=(time.time() - start) * 1000,
                    message=f"SSM API responded ({code})",
                    details={"prefix": prefix},
                )
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="SSM Parameter Store not accessible",
                error=str(exc),
            )

    def check_secrets_manager_access(self) -> CheckResult:
        start = time.time()
        try:
            sm = _client("secretsmanager")
            resp = sm.list_secrets(MaxResults=1)
            count = len(resp.get("SecretList") or [])
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message="Secrets Manager API reachable",
                details={"listed": count},
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message="Secrets Manager not required for this engine",
                error=str(exc),
            )

    def check_dynamodb_tables(self) -> CheckResult:
        start = time.time()
        tables_detail: Dict[str, Any] = {}
        any_fail = False
        configured = 0
        try:
            dynamodb = _resource("dynamodb")
        except Exception as exc:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=(time.time() - start) * 1000, message="DynamoDB client failed", error=str(exc))

        for label, name in self._engine_tables():
            entry: Dict[str, Any] = {"table_name": name}
            t0 = time.time()
            if not name:
                entry.update({"exists": False, "readable": False, "writable": False, "status": "not_configured"})
                tables_detail[label] = entry
                continue
            configured += 1
            try:
                table = dynamodb.Table(name)
                table.load()
                entry["exists"] = True
                entry["table_status"] = table.table_status
                table.scan(Limit=1, Select="COUNT")
                entry["readable"] = True
                key_schema = table.key_schema or []
                diag_key: Dict[str, Any] = {}
                for ks in key_schema:
                    diag_key[ks["AttributeName"]] = "DIAG#test" if ks["KeyType"] == "HASH" else f"DIAG#{int(time.time() * 1000)}"
                table.put_item(Item={**diag_key, "_diag": True})
                table.delete_item(Key=diag_key)
                entry["writable"] = True
                entry["status"] = "pass"
            except Exception as exc:
                entry.update({"readable": entry.get("readable", False), "writable": False, "status": "fail", "error": str(exc)[:300]})
                any_fail = True
            entry["latency_ms"] = round((time.time() - t0) * 1000, 1)
            tables_detail[label] = entry

        passed = sum(1 for v in tables_detail.values() if v.get("status") == "pass")
        if any_fail:
            status = CheckStatus.FAIL
            msg = f"DynamoDB failures: {', '.join(k for k, v in tables_detail.items() if v.get('status') == 'fail')}"
        elif passed == configured and configured:
            status = CheckStatus.PASS
            msg = f"All {configured} engine tables: read+write OK"
        else:
            status = CheckStatus.WARNING
            msg = "Some engine tables are not configured"
        return CheckResult(status=status, latency_ms=(time.time() - start) * 1000, message=msg, details={"tables": tables_detail})

    def check_s3_buckets(self) -> CheckResult:
        start = time.time()
        try:
            s3 = _client("s3")
        except Exception as exc:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=(time.time() - start) * 1000, message="S3 client failed", error=str(exc))
        buckets_detail: Dict[str, Any] = {}
        any_fail = False
        configured = 0
        for label, bucket in self._engine_buckets():
            entry: Dict[str, Any] = {"bucket": bucket}
            if not bucket:
                entry.update({"exists": False, "read_access": False, "write_access": False, "status": "not_configured"})
                buckets_detail[label] = entry
                continue
            configured += 1
            try:
                s3.head_bucket(Bucket=bucket)
                entry["exists"] = True
                key = f"_diagnostics_test/{uuid.uuid4()}.txt"
                s3.put_object(Bucket=bucket, Key=key, Body=b"ai-engine infra diagnostic")
                entry["write_access"] = True
                s3.get_object(Bucket=bucket, Key=key)
                entry["read_access"] = True
                s3.delete_object(Bucket=bucket, Key=key)
                entry["status"] = "pass"
            except Exception as exc:
                entry.setdefault("exists", False)
                entry.setdefault("read_access", False)
                entry.setdefault("write_access", False)
                entry["status"] = "fail"
                entry["error"] = str(exc)[:300]
                any_fail = True
            buckets_detail[label] = entry
        passed = sum(1 for v in buckets_detail.values() if v.get("status") == "pass")
        if any_fail:
            status = CheckStatus.FAIL
            msg = f"S3 failures: {', '.join(k for k, v in buckets_detail.items() if v.get('status') == 'fail')}"
        elif passed == configured and configured:
            status = CheckStatus.PASS
            msg = f"All {configured} engine buckets: read+write OK"
        else:
            status = CheckStatus.WARNING
            msg = "Some engine buckets are not configured"
        return CheckResult(status=status, latency_ms=(time.time() - start) * 1000, message=msg, details={"buckets": buckets_detail})

    def check_glue_catalog(self) -> CheckResult:
        start = time.time()
        from ..resource_naming import resolved_glue_database

        database = resolved_glue_database()
        details: Dict[str, Any] = {"database": database, "table": ARCHIVE_TABLE_NAME}
        try:
            glue = _client("glue")
            glue.get_database(Name=database)
            details["database_exists"] = True
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message=f"Glue database '{database}' not reachable",
                error=str(exc),
                details=details,
            )
        try:
            raw = glue.get_table(DatabaseName=database, Name=ARCHIVE_TABLE_NAME)["Table"]
            details["table_exists"] = True
            details["table_location"] = (raw.get("StorageDescriptor") or {}).get("Location")
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message=f"Glue catalog OK: {database}.{ARCHIVE_TABLE_NAME}",
                details=details,
            )
        except Exception as exc:
            details["table_exists"] = False
            return CheckResult(
                status=CheckStatus.WARNING,
                latency_ms=(time.time() - start) * 1000,
                message=f"Glue table '{ARCHIVE_TABLE_NAME}' not registered yet",
                error=str(exc),
                details=details,
            )

    def check_athena_workgroup(self) -> CheckResult:
        start = time.time()
        workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
        details: Dict[str, Any] = {"workgroup": workgroup}
        try:
            athena = _client("athena")
            wg = athena.get_work_group(WorkGroup=workgroup)
            details["state"] = (wg.get("WorkGroup") or {}).get("State")
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message=f"Athena workgroup '{workgroup}' reachable",
                details=details,
            )
        except Exception as exc:
            return CheckResult(
                status=CheckStatus.FAIL,
                latency_ms=(time.time() - start) * 1000,
                message="Athena workgroup check failed",
                error=str(exc),
                details=details,
            )

    def check_redis_ping(self) -> CheckResult:
        start = time.time()
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return CheckResult(status=CheckStatus.SKIPPED, latency_ms=(time.time() - start) * 1000, message="Redis not configured")
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            ms = round((time.time() - start) * 1000, 2)
            return CheckResult(status=CheckStatus.PASS, latency_ms=ms, message=f"Redis PING OK ({ms} ms)", details={"redis_url": REDIS_URL, "ping_ms": ms})
        except Exception as exc:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=(time.time() - start) * 1000, message="Redis unreachable", error=str(exc))

    def check_redis_memory(self) -> CheckResult:
        start = time.time()
        try:
            from .job_queue_service import REDIS_URL, redis_available, redis_sync

            if not redis_available() or redis_sync is None:
                return CheckResult(status=CheckStatus.SKIPPED, latency_ms=(time.time() - start) * 1000, message="Redis not configured")
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            info = client.info("memory") or {}
            used = info.get("used_memory_human")
            return CheckResult(
                status=CheckStatus.PASS,
                latency_ms=(time.time() - start) * 1000,
                message=f"Redis memory OK ({used or '?'})",
                details={"used_memory_human": used, "maxmemory_human": info.get("maxmemory_human"), "redis_url": REDIS_URL},
            )
        except Exception as exc:
            return CheckResult(status=CheckStatus.FAIL, latency_ms=(time.time() - start) * 1000, message="Could not read Redis memory info", error=str(exc))


_service: Optional[InfraDiagnosticsService] = None


def get_infra_diagnostics_service() -> InfraDiagnosticsService:
    global _service
    if _service is None:
        _service = InfraDiagnosticsService()
    return _service
