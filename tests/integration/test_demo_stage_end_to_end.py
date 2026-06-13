"""End-to-end integration test for the bundled demo stages.

Wires the production ``BaseStage.__init__`` (which constructs real
DynamoDB + S3 boto3 clients) against moto's mocked AWS, registers the
demo stages, and runs ``execute_step`` against a real DemoStage_*
class. Asserts:

1. The step completes without raising and reports ``status="success"``.
2. ``stage_log`` writes to the DynamoDB LIVELOG buffer (the same path
   the legacy ``GET /jobs/{id}/logs`` endpoint reads from).
3. The bundled stages are discoverable via ``list_available_stages``
   after ``register_demo_stages`` runs.

Stops short of driving ``TransformationJobExecutor.execute_job`` because
that path requires a journey + job already persisted in DynamoDB plus
the matching GSI on the table — covered by the broader smoke test in
``tests/integration/test_production_router_mount.py``. This test focuses
narrowly on proving the new DemoStage class functions inside the
production runtime.
"""

from __future__ import annotations

import json
import time
from typing import List

import boto3
import moto
import pytest

from nexus_ai_engine.config import EngineConfig, reset_config, set_config
from nexus_ai_engine.events.sse_manager import sse_manager
from nexus_ai_engine.stages import (
    DEMO_JOURNEYS,
    clear_registry,
    get_stage_class,
    list_available_stages,
    register_demo_stages,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def _aws_and_config():
    """Set up moto-mocked AWS plus a DemoStage-friendly EngineConfig.

    The fixture yields the boto3 dynamodb table and the EngineConfig so
    tests can introspect what the stage wrote.
    """
    reset_config()
    clear_registry()
    with moto.mock_aws():
        ddb = boto3.client("dynamodb", region_name="us-east-1")
        table_name = "demo-test-table"
        ddb.create_table(
            TableName=table_name,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                       {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                                  {"AttributeName": "SK", "AttributeType": "S"}],
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="demo-test-logs")
        s3.create_bucket(Bucket="demo-test-reports")

        cfg = EngineConfig(
            region="us-east-1",
            dynamodb_transformation_table=table_name,
            dynamodb_prompts_table=table_name,
            s3_journey_logs_bucket="demo-test-logs",
            s3_journey_reports_bucket="demo-test-reports",
        )
        set_config(cfg)

        registered = register_demo_stages()

        yield {
            "config": cfg,
            "table_name": table_name,
            "registered": registered,
            "ddb_resource": boto3.resource("dynamodb", region_name="us-east-1"),
        }
    reset_config()
    clear_registry()


def test_demo_stages_visible_in_registry(_aws_and_config) -> None:
    """register_demo_stages exposes every demo stage via list_available_stages."""
    available = set(list_available_stages())
    assert set(_aws_and_config["registered"]) <= available
    # Cross-check against the canonical journey definitions.
    expected = {s["stage_id"] for j in DEMO_JOURNEYS for s in j["stages"]}
    assert expected <= available


def test_order_to_cash_first_step_runs_and_writes_livelog(
    _aws_and_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the first step of the order-to-cash demo stage end-to-end.

    Asserts:
    - execute_step completes with status=success.
    - DynamoDB LIVELOG#<job> entry exists with logs_json populated.
    - The matching `log` SSE event was published (so the v2 UI lights up).
    """
    # Make the step instant so the test runs in <1 second.
    monkeypatch.setattr("nexus_ai_engine.stages.demo.time.sleep", lambda *_: None)

    StageCls = get_stage_class("order_to_cash")
    stage = StageCls(
        journey_id="JRN-DEMO",
        stage_id="order_to_cash",
        job_id="JOB-DEMO",
        region_name="us-east-1",
    )

    # Subscribe to SSE before driving the step so we capture the log events.
    received_log_events: List[dict] = []
    captured_job_id = "JOB-DEMO"
    # SSEManager.broadcast_sync is the entrypoint emit_log uses; intercept it.
    original = sse_manager.broadcast_sync
    def _capture(job_id, event):
        if job_id == captured_job_id:
            received_log_events.append({
                "type": event.event_type.value,
                "data": dict(event.data),
            })
        return original(job_id, event)
    monkeypatch.setattr(sse_manager, "broadcast_sync", _capture)

    # Run the first step of order_to_cash with a small fixed tick count.
    step_def = next(
        s for s in stage.STEP_DEFINITIONS if s["id"] == "entity_resolution"
    )
    step_def_test = {**step_def, "ticks": 3, "sleep_min": 0.0, "sleep_max": 0.0}
    # Mutate the class's step list temporarily so execute_step picks up the
    # smaller tick count without altering the canonical DEMO_JOURNEYS.
    StageCls.STEP_DEFINITIONS = [
        step_def_test if s["id"] == "entity_resolution" else s
        for s in StageCls.STEP_DEFINITIONS
    ]

    result = stage.execute_step("entity_resolution", step_def_test)

    assert result["status"] == "success"
    assert result["ticks_completed"] == 3
    assert result["items_processed"] > 0

    # DynamoDB LIVELOG: BaseStage._write_live_logs_to_dynamo writes one
    # row per step with key (PK=LIVELOG#<job>, SK=<step_id>). We expect a
    # row containing the 5 log lines we just emitted (Starting + 3 ticks
    # + Completed).
    table = _aws_and_config["ddb_resource"].Table(_aws_and_config["table_name"])
    row = table.get_item(
        Key={"PK": "LIVELOG#JOB-DEMO", "SK": "entity_resolution"},
        ConsistentRead=True,
    ).get("Item")
    assert row is not None, "expected LIVELOG row in DynamoDB"
    persisted_logs = json.loads(row["logs_json"])
    assert len(persisted_logs) == 5
    levels = [l["level"] for l in persisted_logs]
    assert levels.count("INFO") == 5
    assert all(l["step_id"] == "entity_resolution" for l in persisted_logs)

    # SSE: at least one `log` event reached the broadcaster for our job.
    log_events = [e for e in received_log_events if e["type"] == "log"]
    assert log_events, "expected at least one `log` SSE event for the job"
    # The first emitted log line is the "Starting ..." line.
    assert any("Starting" in (e["data"].get("message") or "") for e in log_events)
