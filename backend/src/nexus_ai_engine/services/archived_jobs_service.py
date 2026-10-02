"""Search archived job rows via Athena when available, else S3/MinIO NDJSON."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..adapters.aws import AWSClientManager
from ..config import get_config
from ..stages.job_archival import ARCHIVE_TABLE_NAME, archive_bucket_name

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SAFE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def filter_archived_rows(
    rows: List[Dict[str, Any]],
    query: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """In-process filter for S3/MinIO NDJSON fallback (and unit tests)."""
    q = (query or "").strip()
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if q:
            job_id = str(row.get("job_id") or "")
            exec_n = str(row.get("execution_number") or "")
            if q.isdigit():
                if exec_n != q and q not in job_id:
                    continue
            elif q.lower() not in job_id.lower() and q != exec_n:
                continue
        start = str(row.get("start_time") or "")
        if date_from and start and start[:10] < date_from:
            continue
        if date_to and start and start[:10] > date_to:
            continue
        filtered.append(row)

    def _sort_key(row: Dict[str, Any]) -> Tuple[str, int]:
        try:
            exec_n = int(row.get("execution_number") or 0)
        except (TypeError, ValueError):
            exec_n = 0
        return (str(row.get("start_time") or ""), exec_n)

    filtered.sort(key=_sort_key, reverse=True)
    return filtered[: max(1, min(int(limit), 500))]


class ArchivedJobsService:
    def __init__(self) -> None:
        self._config = get_config()
        self._client_manager = AWSClientManager(region_name=None)
        self._s3 = self._client_manager.create_client("s3")
        self._archive_bucket = archive_bucket_name(self._config)
        self._logs_bucket = self._config.s3_journey_logs_bucket or os.getenv("S3_JOURNEY_LOGS_BUCKET") or ""
        self._prefix = "job-archive/"

    def search(
        self,
        query: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        jobs, source = self._try_athena(query, date_from, date_to, limit)
        if jobs is not None:
            return {"success": True, "jobs": jobs, "total": len(jobs), "source": source}
        jobs = self._scan_s3(query, date_from, date_to, limit)
        return {"success": True, "jobs": jobs, "total": len(jobs), "source": "s3"}

    def get_logs(self, job_id: str) -> Dict[str, Any]:
        row = self._resolve_archived_job(job_id)
        if not row:
            return {"success": False, "job_id": job_id, "steps": {}, "message": "Archived job not found"}
        journey_id = str(row.get("journey_id") or "")
        stage_id = str(row.get("stage_id") or "journey")
        if not journey_id:
            return {"success": False, "job_id": job_id, "steps": {}, "message": "Archive row missing journey_id"}
        if not self._logs_bucket:
            return {"success": False, "job_id": job_id, "steps": {}, "message": "Logs bucket is not configured"}

        prefix = f"journeys/{journey_id}/stages/{stage_id}/executions/{job_id}/logs/"
        steps: Dict[str, Any] = {}
        token: Optional[str] = None
        while True:
            kwargs: Dict[str, Any] = {"Bucket": self._logs_bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._s3.list_objects_v2(**kwargs)
            for obj in resp.get("Contents") or []:
                key = obj["Key"]
                step_name = key.rsplit("/", 1)[-1].replace(".json", "")
                body = self._s3.get_object(Bucket=self._logs_bucket, Key=key)["Body"].read().decode("utf-8")
                try:
                    steps[step_name] = json.loads(body)
                except json.JSONDecodeError:
                    steps[step_name] = []
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return {
            "success": True,
            "job_id": job_id,
            "journey_id": journey_id,
            "stage_id": stage_id,
            "steps": steps,
        }

    def _resolve_archived_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        result = self.search(query=job_id, limit=20)
        for row in result.get("jobs") or []:
            if str(row.get("job_id") or "") == job_id:
                return row
        return None

    def _try_athena(
        self,
        query: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int,
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        try:
            glue = self._client_manager.create_client("glue")
            athena = self._client_manager.create_client("athena")
            database = self._discover_database(glue)
            if not database:
                return None, "athena"
            sql, params_ok = self._build_athena_sql(database, query, date_from, date_to, limit)
            if not params_ok:
                return [], "athena"
            if not self._archive_bucket:
                return None, "athena"
            output = f"s3://{self._archive_bucket}/athena-results/"
            resp = athena.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": output},
            )
            qid = resp["QueryExecutionId"]
            status = {"State": "RUNNING"}
            for _ in range(30):
                status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
                if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                    break
                time.sleep(1)
            if status["State"] != "SUCCEEDED":
                logger.warning("Athena archived-jobs query {}: {}", status["State"], status.get("StateChangeReason", ""))
                return None, "athena"
            result = athena.get_query_results(QueryExecutionId=qid)
            columns = [c["Name"] for c in result["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
            jobs: List[Dict[str, Any]] = []
            for row in result["ResultSet"]["Rows"][1:]:
                vals = [field.get("VarCharValue", "") for field in row["Data"]]
                jobs.append(dict(zip(columns, vals)))
            return jobs, "athena"
        except Exception as exc:
            logger.info("Athena archived-jobs unavailable, using S3 scan: {}", exc)
            return None, "athena"

    def _discover_database(self, glue: Any) -> Optional[str]:
        from ..resource_naming import resolved_glue_database

        preferred = resolved_glue_database()
        try:
            glue.get_table(DatabaseName=preferred, Name=ARCHIVE_TABLE_NAME)
            return preferred
        except Exception:
            pass
        try:
            for db_info in glue.get_databases().get("DatabaseList") or []:
                name = db_info.get("Name") or ""
                if not name or not _SAFE_IDENT.match(name):
                    continue
                try:
                    glue.get_table(DatabaseName=name, Name=ARCHIVE_TABLE_NAME)
                    return name
                except Exception:
                    continue
        except Exception as exc:
            logger.info("Glue database discovery failed: {}", exc)
        return None

    def _build_athena_sql(
        self,
        database: str,
        query: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int,
    ) -> Tuple[str, bool]:
        if not _SAFE_IDENT.match(database):
            return "", False
        clauses = ["1=1"]
        q = (query or "").strip()
        if q:
            if q.isdigit():
                clauses.append(f"execution_number = {int(q)}")
            elif _SAFE_ID.match(q):
                clauses.append(f"job_id = '{q}'")
            else:
                return "", False
        if date_from:
            if not _SAFE_DATE.match(date_from):
                return "", False
            clauses.append(f"start_time >= '{date_from}'")
        if date_to:
            if not _SAFE_DATE.match(date_to):
                return "", False
            clauses.append(f"start_time <= '{date_to}T23:59:59'")
        safe_limit = max(1, min(int(limit), 500))
        where = " AND ".join(clauses)
        sql = (
            f'SELECT * FROM "{database}"."{ARCHIVE_TABLE_NAME}" '
            f"WHERE {where} ORDER BY start_time DESC LIMIT {safe_limit}"
        )
        return sql, True

    def _scan_s3(
        self,
        query: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not self._archive_bucket:
            return []
        rows: List[Dict[str, Any]] = []
        token: Optional[str] = None
        while True:
            kwargs: Dict[str, Any] = {
                "Bucket": self._archive_bucket,
                "Prefix": self._prefix,
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._s3.list_objects_v2(**kwargs)
            for obj in resp.get("Contents") or []:
                key = obj.get("Key") or ""
                if not key.endswith(".json"):
                    continue
                try:
                    body = self._s3.get_object(Bucket=self._archive_bucket, Key=key)["Body"].read().decode("utf-8")
                except Exception as exc:
                    logger.warning("Failed to read archive object {}: {}", key, exc)
                    continue
                for line in body.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return filter_archived_rows(rows, query=query, date_from=date_from, date_to=date_to, limit=limit)
