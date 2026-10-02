from types import SimpleNamespace

import pytest

from nexus_ai_engine.services.dlq_service import (
    STATUS_DISMISSED,
    STATUS_PENDING,
    STATUS_REPROCESSED,
    DlqService,
)


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item["PK"], Item["SK"])] = dict(Item)

    def query(self, **kwargs):
        values = kwargs.get("ExpressionAttributeValues") or {}
        pk = values.get(":pk")
        status = values.get(":st")
        rows = [v for (p, _s), v in self.items.items() if p == pk]
        rows.sort(key=lambda r: r["SK"], reverse=True)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return {"Items": rows}

    def get_item(self, Key):
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        item = self.items[(Key["PK"], Key["SK"])]
        item["status"] = ExpressionAttributeValues[":st"]
        if ":nj" in ExpressionAttributeValues:
            item["new_job_id"] = ExpressionAttributeValues[":nj"]
            item["reprocessed_at"] = ExpressionAttributeValues[":ts"]
        if ":ts" in ExpressionAttributeValues and "new_job_id" not in ExpressionAttributeValues:
            item["dismissed_at"] = ExpressionAttributeValues[":ts"]


def test_write_and_list_pending():
    svc = DlqService(table=FakeTable())
    svc.write_failed_job(job_id="job-1", journey_id="j1", stage_id="stage-a", error="boom")
    listed = svc.list_entries()
    assert listed["count"] == 1
    assert listed["items"][0]["job_id"] == "job-1"
    assert listed["items"][0]["status"] == STATUS_PENDING
    assert listed["summary"]["pending_review"] == 1


def test_dismiss_marks_entry():
    svc = DlqService(table=FakeTable())
    entry = svc.write_failed_job(job_id="job-2", journey_id="j1", stage_id="stage-a", error="boom")
    result = svc.dismiss(entry["sk"])
    assert result["dismissed"] is True
    assert svc.get_entry(entry["sk"])["status"] == STATUS_DISMISSED


@pytest.mark.asyncio
async def test_reprocess_queues_new_job(monkeypatch):
    svc = DlqService(table=FakeTable())
    entry = svc.write_failed_job(job_id="job-3", journey_id="j1", stage_id="stage-a", error="boom")

    class FakeJourneyService:
        async def run_job(self, request):
            assert request.journey_id == "j1"
            assert request.stage_id == "stage-a"
            return SimpleNamespace(status="success", job_id="job-3-retry")

    monkeypatch.setattr("nexus_ai_engine.services.journey_service.JourneyService", FakeJourneyService)
    result = await svc.reprocess(entry["sk"])
    assert result["reprocessed"] is True
    assert result["new_job_id"] == "job-3-retry"
    assert svc.get_entry(entry["sk"])["status"] == STATUS_REPROCESSED


@pytest.mark.asyncio
async def test_reprocess_rejected_for_dismissed(monkeypatch):
    svc = DlqService(table=FakeTable())
    entry = svc.write_failed_job(job_id="job-4", journey_id="j1", stage_id="stage-a", error="boom")
    svc.dismiss(entry["sk"])
    with pytest.raises(ValueError):
        await svc.reprocess(entry["sk"])
