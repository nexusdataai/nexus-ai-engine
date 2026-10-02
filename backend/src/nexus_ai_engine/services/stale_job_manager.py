"""Detect and cancel stuck journey jobs (in_progress with stale UpdatedAt)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from botocore.exceptions import ClientError
from loguru import logger


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_long_running_job(data: Dict[str, Any]) -> bool:
    if data.get("longRunning") is True:
        return True
    job_config = data.get("jobConfig") or {}
    return bool(job_config.get("long_running") or job_config.get("longRunning"))


@dataclass
class StaleJobRecord:
    job_id: str
    journey_id: str
    stage_id: str
    current_step: str
    age_min: float
    confidence: str
    pk: str
    sk: str


@dataclass
class BlockedScheduleRecord:
    schedule_id: str
    journey_id: str
    last_job_id: str
    pk: str
    sk: str


@dataclass
class StaleJobScanResult:
    jobs: List[StaleJobRecord] = field(default_factory=list)
    blocked_schedules: List[BlockedScheduleRecord] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        counts = {"STALE": 0, "LIKELY-STUCK": 0, "UNVERIFIED-LONG": 0}
        for job in self.jobs:
            counts[job.confidence] = counts.get(job.confidence, 0) + 1
        return {
            "total_stale": len(self.jobs),
            **counts,
            "blocked_schedules": len(self.blocked_schedules),
        }


class StaleJobManager:
    """Scan / cancel stale jobs and unblock wedged batch schedules."""

    def __init__(
        self,
        table,
        *,
        threshold_min: Optional[int] = None,
        likely_stuck_min: Optional[int] = None,
        long_running_min: Optional[int] = None,
        known_slow_steps: Optional[Set[str]] = None,
        ddb_workers: int = 4,
        ddb_page_size: int = 500,
        journey_id_filter: str = "",
    ):
        self.table = table
        self.threshold_min = threshold_min or int(os.getenv("STALE_JOB_THRESHOLD_MIN", "10"))
        self.likely_stuck_min = likely_stuck_min or int(os.getenv("STALE_JOB_LIKELY_STUCK_MIN", "30"))
        if long_running_min is not None:
            self.long_running_min = long_running_min
        else:
            try:
                from .job_execution_config_service import get_job_execution_config

                self.long_running_min = get_job_execution_config().get_long_running_job_min()
            except Exception:
                self.long_running_min = int(os.getenv("STALE_JOB_LONG_RUNNING_MIN", "180"))
        default_slow = os.getenv(
            "STALE_JOB_KNOWN_SLOW_STEPS",
            "process_recordings,openai_transcription,glue_registration,download_recording,"
            "ai_analysis,diarization,scan_calls,load_and_merge,compute_snapshots,publish_cache",
        )
        self.known_slow_steps = known_slow_steps or {
            s.strip() for s in default_slow.split(",") if s.strip()
        }
        self.ddb_workers = max(1, ddb_workers)
        self.ddb_page_size = max(50, ddb_page_size)
        self.journey_id_filter = journey_id_filter.strip()
        self.exclude_job_ids: Set[str] = set()

    def scan(self) -> StaleJobScanResult:
        return StaleJobScanResult(
            jobs=self._scan_stale_jobs(),
            blocked_schedules=self._scan_blocked_schedules(),
        )

    def sweep(
        self,
        *,
        skip_unverified_long: bool = True,
        reason: str = "Cancelled by stale-job sweeper",
    ) -> Dict[str, Any]:
        scan = self.scan()
        to_cancel = [
            j for j in scan.jobs
            if not (skip_unverified_long and j.confidence == "UNVERIFIED-LONG")
        ]
        return {
            "scan_summary": scan.summary,
            "cancel": self.cancel_jobs(to_cancel, skip_unverified_long=False, reason=reason),
            "unblock_schedules": self.unblock_schedules(scan.blocked_schedules),
        }

    def cancel_jobs(
        self,
        jobs: List[StaleJobRecord],
        *,
        skip_unverified_long: bool = True,
        reason: str = "Cancelled by stale-job-manager",
    ) -> Dict[str, Any]:
        cancelled = skipped = failed = 0
        details: List[Dict[str, str]] = []
        for job in jobs:
            if skip_unverified_long and job.confidence == "UNVERIFIED-LONG":
                skipped += 1
                details.append({"job_id": job.job_id, "result": "skipped", "confidence": job.confidence})
                continue
            ok = self._cancel_one(job, reason=reason)
            if ok:
                cancelled += 1
                details.append({"job_id": job.job_id, "result": "cancelled", "confidence": job.confidence})
            else:
                failed += 1
                details.append({"job_id": job.job_id, "result": "failed", "confidence": job.confidence})
        return {"cancelled": cancelled, "skipped": skipped, "failed": failed, "details": details}

    def unblock_schedules(self, schedules: List[BlockedScheduleRecord]) -> Dict[str, Any]:
        unblocked = skipped = failed = 0
        now = _now().isoformat().replace("+00:00", "Z")
        for sched in schedules:
            try:
                self.table.update_item(
                    Key={"PK": sched.pk, "SK": sched.sk},
                    UpdateExpression="SET #d.lastJobStatus = :unk, UpdatedAt = :now",
                    ConditionExpression="#et = :et AND #d.lastJobStatus = :inp",
                    ExpressionAttributeNames={"#d": "Data", "#et": "EntityType"},
                    ExpressionAttributeValues={
                        ":unk": "unknown",
                        ":inp": "in_progress",
                        ":et": "Schedule",
                        ":now": now,
                    },
                )
                unblocked += 1
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code == "ConditionalCheckFailedException":
                    skipped += 1
                else:
                    failed += 1
        return {"unblocked": unblocked, "skipped": skipped, "failed": failed}

    def _cancel_one(self, job: StaleJobRecord, *, reason: str) -> bool:
        try:
            from .journey_service import JourneyService

            JourneyService.cancel_running_job(job.job_id)
        except Exception:
            pass

        now = _now().isoformat().replace("+00:00", "Z")
        try:
            self.table.update_item(
                Key={"PK": job.pk, "SK": job.sk},
                UpdateExpression=(
                    "SET #d.#s = :cancelled, #d.errorMessage = :reason, "
                    "#d.endTime = :now, UpdatedAt = :now"
                ),
                ConditionExpression="#et = :et AND #d.#s = :inp",
                ExpressionAttributeNames={"#d": "Data", "#s": "status", "#et": "EntityType"},
                ExpressionAttributeValues={
                    ":cancelled": "cancelled",
                    ":reason": reason,
                    ":now": now,
                    ":et": "JobExecution",
                    ":inp": "in_progress",
                },
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ConditionalCheckFailedException":
                return True
            return False

    def _scan_stale_jobs(self) -> List[StaleJobRecord]:
        fe = "#et = :et AND #d.#st = :inp"
        ean = {"#et": "EntityType", "#d": "Data", "#st": "status"}
        eav: Dict[str, Any] = {":et": "JobExecution", ":inp": "in_progress"}
        if self.journey_id_filter:
            fe += " AND #d.journeyId = :jid"
            eav[":jid"] = self.journey_id_filter

        projection = (
            "PK, SK, UpdatedAt, "
            "#d.jobId, #d.journeyId, #d.stageId, #d.currentStepId, "
            "#d.startTime, #d.#st, #d.longRunning, #d.jobConfig"
        )

        def scan_segment(segment: int, total: int) -> List[Dict[str, Any]]:
            segment_items: List[Dict[str, Any]] = []
            lek = None
            while True:
                kwargs: Dict[str, Any] = {
                    "FilterExpression": fe,
                    "ExpressionAttributeNames": ean,
                    "ExpressionAttributeValues": eav,
                    "ProjectionExpression": projection,
                    "Segment": segment,
                    "TotalSegments": total,
                    "Limit": self.ddb_page_size,
                }
                if lek:
                    kwargs["ExclusiveStartKey"] = lek
                resp = self.table.scan(**kwargs)
                segment_items.extend(resp.get("Items", []))
                lek = resp.get("LastEvaluatedKey")
                if not lek:
                    break
            return segment_items

        if self.ddb_workers == 1:
            items = scan_segment(0, 1)
        else:
            items = []
            with ThreadPoolExecutor(max_workers=self.ddb_workers) as pool:
                futures = [pool.submit(scan_segment, i, self.ddb_workers) for i in range(self.ddb_workers)]
                for future in as_completed(futures):
                    items.extend(future.result())

        now = _now()
        rows: List[StaleJobRecord] = []
        for item in items:
            data = item.get("Data") or {}
            job_id = str(data.get("jobId") or "")
            if job_id and job_id in self.exclude_job_ids:
                continue
            updated_at = item.get("UpdatedAt") or data.get("UpdatedAt")
            started_at = data.get("startTime")
            upd_dt = _parse_iso(updated_at) or _parse_iso(started_at)
            if not upd_dt:
                continue
            cur_step = str(data.get("currentStepId") or "")
            age_min = (now - upd_dt).total_seconds() / 60.0
            is_long_running = _is_long_running_job(data)
            if is_long_running:
                if age_min < self.long_running_min:
                    continue
                confidence = "LIKELY-STUCK"
            elif age_min < self.threshold_min:
                continue
            elif age_min >= self.likely_stuck_min:
                confidence = "LIKELY-STUCK"
            elif cur_step in self.known_slow_steps:
                confidence = "UNVERIFIED-LONG"
            else:
                confidence = "STALE"

            rows.append(
                StaleJobRecord(
                    job_id=job_id,
                    journey_id=str(data.get("journeyId") or ""),
                    stage_id=str(data.get("stageId") or ""),
                    current_step=cur_step,
                    age_min=round(age_min, 1),
                    confidence=confidence,
                    pk=str(item.get("PK") or ""),
                    sk=str(item.get("SK") or ""),
                )
            )

        order = {"LIKELY-STUCK": 0, "STALE": 1, "UNVERIFIED-LONG": 2}
        rows.sort(key=lambda r: (order.get(r.confidence, 9), -r.age_min))
        return rows

    def _scan_blocked_schedules(self) -> List[BlockedScheduleRecord]:
        fe = "#et = :et AND #d.#l = :inp"
        ean = {"#et": "EntityType", "#d": "Data", "#l": "lastJobStatus"}
        eav: Dict[str, Any] = {":et": "BatchSchedule", ":inp": "in_progress"}
        if self.journey_id_filter:
            fe += " AND #d.journeyId = :jid"
            eav[":jid"] = self.journey_id_filter

        projection = "PK, SK, #d.scheduleId, #d.id, #d.journeyId, #d.lastJobId, #d.#l"
        items: List[Dict[str, Any]] = []
        lek = None
        while True:
            kwargs: Dict[str, Any] = {
                "FilterExpression": fe,
                "ExpressionAttributeNames": ean,
                "ExpressionAttributeValues": eav,
                "ProjectionExpression": projection,
                "Limit": self.ddb_page_size,
            }
            if lek:
                kwargs["ExclusiveStartKey"] = lek
            resp = self.table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break

        rows: List[BlockedScheduleRecord] = []
        for item in items:
            data = item.get("Data") or {}
            rows.append(
                BlockedScheduleRecord(
                    schedule_id=str(data.get("scheduleId") or data.get("id") or ""),
                    journey_id=str(data.get("journeyId") or ""),
                    last_job_id=str(data.get("lastJobId") or ""),
                    pk=str(item.get("PK") or ""),
                    sk=str(item.get("SK") or ""),
                )
            )
        return rows


_sweeper_task: Optional[Any] = None


def _get_transformation_table():
    from ..adapters.aws import AWSClientManager
    from ..config import get_config

    config = get_config()
    table_name = config.dynamodb_transformation_table
    if not table_name:
        raise RuntimeError("DYNAMODB_TRANSFORMATION_TABLE is not configured")
    manager = AWSClientManager(region_name=config.aws_region, role_arn=config.role_arn)
    return manager.create_resource("dynamodb").Table(table_name)


async def run_stale_job_sweeper_loop(interval_sec: int = 300) -> None:
    import asyncio

    interval = int(os.getenv("STALE_JOB_SWEEPER_INTERVAL_SEC", str(interval_sec)))
    threshold = int(os.getenv("STALE_JOB_SWEEPER_THRESHOLD_MIN", "30"))
    await asyncio.sleep(10)

    while True:
        try:
            await asyncio.sleep(interval)
            table = await asyncio.to_thread(_get_transformation_table)
            from .job_execution_config_service import get_job_execution_config

            manager = StaleJobManager(
                table,
                threshold_min=threshold,
                long_running_min=get_job_execution_config().get_long_running_job_min(),
            )
            result = await asyncio.to_thread(
                manager.sweep,
                skip_unverified_long=True,
                reason="Cancelled by background stale-job sweeper",
            )
            cancelled = result.get("cancel", {}).get("cancelled", 0)
            unblocked = result.get("unblock_schedules", {}).get("unblocked", 0)
            if cancelled or unblocked:
                logger.info(
                    "Stale-job sweeper: cancelled={}, unblocked_schedules={}, scan={}",
                    cancelled,
                    unblocked,
                    result.get("scan_summary"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Stale-job sweeper error: {}", exc)


def start_stale_job_sweeper() -> None:
    global _sweeper_task
    if _sweeper_task is not None and not _sweeper_task.done():
        return
    enabled = os.getenv("STALE_JOB_SWEEPER_ENABLED", "true").lower() in ("1", "true", "yes")
    if not enabled:
        logger.info("Background stale-job sweeper disabled")
        return
    try:
        import asyncio

        loop = asyncio.get_running_loop()
        _sweeper_task = loop.create_task(run_stale_job_sweeper_loop())
    except RuntimeError:
        pass
