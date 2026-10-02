"""Dead-letter queue for failed transformation jobs — list, import, reprocess, dismiss."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from loguru import logger

from ..resource_naming import resolved_dlq_table

DLQ_PK = "dlq"
STATUS_PENDING = "pending_review"
STATUS_REPROCESSED = "reprocessed"
STATUS_DISMISSED = "dismissed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ddb_resource():
    from ..adapters.aws.client_manager import AWSClientManager

    return AWSClientManager(region_name=None).create_resource("dynamodb")


def _journeys_table_name() -> str:
    from ..config import get_config

    cfg = get_config()
    return cfg.dynamodb_transformation_table or resolved_dlq_table().rsplit("-", 1)[0] + "-journeys"


def _item_to_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pk": item.get("PK", DLQ_PK),
        "sk": item.get("SK", ""),
        "job_id": item.get("job_id", ""),
        "journey_id": item.get("journey_id", ""),
        "stage_id": item.get("stage_id", ""),
        "error": item.get("error", ""),
        "context": item.get("context", ""),
        "timestamp": item.get("timestamp", ""),
        "status": item.get("status", STATUS_PENDING),
        "new_job_id": item.get("new_job_id") or None,
        "reprocessed_at": item.get("reprocessed_at") or None,
        "dismissed_at": item.get("dismissed_at") or None,
    }


class DlqService:
    def __init__(self, table=None):
        self._table = table
        self._table_ready = table is not None

    def _ensure_table(self):
        if self._table is not None and self._table_ready:
            return self._table
        name = resolved_dlq_table()
        ddb = _ddb_resource()
        try:
            ddb.meta.client.describe_table(TableName=name)
        except ClientError:
            try:
                ddb.create_table(
                    TableName=name,
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
                ddb.meta.client.get_waiter("table_exists").wait(
                    TableName=name, WaiterConfig={"Delay": 1, "MaxAttempts": 15}
                )
                logger.info("Created DLQ table {}", name)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ResourceInUseException":
                    raise
        self._table = ddb.Table(name)
        self._table_ready = True
        return self._table

    def write_failed_job(
        self,
        *,
        job_id: str,
        journey_id: str,
        stage_id: str,
        error: str,
        context: str = "",
    ) -> Dict[str, Any]:
        table = self._ensure_table()
        now = _now_iso()
        item = {
            "PK": DLQ_PK,
            "SK": f"{now}#{job_id}",
            "EntityType": "JobDLQ",
            "job_id": job_id,
            "journey_id": journey_id,
            "stage_id": stage_id or "",
            "error": str(error)[:2000],
            "context": str(context)[:5000] if context else "",
            "timestamp": now,
            "status": STATUS_PENDING,
        }
        table.put_item(Item=item)
        return _item_to_entry(item)

    def list_entries(self, *, status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        table = self._ensure_table()
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": DLQ_PK},
            "ScanIndexForward": False,
            "Limit": max(1, min(limit, 200)),
        }
        if status:
            kwargs["FilterExpression"] = "#st = :st"
            kwargs["ExpressionAttributeNames"] = {"#st": "status"}
            kwargs["ExpressionAttributeValues"] = {":pk": DLQ_PK, ":st": status}
        resp = table.query(**kwargs)
        items = [_item_to_entry(i) for i in resp.get("Items") or []]
        counts = {"pending_review": 0, "reprocessed": 0, "dismissed": 0}
        for row in items:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {
            "table": resolved_dlq_table(),
            "count": len(items),
            "summary": counts,
            "items": items,
        }

    def import_failed_jobs(self, *, limit: int = 100) -> Dict[str, Any]:
        """Copy failed jobs from the journeys table into the DLQ if missing."""
        existing = {row["job_id"] for row in self.list_entries(limit=200)["items"]}
        ddb = _ddb_resource()
        journeys = ddb.Table(_journeys_table_name())
        imported = 0
        scanned = 0
        kwargs: Dict[str, Any] = {
            "FilterExpression": "EntityType = :et AND #data.#status = :failed",
            "ExpressionAttributeNames": {"#data": "Data", "#status": "status"},
            "ExpressionAttributeValues": {":et": "JobExecution", ":failed": "failed"},
        }
        while scanned < limit:
            resp = journeys.scan(**kwargs)
            for item in resp.get("Items") or []:
                scanned += 1
                data = item.get("Data") or {}
                job_id = data.get("jobId") or ""
                if not job_id or job_id in existing:
                    continue
                pk = str(item.get("PK") or "")
                journey_id = str(data.get("journeyId") or pk.replace("JOURNEY#", "") or "")
                self.write_failed_job(
                    job_id=job_id,
                    journey_id=journey_id,
                    stage_id=data.get("currentStageId") or data.get("stageId") or "",
                    error=data.get("errorMessage") or "Job failed",
                    context=f"imported from {item.get('SK', '')}",
                )
                existing.add(job_id)
                imported += 1
                if imported + len(existing) >= limit:
                    break
            last_key = resp.get("LastEvaluatedKey")
            if not last_key or imported >= limit:
                break
            kwargs["ExclusiveStartKey"] = last_key
        listed = self.list_entries(limit=limit)
        listed["imported"] = imported
        listed["scanned"] = scanned
        return listed

    def get_entry(self, sk: str) -> Optional[Dict[str, Any]]:
        table = self._ensure_table()
        resp = table.get_item(Key={"PK": DLQ_PK, "SK": sk})
        item = resp.get("Item")
        return _item_to_entry(item) if item else None

    async def reprocess(self, sk: str, *, triggered_by: str = "operations-dlq") -> Dict[str, Any]:
        entry = self.get_entry(sk)
        if not entry:
            raise KeyError(f"DLQ entry not found: {sk}")
        if entry["status"] == STATUS_DISMISSED:
            raise ValueError("Dismissed DLQ entries cannot be reprocessed")
        from ..models.journey_model import JourneyActionRequest
        from .journey_service import JourneyService

        svc = JourneyService()
        result = await svc.run_job(
            JourneyActionRequest(
                action="run_job",
                journey_id=entry["journey_id"],
                stage_id=entry["stage_id"] or None,
                triggered_by=triggered_by,
                reason=f"DLQ reprocess of {entry['job_id']}",
            )
        )
        if getattr(result, "status", "") == "error":
            raise RuntimeError(getattr(result, "message", None) or "Reprocess failed")
        new_job_id = getattr(result, "job_id", None)
        table = self._ensure_table()
        now = _now_iso()
        table.update_item(
            Key={"PK": DLQ_PK, "SK": sk},
            UpdateExpression="SET #st = :st, new_job_id = :nj, reprocessed_at = :ts",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": STATUS_REPROCESSED, ":nj": new_job_id or "", ":ts": now},
        )
        entry["status"] = STATUS_REPROCESSED
        entry["new_job_id"] = new_job_id
        entry["reprocessed_at"] = now
        return {"reprocessed": True, "original": entry, "new_job_id": new_job_id}

    def dismiss(self, sk: str) -> Dict[str, Any]:
        entry = self.get_entry(sk)
        if not entry:
            raise KeyError(f"DLQ entry not found: {sk}")
        now = _now_iso()
        self._ensure_table().update_item(
            Key={"PK": DLQ_PK, "SK": sk},
            UpdateExpression="SET #st = :st, dismissed_at = :ts",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":st": STATUS_DISMISSED, ":ts": now},
        )
        entry["status"] = STATUS_DISMISSED
        entry["dismissed_at"] = now
        return {"dismissed": True, "item": entry}


_service: Optional[DlqService] = None


def get_dlq_service() -> DlqService:
    global _service
    if _service is None:
        _service = DlqService()
    return _service


def write_failed_job(**kwargs: Any) -> None:
    try:
        get_dlq_service().write_failed_job(**kwargs)
    except Exception as exc:
        logger.warning("DLQ write failed for job {}: {}", kwargs.get("job_id"), exc)
