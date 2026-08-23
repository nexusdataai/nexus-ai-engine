"""EngineConfig — application-provided settings for the engine.

The library itself remains injection-only: host applications build an
``EngineConfig`` from whichever source they prefer and pass it to
``nexus_ai_engine.factory.build_engine``. ``set_config()`` /
``get_config()`` expose a process-wide singleton so service modules ported
from nexus-backend keep their existing ``from ..config import get_config``
import shape.

The reference CLI (``nexus-ai-engine serve``) provides two opt-in
bootstrap paths on top of that contract:

- Default: read ``EngineConfig`` fields from environment variables
  (``DYNAMODB_TRANSFORMATION_TABLE``, ``S3_JOURNEY_LOGS_BUCKET``, etc.).
- ``--ssm-prefix /ai-engine/{env}/`` (or ``SSM_PARAMETER_PREFIX``):
  read fields from AWS SSM Parameter Store via boto3, with env-var
  fallback per key. Used by the K8s deployment so operators only need to
  manage one set of values per environment in SSM.

Direct callers of :func:`build_engine` are unaffected by either path.
"""

from __future__ import annotations

import os
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
    dynamodb_executions_table: Optional[str] = None
    dynamodb_prompts_table: Optional[str] = None

    s3_journey_logs_bucket: Optional[str] = None
    s3_journey_reports_bucket: Optional[str] = None

    max_concurrent_jobs: int = 10
    job_task_cleanup_interval_seconds: int = 60

    capability_name: str = "ai-engine"
    environment: str = "dev"

    extras: dict = field(default_factory=dict)

    @property
    def aws_region(self) -> str:
        """Alias for ``region`` with env-var fallback."""
        return (
            self.region
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )


# ────────────────────────────────────────────────────────────────────────────
# Process-wide singleton helpers
# ────────────────────────────────────────────────────────────────────────────
# Service code ported from nexus-backend uses ``from ..config import
# get_config`` and then accesses fields like
# ``config.dynamodb_transformation_table``. The host app wires its config
# object via ``set_config()`` at startup; ``get_config()`` returns it (or
# falls back to a default ``EngineConfig`` so library-only usage and tests
# work without explicit wiring).
# ────────────────────────────────────────────────────────────────────────────


_global_config: Optional[EngineConfig] = None


def set_config(config: EngineConfig) -> None:
    """Wire the process-wide engine config. Call once at application startup."""
    global _global_config
    _global_config = config


def _env_or_default(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    return value if value else default


def config_from_environment() -> EngineConfig:
    """Build EngineConfig from environment with resource-naming fallbacks."""
    from . import resource_naming as rn

    cap = _env_or_default("CAPABILITY_NAME", "ai-engine") or "ai-engine"
    env = _env_or_default("ENVIRONMENT", "dev") or "dev"

    return EngineConfig(
        region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        role_arn=os.getenv("AWS_ROLE_ARN"),
        dynamodb_transformation_table=(
            os.getenv("DYNAMODB_TRANSFORMATION_TABLE")
            or os.getenv("DYNAMODB_TABLE")
            or rn.dynamodb_table_name("journeys", capability=cap, environment=env)
        ),
        dynamodb_executions_table=(
            os.getenv("DYNAMODB_EXECUTIONS_TABLE")
            or rn.dynamodb_table_name("executions", capability=cap, environment=env)
        ),
        dynamodb_prompts_table=(
            os.getenv("DYNAMODB_PROMPTS_TABLE")
            or rn.dynamodb_table_name("prompts", capability=cap, environment=env)
        ),
        s3_journey_logs_bucket=(
            os.getenv("S3_JOURNEY_LOGS_BUCKET")
            or rn.s3_bucket_name("journey-logs", capability=cap, environment=env)
        ),
        s3_journey_reports_bucket=(
            os.getenv("S3_JOURNEY_REPORTS_BUCKET")
            or rn.s3_bucket_name("journey-reports", capability=cap, environment=env)
        ),
        max_concurrent_jobs=int(os.getenv("MAX_CONCURRENT_JOBS", "10")),
        capability_name=cap,
        environment=env,
    )


def get_config() -> EngineConfig:
    """Return the wired engine config, defaulting to env-var-driven values."""
    global _global_config
    if _global_config is None:
        _global_config = config_from_environment()
    return _global_config


def reset_config() -> None:
    """Clear the wired config (mainly for tests)."""
    global _global_config
    _global_config = None
