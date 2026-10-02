"""Archive older JobExecution rows from DynamoDB to S3 (and Glue when available)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .base_stage import BaseStage
from .registry import register_stage

ARCHIVE_TABLE_NAME = "archived_jobs"
DEFAULT_KEEP = 1000
DEFAULT_MAX_PER_RUN = 500


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def archive_limits() -> Tuple[int, int]:
    keep = max(1, int(os.getenv("JOB_ARCHIVE_KEEP", str(DEFAULT_KEEP))))
    max_per_run = max(1, int(os.getenv("JOB_ARCHIVE_MAX_PER_RUN", str(DEFAULT_MAX_PER_RUN))))
    return keep, max_per_run


def job_sort_key(item: Dict[str, Any]) -> Tuple[str, int]:
    data = item.get("Data") or {}
    start = str(data.get("startTime") or "")
    try:
        execution_number = int(data.get("executionNumber") or 0)
    except (TypeError, ValueError):
        execution_number = 0
    return (start, execution_number)


def select_archive_candidates(
    jobs: List[Dict[str, Any]],
    keep: int = DEFAULT_KEEP,
    max_per_run: int = DEFAULT_MAX_PER_RUN,
) -> List[Dict[str, Any]]:
    """Keep the newest ``keep`` jobs globally; return up to ``max_per_run`` older rows."""
    ordered = sorted(jobs, key=job_sort_key, reverse=True)
    overflow = ordered[keep:]
    return overflow[:max_per_run]


def parse_duration(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float, Decimal)):
        return float(val)
    text = str(val).strip()
    try:
        return float(text)
    except ValueError:
        pass
    total = 0.0
    minutes = re.search(r"(\d+)\s*m", text)
    if minutes:
        total += int(minutes.group(1)) * 60
    seconds = re.search(r"(\d+)\s*s", text)
    if seconds:
        total += int(seconds.group(1))
    return total


def archive_bucket_name(config: Any) -> str:
    return (
        os.getenv("S3_JOB_ARCHIVE_BUCKET")
        or getattr(config, "s3_journey_reports_bucket", None)
        or os.getenv("S3_JOURNEY_REPORTS_BUCKET")
        or ""
    )


class JobArchivalStage(BaseStage):
    """Export older jobs to S3 NDJSON, optionally register Glue, then delete Dynamo rows."""

    STAGE_NAME = "Job Archival"
    STAGE_DESCRIPTION = "Archive old job metadata from DynamoDB to S3, keeping the latest 1000 jobs globally"
    STEP_DEFINITIONS = [
        {"id": "count_jobs", "name": "Count Jobs", "order": 0},
        {"id": "identify_candidates", "name": "Identify Archive Candidates", "order": 1},
        {"id": "export_to_s3", "name": "Export to S3", "order": 2},
        {"id": "register_glue", "name": "Register in Glue Catalog", "order": 3},
        {"id": "delete_from_dynamo", "name": "Delete from DynamoDB", "order": 4},
    ]

    def __init__(
        self,
        journey_id: str,
        stage_id: str,
        job_id: str,
        region_name: Optional[str] = None,
        role_arn: Optional[str] = None,
        enable_logging: bool = True,
    ) -> None:
        super().__init__(journey_id, stage_id, job_id, region_name, role_arn)
        if enable_logging:
            try:
                self.setup_enhanced_logging()
            except Exception:
                pass
        self._s3_bucket = archive_bucket_name(self._config)
        self._s3_prefix = "job-archive"
        from ..resource_naming import resolved_glue_database

        self._glue_database = resolved_glue_database()
        self._glue_table = ARCHIVE_TABLE_NAME
        self._candidates: List[Dict[str, Any]] = []
        self._total_jobs = 0
        self._keep, self._max_per_run = archive_limits()

    @property
    def stage_name(self) -> str:
        return self.STAGE_NAME

    @property
    def stage_description(self) -> str:
        return self.STAGE_DESCRIPTION

    @property
    def steps(self) -> List[Dict[str, Any]]:
        return list(self.STEP_DEFINITIONS)

    def execute_step(self, step_id: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        handler = {
            "count_jobs": self._step_count,
            "identify_candidates": self._step_identify,
            "export_to_s3": self._step_export,
            "register_glue": self._step_register_glue,
            "delete_from_dynamo": self._step_delete,
        }.get(step_id)
        if not handler:
            return {"status": "failed", "message": f"Unknown step: {step_id}"}
        return handler(step_id)

    def _step_count(self, step_id: str) -> Dict[str, Any]:
        self.log_info("Counting JobExecution rows across all journeys...", step_id)
        all_jobs = self._scan_all_jobs()
        self._total_jobs = len(all_jobs)
        self.log_info(f"Total jobs in DynamoDB: {self._total_jobs}", step_id)
        self.log_info(f"Keep window: {self._keep}; max per run: {self._max_per_run}", step_id)
        return {
            "status": "completed",
            "total_jobs": self._total_jobs,
            "max_jobs": self._keep,
            "max_per_run": self._max_per_run,
        }

    def _step_identify(self, step_id: str) -> Dict[str, Any]:
        self.log_info("Identifying archive candidates (global keep window)...", step_id)
        all_jobs = self._scan_all_jobs()
        self._total_jobs = len(all_jobs)
        self._candidates = select_archive_candidates(all_jobs, self._keep, self._max_per_run)
        if not self._candidates:
            self.log_info(f"Only {len(all_jobs)} jobs — nothing to archive", step_id)
            return {"status": "completed", "candidates": 0, "total_jobs": len(all_jobs)}
        self.log_info(
            f"Identified {len(self._candidates)} jobs to archive "
            f"(keeping latest {self._keep}, cap {self._max_per_run})",
            step_id,
        )
        return {
            "status": "completed",
            "candidates": len(self._candidates),
            "total_jobs": len(all_jobs),
        }

    def _step_export(self, step_id: str) -> Dict[str, Any]:
        if not self._candidates:
            self.log_info("No candidates to export — skipping", step_id)
            return {"status": "completed", "exported": 0}
        if not self._s3_bucket:
            raise RuntimeError("Archive bucket is not configured (S3_JOB_ARCHIVE_BUCKET / S3_JOURNEY_REPORTS_BUCKET)")

        self.log_info(f"Exporting {len(self._candidates)} jobs to S3...", step_id)
        now = datetime.now(timezone.utc)
        rows = [self._row_from_item(item, now) for item in self._candidates]
        ndjson = "\n".join(json.dumps(row, cls=_DecimalEncoder) for row in rows)
        key = f"{self._s3_prefix}/{now.strftime('%Y/%m/%d')}/jobs-{self.job_id}.json"
        self.s3.put_object(
            Bucket=self._s3_bucket,
            Key=key,
            Body=ndjson.encode("utf-8"),
            ContentType="application/json",
        )
        self.log_info(f"Exported {len(rows)} jobs to s3://{self._s3_bucket}/{key}", step_id)
        return {"status": "completed", "exported": len(rows), "s3_key": key}

    def _step_register_glue(self, step_id: str) -> Dict[str, Any]:
        if not self._candidates:
            self.log_info("No candidates — skipping Glue registration", step_id)
            return {"status": "completed", "registered": False}
        if not self._s3_bucket:
            self.log_warning("No archive bucket — skipping Glue registration", step_id)
            return {"status": "completed", "registered": False}

        self.log_info("Ensuring Glue table exists...", step_id)
        try:
            glue = self.client_manager.create_client("glue")
            try:
                glue.get_table(DatabaseName=self._glue_database, Name=self._glue_table)
                self.log_info(f"Glue table {self._glue_table} already exists", step_id)
                return {"status": "completed", "registered": True}
            except Exception:
                glue.create_table(
                    DatabaseName=self._glue_database,
                    TableInput={
                        "Name": self._glue_table,
                        "StorageDescriptor": {
                            "Columns": [
                                {"Name": "job_id", "Type": "string"},
                                {"Name": "journey_id", "Type": "string"},
                                {"Name": "execution_number", "Type": "int"},
                                {"Name": "stage_id", "Type": "string"},
                                {"Name": "stage_name", "Type": "string"},
                                {"Name": "status", "Type": "string"},
                                {"Name": "start_time", "Type": "string"},
                                {"Name": "end_time", "Type": "string"},
                                {"Name": "duration", "Type": "double"},
                                {"Name": "triggered_by", "Type": "string"},
                                {"Name": "metrics", "Type": "string"},
                                {"Name": "step_results", "Type": "string"},
                                {"Name": "archived_at", "Type": "string"},
                            ],
                            "Location": f"s3://{self._s3_bucket}/{self._s3_prefix}/",
                            "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                            "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                            "SerdeInfo": {
                                "SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe",
                            },
                        },
                        "TableType": "EXTERNAL_TABLE",
                    },
                )
                self.log_info(f"Glue table {self._glue_table} created", step_id)
                return {"status": "completed", "registered": True}
        except Exception as exc:
            self.log_warning(f"Glue registration skipped (local/no Glue): {exc}", step_id)
            return {"status": "completed", "registered": False, "message": str(exc)}

    def _step_delete(self, step_id: str) -> Dict[str, Any]:
        if not self._candidates:
            self.log_info("No candidates to delete — skipping", step_id)
            return {"status": "completed", "deleted": 0}

        self.log_info(f"Deleting {len(self._candidates)} archived jobs from DynamoDB...", step_id)
        deleted = 0
        for item in self._candidates:
            try:
                self.table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                deleted += 1
            except Exception as exc:
                self.log_warning(f"Failed to delete {item.get('SK')}: {exc}", step_id)
        self.log_info(f"Deleted {deleted}/{len(self._candidates)} jobs from DynamoDB", step_id)
        return {"status": "completed", "deleted": deleted}

    def _row_from_item(self, item: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        data = item.get("Data") or {}
        return {
            "job_id": data.get("jobId", ""),
            "journey_id": data.get("journeyId", ""),
            "execution_number": int(data.get("executionNumber", 0) or 0),
            "stage_id": data.get("stageId", ""),
            "stage_name": data.get("stageName", ""),
            "status": data.get("status", ""),
            "start_time": data.get("startTime", ""),
            "end_time": data.get("endTime", ""),
            "duration": parse_duration(data.get("duration")),
            "triggered_by": data.get("triggeredBy", ""),
            "metrics": json.dumps(data.get("metrics", {}), cls=_DecimalEncoder),
            "step_results": json.dumps(data.get("stepResults", {}), cls=_DecimalEncoder),
            "archived_at": now.isoformat().replace("+00:00", "Z"),
        }

    def _scan_all_jobs(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {
            "FilterExpression": "EntityType = :et AND begins_with(SK, :sk)",
            "ExpressionAttributeValues": {":et": "JobExecution", ":sk": "JOB#"},
        }
        while True:
            resp = self.table.scan(**params)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            params["ExclusiveStartKey"] = last_key
        return items


def register_job_archival_stage(*, registry_register=register_stage) -> str:
    registry_register("job_archival", JobArchivalStage)
    return "job_archival"
