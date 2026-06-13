"""Unit tests for the SSM-driven EngineConfig loader in `server/cli.py`.

The loader is invoked from `_cmd_serve` when the operator passes
`--ssm-prefix /ai-engine/{env}/`. We mock `boto3.client('ssm')` so the
test does not require AWS credentials or network.

Covers:
- SSM-only path: every field present in SSM populates EngineConfig.
- Per-key env-var fallback: keys absent in SSM fall back to the matching
  ``DYNAMODB_*`` / ``S3_*`` env var (so an operator can override one
  field without round-tripping through SSM).
- Empty SSM prefix: pure env-var path still produces a usable config.
- The ``_SSM_TO_ENV_FALLBACK`` contract is the single source of truth for
  which env var pairs with which SSM key.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nexus_ai_engine.server.cli import (
    _SSM_TO_ENV_FALLBACK,
    _build_engine_config_from_ssm,
)


def _fake_ssm_client(parameters: dict[str, str]) -> MagicMock:
    """Return a MagicMock that mimics boto3 ssm client paginator output."""
    paginator = MagicMock()
    paginator.paginate.return_value = iter(
        [{"Parameters": [{"Name": k, "Value": v} for k, v in parameters.items()]}]
    )
    client = MagicMock()
    client.get_paginator.return_value = paginator
    return client


def test_ssm_only_path_populates_all_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    # Clear any env vars that could mask SSM values during assertion.
    for env_key in _SSM_TO_ENV_FALLBACK.values():
        monkeypatch.delenv(env_key, raising=False)

    prefix = "/ai-engine/test/"
    ssm_params = {
        f"{prefix}dynamodb_transformation_table":  "ai-engine-journeys-test",
        f"{prefix}dynamodb_prompts_table":         "ai-engine-journeys-test",
        f"{prefix}s3_journey_logs_bucket":         "ai-engine-journeys-logs-test",
        f"{prefix}s3_journey_reports_bucket":      "ai-engine-journeys-reports-test",
        f"{prefix}max_concurrent_jobs":            "25",
        f"{prefix}capability_name":                "demand-forecasting",
        f"{prefix}environment":                    "test",
        f"{prefix}role_arn":                       "arn:aws:iam::123:role/r",
    }

    fake_client = _fake_ssm_client(ssm_params)
    with patch("boto3.client", return_value=fake_client):
        cfg = _build_engine_config_from_ssm(prefix)

    assert cfg.region == "us-east-1"
    assert cfg.role_arn == "arn:aws:iam::123:role/r"
    assert cfg.dynamodb_transformation_table == "ai-engine-journeys-test"
    assert cfg.dynamodb_prompts_table == "ai-engine-journeys-test"
    assert cfg.s3_journey_logs_bucket == "ai-engine-journeys-logs-test"
    assert cfg.s3_journey_reports_bucket == "ai-engine-journeys-reports-test"
    assert cfg.max_concurrent_jobs == 25
    assert cfg.capability_name == "demand-forecasting"
    assert cfg.environment == "test"


def test_env_var_fallback_for_keys_absent_in_ssm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Half-and-half: SSM has a few keys, env vars cover the rest."""
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    # SSM provides the table name only; everything else must come from env.
    monkeypatch.setenv("S3_JOURNEY_LOGS_BUCKET",    "from-env-logs")
    monkeypatch.setenv("S3_JOURNEY_REPORTS_BUCKET", "from-env-reports")
    monkeypatch.setenv("DYNAMODB_PROMPTS_TABLE",    "from-env-prompts")
    monkeypatch.setenv("MAX_CONCURRENT_JOBS",       "7")
    monkeypatch.setenv("CAPABILITY_NAME",           "from-env-cap")
    monkeypatch.setenv("ENVIRONMENT",               "from-env-environment")

    prefix = "/ai-engine/staging/"
    ssm_params = {
        f"{prefix}dynamodb_transformation_table": "from-ssm-table",
    }

    fake_client = _fake_ssm_client(ssm_params)
    with patch("boto3.client", return_value=fake_client):
        cfg = _build_engine_config_from_ssm(prefix)

    assert cfg.dynamodb_transformation_table == "from-ssm-table"   # SSM wins
    assert cfg.dynamodb_prompts_table == "from-env-prompts"        # env fallback
    assert cfg.s3_journey_logs_bucket == "from-env-logs"           # env fallback
    assert cfg.s3_journey_reports_bucket == "from-env-reports"     # env fallback
    assert cfg.max_concurrent_jobs == 7                            # env fallback (cast)
    assert cfg.capability_name == "from-env-cap"
    assert cfg.environment == "from-env-environment"


def test_empty_ssm_pure_env_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty SSM result must not crash; env vars produce a usable config."""
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("DYNAMODB_TRANSFORMATION_TABLE", "env-only-table")
    monkeypatch.setenv("S3_JOURNEY_LOGS_BUCKET",        "env-only-logs")
    # Leave other env vars unset so defaults kick in for max_concurrent_jobs etc.
    for k in ("DYNAMODB_PROMPTS_TABLE", "S3_JOURNEY_REPORTS_BUCKET",
              "MAX_CONCURRENT_JOBS", "CAPABILITY_NAME", "ENVIRONMENT",
              "AWS_ROLE_ARN"):
        monkeypatch.delenv(k, raising=False)

    fake_client = _fake_ssm_client({})  # SSM returns zero parameters
    with patch("boto3.client", return_value=fake_client):
        cfg = _build_engine_config_from_ssm("/ai-engine/empty/")

    assert cfg.region == "ap-south-1"
    assert cfg.dynamodb_transformation_table == "env-only-table"
    assert cfg.s3_journey_logs_bucket == "env-only-logs"
    assert cfg.dynamodb_prompts_table is None
    assert cfg.s3_journey_reports_bucket is None
    assert cfg.max_concurrent_jobs == 10        # documented default
    assert cfg.capability_name == "call-processing"
    assert cfg.environment == "dev"


def test_fallback_contract_covers_every_optional_field() -> None:
    """Regression guard for the SSM key → env var mapping."""
    # If a future engineer adds a new EngineConfig field they must update
    # the fallback table too, or document that the field has no env-var
    # override. These are the keys we currently promise to back-fill.
    assert _SSM_TO_ENV_FALLBACK == {
        "role_arn":                       "AWS_ROLE_ARN",
        "dynamodb_transformation_table":  "DYNAMODB_TRANSFORMATION_TABLE",
        "dynamodb_prompts_table":         "DYNAMODB_PROMPTS_TABLE",
        "s3_journey_logs_bucket":         "S3_JOURNEY_LOGS_BUCKET",
        "s3_journey_reports_bucket":      "S3_JOURNEY_REPORTS_BUCKET",
        "max_concurrent_jobs":            "MAX_CONCURRENT_JOBS",
        "capability_name":                "CAPABILITY_NAME",
        "environment":                    "ENVIRONMENT",
    }
