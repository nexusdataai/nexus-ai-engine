"""S3 artifact storage for execution logs and reports (spec 050)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import boto3

from nexus_ai_engine.config import get_config


class S3ArtifactStore:
    """Write JSON/JSONL artifacts to ai-engine-journey-logs/reports buckets."""

    def __init__(
        self,
        *,
        logs_bucket: str | None = None,
        reports_bucket: str | None = None,
        s3_client: Any = None,
        region: str | None = None,
    ):
        config = get_config()
        self.logs_bucket = logs_bucket or config.s3_journey_logs_bucket
        self.reports_bucket = reports_bucket or config.s3_journey_reports_bucket
        region = region or config.aws_region
        self._s3 = s3_client or boto3.client("s3", region_name=region)

    def log_key(self, tenant_id: str, journey_id: str, execution_id: str, stage_id: str, step_id: str) -> str:
        return f"logs/{tenant_id}/{journey_id}/{execution_id}/{stage_id}/{step_id}.jsonl"

    def report_key(self, tenant_id: str, journey_id: str, execution_id: str) -> str:
        return f"reports/{tenant_id}/{journey_id}/{execution_id}/summary.json"

    async def put_log_line(
        self,
        tenant_id: str,
        journey_id: str,
        execution_id: str,
        stage_id: str,
        step_id: str,
        line: dict,
    ) -> str:
        key = self.log_key(tenant_id, journey_id, execution_id, stage_id, step_id)
        body = (json.dumps(line, default=str) + "\n").encode()

        def _put():
            if not self.logs_bucket:
                return key
            self._s3.put_object(Bucket=self.logs_bucket, Key=key, Body=body, ContentType="application/x-ndjson")
            return key

        return await asyncio.get_event_loop().run_in_executor(None, _put)

    async def put_report_summary(
        self,
        tenant_id: str,
        journey_id: str,
        execution_id: str,
        summary: dict,
    ) -> str:
        key = self.report_key(tenant_id, journey_id, execution_id)
        body = json.dumps(summary, default=str).encode()

        def _put():
            if not self.reports_bucket:
                return key
            self._s3.put_object(Bucket=self.reports_bucket, Key=key, Body=body, ContentType="application/json")
            return key

        return await asyncio.get_event_loop().run_in_executor(None, _put)
