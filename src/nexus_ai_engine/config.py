"""EngineConfig — application-provided settings for the engine.

The library never reads environment variables or SSM/Secrets by itself. Host
applications build an ``EngineConfig`` from whichever source they prefer and
pass it to ``nexus_ai_engine.factory.build_engine``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class EngineConfig:
    """Runtime settings required to assemble the engine.

    Fields are intentionally concrete; adapter-specific settings live on the
    adapter classes themselves (e.g. ``DynamoDBJobRepository(table_name=...)``).
    """

    region: Optional[str] = None
    role_arn: Optional[str] = None

    dynamodb_transformation_table: Optional[str] = None
    dynamodb_prompts_table: Optional[str] = None

    s3_journey_logs_bucket: Optional[str] = None
    s3_journey_reports_bucket: Optional[str] = None

    max_concurrent_jobs: int = 10
    job_task_cleanup_interval_seconds: int = 60

    extras: dict = field(default_factory=dict)
