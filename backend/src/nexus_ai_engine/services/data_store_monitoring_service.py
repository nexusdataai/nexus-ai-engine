"""DynamoDB and Athena/Glue monitoring for Operations → Infra."""

from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, DefaultDict, Deque, Dict, Iterable, List, Optional, Tuple

from loguru import logger

from ..config import get_config
from ..stages.job_archival import ARCHIVE_TABLE_NAME, archive_bucket_name

DYNAMO_SNAPSHOT_KEY = "ai-engine:dynamo-snapshots"
ATHENA_SNAPSHOT_KEY = "ai-engine:athena-snapshots"
MEMORY_LIMIT = 900
WINDOWS: Dict[str, Tuple[int, str, int]] = {
    "1h": (1, "minute", 60),
    "24h": (24, "hour", 300),
    "7d": (168, "hour", 3600),
}
ATHENA_WRITE_PREFIXES = ("INSERT", "CREATE", "UNLOAD", "UPDATE", "DELETE", "MERGE", "ALTER", "DROP", "MSCK")
ATHENA_READ_PREFIXES = ("SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "WITH")

_dynamo_memory: Deque[Dict[str, Any]] = deque(maxlen=MEMORY_LIMIT)
_athena_memory: Deque[Dict[str, Any]] = deque(maxlen=MEMORY_LIMIT)
_lock = Lock()


def _bytes_human(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    return f"{value:.2f}{units[idx]}"


def _client(service: str):
    from ..adapters.aws.client_manager import AWSClientManager

    return AWSClientManager(region_name=None).create_client(service)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if hasattr(raw, "isoformat"):
        dt = raw
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    text = str(raw).strip()
    return text or None


def _parse_ts(raw: Any) -> Optional[datetime]:
    text = _iso(raw)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _window_spec(window: str) -> Tuple[int, str, int]:
    return WINDOWS.get(window, WINDOWS["1h"])


def _redis_list_write(key: str, point: Dict[str, Any], memory: Deque[Dict[str, Any]]) -> None:
    with _lock:
        memory.append(point)
    try:
        from .job_queue_service import REDIS_URL, redis_available, redis_sync

        if redis_available() and redis_sync is not None:
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            client.lpush(key, json.dumps(point))
            client.ltrim(key, 0, MEMORY_LIMIT - 1)
    except Exception as exc:
        logger.debug("Data-store snapshot Redis write skipped: {}", exc)


def _redis_list_history(key: str, hours: float, memory: Deque[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = (_now() - timedelta(hours=hours)).isoformat()
    points: List[Dict[str, Any]] = []
    try:
        from .job_queue_service import REDIS_URL, redis_available, redis_sync

        if redis_available() and redis_sync is not None:
            client = redis_sync.from_url(REDIS_URL, decode_responses=True)
            for raw in client.lrange(key, 0, MEMORY_LIMIT):
                item = json.loads(raw)
                if (item.get("timestamp") or "") >= cutoff:
                    points.append(item)
    except Exception:
        pass
    if not points:
        with _lock:
            points = [dict(p) for p in memory if (p.get("timestamp") or "") >= cutoff]
    points.sort(key=lambda p: p.get("timestamp") or "")
    return points


def _cw_datapoints(
    cw,
    namespace: str,
    metric: str,
    start: datetime,
    end: datetime,
    period: int,
    stat: str,
    dimensions: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    if cw is None:
        return []
    try:
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dimensions,
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=[stat],
        )
        rows = []
        for item in resp.get("Datapoints") or []:
            ts = _iso(item.get("Timestamp"))
            value = item.get(stat)
            if ts is None or value is None:
                continue
            rows.append({"timestamp": ts, "value": float(value)})
        return rows
    except Exception as exc:
        logger.debug("CloudWatch {}/{} unavailable: {}", namespace, metric, exc)
        return []


def _merge_metric_points(
    buckets: DefaultDict[str, Dict[str, Any]],
    rows: Iterable[Dict[str, Any]],
    field: str,
    mode: str = "sum",
) -> None:
    for row in rows:
        ts = row.get("timestamp")
        if not ts:
            continue
        slot = buckets[ts]
        slot["timestamp"] = ts
        value = row.get("value")
        if value is None:
            continue
        if mode == "avg":
            count_key = f"_{field}_n"
            slot[field] = (slot.get(field) or 0) + float(value)
            slot[count_key] = (slot.get(count_key) or 0) + 1
        else:
            slot[field] = (slot.get(field) or 0) + float(value)


def _finalize_avg(points: List[Dict[str, Any]], fields: Iterable[str]) -> None:
    for point in points:
        for field in fields:
            count = point.pop(f"_{field}_n", None)
            if count:
                point[field] = round(float(point.get(field) or 0) / count, 3)


def _latest_numeric(points: List[Dict[str, Any]], field: str) -> Optional[float]:
    for point in reversed(points):
        value = point.get(field)
        if value is not None:
            return float(value)
    return None


def _table_last(points_by_table: Dict[str, Dict[str, List[Dict[str, Any]]]], name: str, field: str) -> Optional[float]:
    return _latest_numeric(points_by_table.get(name, {}).get(field, []), "value")


class DataStoreMonitoringService:
    def get_dynamodb_overview(self, window: str = "1h") -> Dict[str, Any]:
        hours, grain, period = _window_spec(window)
        cfg = get_config()
        env = cfg.environment or os.getenv("ENVIRONMENT", "local")
        region = cfg.aws_region
        tables = [
            {"id": "journeys", "label": "Journeys", "name": cfg.dynamodb_transformation_table},
            {"id": "executions", "label": "Executions", "name": cfg.dynamodb_executions_table},
            {"id": "prompts", "label": "Prompts", "name": cfg.dynamodb_prompts_table},
            {"id": "sla", "label": "SLA snapshots", "name": f"ai-engine-{env}-sla-snapshots"},
        ]
        start = _now()
        connected = False
        ping_ms: Optional[float] = None
        ping_message = "unavailable"
        rows: List[Dict[str, Any]] = []
        client = None
        try:
            client = _client("dynamodb")
            client.list_tables(Limit=1)
            ping_ms = round((_now() - start).total_seconds() * 1000, 2)
            connected = True
            ping_message = "ok"
            for spec in tables:
                rows.append(self._describe_table(client, spec))
        except Exception as exc:
            ping_message = str(exc)
            rows = [{**spec, "status": "unknown", "error": ping_message} for spec in tables]

        names = [row.get("name") for row in rows if row.get("name")]
        cw_points, per_table, cw_ok = self._dynamo_cloudwatch(names, hours, period)
        probe = self._dynamo_read_probe(client, names)
        current = self._record_dynamo_snapshot(cw_points, probe)
        history = self._dynamo_history(hours, cw_points, current)
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            row["read_rcu"] = _table_last(per_table, name, "read_rcu")
            row["write_wcu"] = _table_last(per_table, name, "write_wcu")
            row["read_latency_ms"] = _table_last(per_table, name, "read_latency_ms")
            row["write_latency_ms"] = _table_last(per_table, name, "write_latency_ms")

        read_rcu = _latest_numeric(history, "read_rcu")
        write_wcu = _latest_numeric(history, "write_wcu")
        read_latency = _latest_numeric(history, "read_latency_ms")
        write_latency = _latest_numeric(history, "write_latency_ms")
        if read_rcu is None:
            read_rcu = probe.get("read_rcu")
        if read_latency is None:
            read_latency = probe.get("read_latency_ms")
        source = "cloudwatch" if cw_ok else ("probe" if probe.get("read_latency_ms") is not None else "none")
        active = sum(1 for row in rows if row.get("status") == "ACTIVE")
        return {
            "connected": connected,
            "ping_ms": ping_ms,
            "ping_message": ping_message,
            "region": region,
            "window": window,
            "grain": grain,
            "table_total": len(tables),
            "tables_active": active,
            "tables": rows,
            "metrics_source": source,
            "kpis": [
                {"id": "read_rcu", "label": "Read capacity", "value": read_rcu, "unit": "RCU"},
                {"id": "write_wcu", "label": "Write capacity", "value": write_wcu, "unit": "WCU"},
                {"id": "read_latency", "label": "Read latency", "value": read_latency, "unit": "ms"},
                {"id": "write_latency", "label": "Write latency", "value": write_latency, "unit": "ms"},
            ],
            "points": history,
            "timestamp": _now().isoformat(),
        }

    def _describe_table(self, client, spec: Dict[str, Any]) -> Dict[str, Any]:
        name = spec.get("name")
        base = {**spec, "status": "not_configured", "item_count": None, "size_human": None, "gsi_count": 0}
        if not name:
            return base
        try:
            desc = client.describe_table(TableName=name)["Table"]
            billing = (desc.get("BillingModeSummary") or {}).get("BillingMode") or "PROVISIONED"
            return {
                **spec,
                "status": desc.get("TableStatus") or "unknown",
                "item_count": desc.get("ItemCount"),
                "size_bytes": desc.get("TableSizeBytes"),
                "size_human": _bytes_human(desc.get("TableSizeBytes")),
                "gsi_count": len(desc.get("GlobalSecondaryIndexes") or []),
                "billing_mode": billing,
            }
        except Exception as exc:
            logger.debug("DynamoDB describe {} failed: {}", name, exc)
            return {**base, "status": "missing", "error": str(exc)}

    def _dynamo_cloudwatch(
        self, tables: List[str], hours: int, period: int
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, List[Dict[str, Any]]]], bool]:
        per_table: Dict[str, Dict[str, List[Dict[str, Any]]]] = {name: {} for name in tables}
        buckets: DefaultDict[str, Dict[str, Any]] = defaultdict(dict)
        try:
            cw = _client("cloudwatch")
        except Exception:
            cw = None
        end = _now()
        start = end - timedelta(hours=hours)
        found = False
        for name in tables:
            if not name:
                continue
            dims = [{"Name": "TableName", "Value": name}]
            read = _cw_datapoints(cw, "AWS/DynamoDB", "ConsumedReadCapacityUnits", start, end, period, "Sum", dims)
            write = _cw_datapoints(cw, "AWS/DynamoDB", "ConsumedWriteCapacityUnits", start, end, period, "Sum", dims)
            read_lat = _cw_datapoints(
                cw,
                "AWS/DynamoDB",
                "SuccessfulRequestLatency",
                start,
                end,
                period,
                "Average",
                dims + [{"Name": "Operation", "Value": "GetItem"}],
            )
            if not read_lat:
                read_lat = _cw_datapoints(
                    cw,
                    "AWS/DynamoDB",
                    "SuccessfulRequestLatency",
                    start,
                    end,
                    period,
                    "Average",
                    dims + [{"Name": "Operation", "Value": "Query"}],
                )
            write_lat = _cw_datapoints(
                cw,
                "AWS/DynamoDB",
                "SuccessfulRequestLatency",
                start,
                end,
                period,
                "Average",
                dims + [{"Name": "Operation", "Value": "PutItem"}],
            )
            per_table[name] = {
                "read_rcu": read,
                "write_wcu": write,
                "read_latency_ms": read_lat,
                "write_latency_ms": write_lat,
            }
            if read or write or read_lat or write_lat:
                found = True
            _merge_metric_points(buckets, read, "read_rcu")
            _merge_metric_points(buckets, write, "write_wcu")
            _merge_metric_points(buckets, read_lat, "read_latency_ms", "avg")
            _merge_metric_points(buckets, write_lat, "write_latency_ms", "avg")
        points = [buckets[key] for key in sorted(buckets)]
        _finalize_avg(points, ("read_latency_ms", "write_latency_ms"))
        for point in points:
            if point.get("read_rcu") is not None:
                point["read_rcu"] = round(float(point["read_rcu"]), 3)
            if point.get("write_wcu") is not None:
                point["write_wcu"] = round(float(point["write_wcu"]), 3)
        return points, per_table, found

    def _dynamo_read_probe(self, client, tables: List[str]) -> Dict[str, Any]:
        probe = {"read_rcu": None, "read_latency_ms": None}
        if client is None:
            return probe
        name = next((item for item in tables if item), None)
        if not name:
            return probe
        try:
            start = _now()
            resp = client.scan(TableName=name, Limit=1, ReturnConsumedCapacity="TOTAL")
            probe["read_latency_ms"] = round((_now() - start).total_seconds() * 1000, 2)
            consumed = resp.get("ConsumedCapacity") or {}
            units = consumed.get("CapacityUnits")
            if units is not None:
                probe["read_rcu"] = float(units)
        except Exception as exc:
            logger.debug("DynamoDB read probe failed: {}", exc)
        return probe

    def _record_dynamo_snapshot(
        self, cw_points: List[Dict[str, Any]], probe: Dict[str, Any]
    ) -> Dict[str, Any]:
        latest = cw_points[-1] if cw_points else {}
        point = {
            "timestamp": _now().isoformat(),
            "read_rcu": latest.get("read_rcu") if latest.get("read_rcu") is not None else probe.get("read_rcu"),
            "write_wcu": latest.get("write_wcu"),
            "read_latency_ms": latest.get("read_latency_ms")
            if latest.get("read_latency_ms") is not None
            else probe.get("read_latency_ms"),
            "write_latency_ms": latest.get("write_latency_ms"),
        }
        _redis_list_write(DYNAMO_SNAPSHOT_KEY, point, _dynamo_memory)
        return point

    def _dynamo_history(
        self, hours: int, cw_points: List[Dict[str, Any]], current: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if cw_points:
            return cw_points
        history = _redis_list_history(DYNAMO_SNAPSHOT_KEY, hours, _dynamo_memory)
        if not history:
            history = [current]
        return [
            {
                "timestamp": item.get("timestamp"),
                "read_rcu": item.get("read_rcu"),
                "write_wcu": item.get("write_wcu"),
                "read_latency_ms": item.get("read_latency_ms"),
                "write_latency_ms": item.get("write_latency_ms"),
            }
            for item in history
        ]

    def get_athena_overview(self, window: str = "1h") -> Dict[str, Any]:
        cfg = get_config()
        from ..resource_naming import resolved_glue_database

        preferred_db = resolved_glue_database()
        workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
        archive_bucket = archive_bucket_name(cfg)
        start = datetime.now(timezone.utc)
        glue_ok = False
        athena_ok = False
        ping_ms: Optional[float] = None
        ping_message = "unavailable"
        database = preferred_db
        table: Dict[str, Any] = {
            "name": ARCHIVE_TABLE_NAME,
            "exists": False,
            "location": None,
            "partition_keys": [],
            "record_count": None,
            "partition_count": None,
            "partitions_truncated": False,
        }
        recent: List[Dict[str, Any]] = []
        hours, grain, period = _window_spec(window)
        try:
            glue = _client("glue")
            glue.get_databases(MaxResults=1)
            glue_ok = True
            discovered = self._discover_archive_database(glue, preferred_db)
            if discovered:
                database = discovered
            table = self._glue_table(glue, database)
            ping_ms = round((_now() - start).total_seconds() * 1000, 2)
            ping_message = "ok"
        except Exception as exc:
            ping_message = str(exc)
        try:
            athena = _client("athena")
            athena.get_work_group(WorkGroup=workgroup)
            athena_ok = True
            recent = self._recent_queries(athena, workgroup, limit=50)
            if ping_ms is None:
                ping_ms = round((_now() - start).total_seconds() * 1000, 2)
                ping_message = "ok"
        except Exception as exc:
            if not glue_ok:
                ping_message = str(exc)

        cw_points, cw_ok = self._athena_cloudwatch(workgroup, hours, period)
        query_points, scoped = self._athena_query_points(recent, hours)
        if query_points:
            points = query_points
            source = "athena_queries"
        elif cw_ok:
            points = cw_points
            scoped = "window"
            source = "cloudwatch"
        else:
            points = []
            source = "none"
        current = self._record_athena_snapshot(points)
        if not points:
            history = _redis_list_history(ATHENA_SNAPSHOT_KEY, hours, _athena_memory)
            points = history or [current]
        read_q = _latest_numeric(points, "read_queries")
        write_q = _latest_numeric(points, "write_queries")
        scanned = _latest_numeric(points, "bytes_scanned")
        engine = _latest_numeric(points, "avg_engine_ms")
        if query_points:
            read_q = sum(float(p.get("read_queries") or 0) for p in query_points)
            write_q = sum(float(p.get("write_queries") or 0) for p in query_points)
            scanned = sum(float(p.get("bytes_scanned") or 0) for p in query_points)
            samples = [p.get("avg_engine_ms") for p in query_points if p.get("avg_engine_ms") is not None]
            engine = round(sum(samples) / len(samples), 2) if samples else None
        return {
            "connected": glue_ok or athena_ok,
            "glue_reachable": glue_ok,
            "athena_reachable": athena_ok,
            "ping_ms": ping_ms,
            "ping_message": ping_message,
            "region": cfg.aws_region,
            "window": window,
            "grain": grain,
            "points_scope": scoped,
            "metrics_source": source,
            "database": database,
            "workgroup": workgroup,
            "archive_bucket": archive_bucket or None,
            "table": table,
            "recent_queries": recent[:10],
            "kpis": [
                {"id": "read_queries", "label": "Read queries", "value": read_q, "unit": "count"},
                {"id": "write_queries", "label": "Write queries", "value": write_q, "unit": "count"},
                {"id": "bytes_scanned", "label": "Data scanned", "value": scanned, "unit": "bytes"},
                {"id": "avg_engine_ms", "label": "Avg engine time", "value": engine, "unit": "ms"},
            ],
            "points": points,
            "timestamp": _now().isoformat(),
        }

    def _discover_archive_database(self, glue, preferred: str) -> Optional[str]:
        try:
            glue.get_table(DatabaseName=preferred, Name=ARCHIVE_TABLE_NAME)
            return preferred
        except Exception:
            pass
        try:
            for db_info in glue.get_databases().get("DatabaseList") or []:
                name = db_info.get("Name") or ""
                if not name:
                    continue
                try:
                    glue.get_table(DatabaseName=name, Name=ARCHIVE_TABLE_NAME)
                    return name
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Glue database discovery failed: {}", exc)
        return preferred

    def _glue_table(self, glue, database: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "name": ARCHIVE_TABLE_NAME,
            "database": database,
            "exists": False,
            "location": None,
            "partition_keys": [],
            "record_count": None,
            "partition_count": None,
            "partitions_truncated": False,
        }
        try:
            raw = glue.get_table(DatabaseName=database, Name=ARCHIVE_TABLE_NAME)["Table"]
            params = raw.get("Parameters") or {}
            keys = [k.get("Name") for k in (raw.get("PartitionKeys") or []) if k.get("Name")]
            info.update(
                {
                    "exists": True,
                    "location": (raw.get("StorageDescriptor") or {}).get("Location"),
                    "partition_keys": keys,
                    "record_count": _safe_int(params.get("recordCount") or params.get("numRows")),
                }
            )
        except Exception as exc:
            info["error"] = str(exc)
            return info
        try:
            parts = glue.get_partitions(DatabaseName=database, TableName=ARCHIVE_TABLE_NAME, MaxResults=100)
            info["partition_count"] = len(parts.get("Partitions") or [])
            info["partitions_truncated"] = bool(parts.get("NextToken"))
        except Exception:
            pass
        return info

    def _recent_queries(self, athena, workgroup: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            ids = (athena.list_query_executions(WorkGroup=workgroup, MaxResults=min(limit, 50)).get("QueryExecutionIds") or [])[:limit]
            for qid in ids:
                try:
                    qe = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
                    status = (qe.get("Status") or {})
                    stats = (qe.get("Statistics") or {})
                    submitted = _iso(status.get("SubmissionDateTime"))
                    scanned = stats.get("DataScannedInBytes")
                    statement = (qe.get("Query") or "").strip()
                    kind = _athena_statement_kind(statement)
                    rows.append(
                        {
                            "id": qid,
                            "state": status.get("State"),
                            "submitted": submitted,
                            "engine_ms": stats.get("EngineExecutionTimeInMillis")
                            or stats.get("TotalExecutionTimeInMillis"),
                            "bytes_scanned": scanned,
                            "bytes_scanned_human": _bytes_human(scanned),
                            "kind": kind,
                        }
                    )
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Athena recent queries unavailable: {}", exc)
        return rows

    def _athena_cloudwatch(self, workgroup: str, hours: int, period: int) -> Tuple[List[Dict[str, Any]], bool]:
        try:
            cw = _client("cloudwatch")
        except Exception:
            cw = None
        end = _now()
        start = end - timedelta(hours=hours)
        dims = [{"Name": "WorkGroup", "Value": workgroup}]
        processed = _cw_datapoints(cw, "AWS/Athena", "ProcessedBytes", start, end, period, "Sum", dims)
        engine = _cw_datapoints(cw, "AWS/Athena", "EngineExecutionTime", start, end, period, "Average", dims)
        total = _cw_datapoints(cw, "AWS/Athena", "TotalExecutionTime", start, end, period, "Average", dims)
        buckets: DefaultDict[str, Dict[str, Any]] = defaultdict(dict)
        _merge_metric_points(buckets, processed, "bytes_scanned")
        _merge_metric_points(buckets, engine or total, "avg_engine_ms", "avg")
        points = [buckets[key] for key in sorted(buckets)]
        _finalize_avg(points, ("avg_engine_ms",))
        found = bool(points)
        return points, found

    def _athena_query_points(self, queries: List[Dict[str, Any]], hours: int) -> Tuple[List[Dict[str, Any]], str]:
        cutoff = _now() - timedelta(hours=hours)
        in_window = []
        for row in queries:
            ts = _parse_ts(row.get("submitted"))
            if ts and ts >= cutoff:
                in_window.append(row)
        scoped = "window"
        chosen = in_window
        if not chosen:
            chosen = [row for row in queries if row.get("submitted")]
            scoped = "recent"
        buckets: DefaultDict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "read_queries": 0,
                "write_queries": 0,
                "bytes_scanned": 0,
                "engine_sum": 0.0,
                "engine_n": 0,
            }
        )
        for row in chosen:
            ts = _parse_ts(row.get("submitted"))
            if ts is None:
                continue
            if hours <= 1:
                key = ts.replace(second=0, microsecond=0).isoformat()
            elif hours <= 24:
                key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            else:
                key = ts.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            slot = buckets[key]
            slot["timestamp"] = key
            kind = row.get("kind")
            if kind == "write":
                slot["write_queries"] += 1
            elif kind == "read":
                slot["read_queries"] += 1
            scanned = row.get("bytes_scanned")
            if scanned is not None:
                slot["bytes_scanned"] += float(scanned)
            engine = row.get("engine_ms")
            if engine is not None:
                slot["engine_sum"] += float(engine)
                slot["engine_n"] += 1
        points = []
        for key in sorted(buckets):
            slot = buckets[key]
            engine_n = slot.pop("engine_n")
            engine_sum = slot.pop("engine_sum")
            slot["avg_engine_ms"] = round(engine_sum / engine_n, 2) if engine_n else None
            slot["bytes_scanned"] = round(slot["bytes_scanned"], 0)
            points.append(slot)
        return points, scoped

    def _record_athena_snapshot(self, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        latest = points[-1] if points else {}
        point = {
            "timestamp": _now().isoformat(),
            "read_queries": latest.get("read_queries"),
            "write_queries": latest.get("write_queries"),
            "bytes_scanned": latest.get("bytes_scanned"),
            "avg_engine_ms": latest.get("avg_engine_ms"),
        }
        _redis_list_write(ATHENA_SNAPSHOT_KEY, point, _athena_memory)
        return point


def _safe_int(raw: Any) -> Optional[int]:
    try:
        if raw is None or raw == "":
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _athena_statement_kind(statement: str) -> str:
    token = (statement or "").lstrip().split(" ", 1)[0].upper()
    if token in ATHENA_WRITE_PREFIXES:
        return "write"
    if token in ATHENA_READ_PREFIXES:
        return "read"
    return "other"


_service: Optional[DataStoreMonitoringService] = None


def get_data_store_monitoring_service() -> DataStoreMonitoringService:
    global _service
    if _service is None:
        _service = DataStoreMonitoringService()
    return _service


def record_data_store_snapshots() -> Dict[str, Any]:
    svc = get_data_store_monitoring_service()
    dynamo = svc.get_dynamodb_overview(window="1h")
    athena = svc.get_athena_overview(window="1h")
    return {
        "dynamo_points": len(dynamo.get("points") or []),
        "athena_points": len(athena.get("points") or []),
    }
