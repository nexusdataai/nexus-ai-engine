"""Routing-level integration test for production-mode app assembly.

When `factory.build_engine(EngineConfig(dynamodb_transformation_table=...))`
returns the production `Engine` facade, `create_app` must:

1. NOT mount the slim routers (which only speak `InMemoryEngine.run_job(...)`
   and would crash on the production facade).
2. Mount the legacy routers from `nexus_ai_engine.server.routers.legacy.*`
   so the embedded UI / external HTTP / MCP clients see the same
   `/api/v1/*` URL surface as nexus-backend.
3. Expose the production services on `app.state` for downstream
   dependency consumers and test introspection.

The test does NOT drive a real job through DynamoDB — that's Phase E
(LocalStack sandbox). We mock AWS so the imports / singleton constructors
inside the legacy routers don't issue real network calls.

Marked `integration` because it pulls in `moto` and the heavy production
service modules.
"""

from __future__ import annotations

import boto3
import moto
import pytest

from nexus_ai_engine.config import EngineConfig, reset_config
from nexus_ai_engine.execution import InMemoryEngine
from nexus_ai_engine.factory import build_engine
from nexus_ai_engine.server.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def reset_global_config():
    """Clear the process-wide engine config singleton between tests so the
    factory's `set_config()` call doesn't leak state into adjacent tests."""
    reset_config()
    yield
    reset_config()


def _create_dynamodb_table(table_name: str) -> None:
    """Create a minimal DynamoDB table that satisfies the journey
    manager's setup_aws_client() call. Schema mirrors the production
    table convention (PK + SK)."""
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
    )


@moto.mock_aws
def test_production_engine_mounts_legacy_routers(reset_global_config) -> None:
    _create_dynamodb_table("test-journeys")
    _create_dynamodb_table("test-executions")
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test-logs")
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test-reports")

    cfg = EngineConfig(
        region="us-east-1",
        dynamodb_transformation_table="test-journeys",
        dynamodb_executions_table="test-executions",
        dynamodb_prompts_table="test-journeys",
        s3_journey_logs_bucket="test-logs",
        s3_journey_reports_bucket="test-reports",
    )
    engine = build_engine(cfg)

    # 1. Production facade — not the in-memory engine.
    assert not isinstance(engine, InMemoryEngine), (
        "build_engine returned InMemoryEngine even though "
        "dynamodb_transformation_table was set"
    )

    app = create_app(engine=engine)
    paths = set(app.openapi()["paths"].keys())

    # 2. Legacy-only endpoints must be present. These have no equivalent
    #    in the slim router suite; their presence proves the legacy
    #    journey_api router was mounted.
    assert "/api/v1/journeys/admin/task-tracker" in paths
    assert "/api/v1/journeys/{journey_id}/execute" in paths

    # 3. Endpoints common to both router suites must still be present so
    #    the embedded UI works against either backend.
    assert "/api/v1/journeys/{journey_id}/jobs" in paths
    assert "/api/v1/journeys/{journey_id}/jobs/{job_id}/stream" in paths

    # 4. Slim-router-only endpoints must NOT be present (they would have
    #    crashed at request time on the production facade).
    #    Slim schedules use POST /{id}/run; legacy uses /{id}/run-now.
    assert "/api/v1/schedules/{schedule_id}/run" not in paths
    assert "/api/v1/schedules/{schedule_id}/run-now" in paths

    # 5. Production services hung off app.state for downstream consumers.
    assert app.state.engine is engine
    assert app.state.journey_service is engine.journeys
    assert app.state.prompts_service is engine.prompts
    assert app.state.scheduler_service is engine.schedules
    assert app.state.logs_reports_service is engine.logs_and_reports
    assert app.state.job_executor is engine.job_executor


def test_in_memory_engine_mounts_slim_routers() -> None:
    """Regression guard for the InMemoryEngine branch of `create_app`.

    Lives next to the production-mode test so a future change that
    accidentally swaps both branches breaks both tests at once.
    """
    engine = InMemoryEngine()
    app = create_app(engine=engine)
    paths = set(app.openapi()["paths"].keys())

    # Slim router contract.
    assert "/api/v1/journeys/{journey_id}/jobs/{job_id}/stream" in paths
    assert "/api/v1/schedules/{schedule_id}/run" in paths

    # Legacy-only paths must be absent.
    assert "/api/v1/journeys/admin/task-tracker" not in paths
    assert "/api/v1/schedules/{schedule_id}/run-now" not in paths

    # No production services hung off app.state for the in-memory path.
    assert app.state.engine is engine
    assert not hasattr(app.state, "journey_service") or app.state.__dict__.get("journey_service") is None
