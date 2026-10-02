"""
Resource naming helpers — mirrors nexus_operator.utils.naming.ResourceNaming.

Pattern: {capability}-{environment}-{purpose}
Example: ai-engine-local-journeys  (local K3s)
         ai-engine-dev-journeys      (remote K8 dev via operator)

Remote AWS CloudFormation uses legacy names (ai-engine-journeys-{env});
override via explicit env vars / SSM when deploying to real AWS.
"""

from __future__ import annotations

import os
import re


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]", "-", name.lower())
    sanitized = re.sub(r"-+", "-", sanitized)
    return sanitized.strip("-")


def capability_name() -> str:
    return sanitize_name(os.getenv("CAPABILITY_NAME", "ai-engine"))


def environment_name() -> str:
    return sanitize_name(os.getenv("ENVIRONMENT", "dev"))


def dynamodb_table_name(
    purpose: str,
    *,
    capability: str | None = None,
    environment: str | None = None,
) -> str:
    cap = sanitize_name(capability) if capability else capability_name()
    env = sanitize_name(environment) if environment else environment_name()
    return f"{cap}-{env}-{purpose}"


def glue_database_name(*, capability: str | None = None, environment: str | None = None) -> str:
    cap = sanitize_name(capability) if capability else capability_name()
    env = sanitize_name(environment) if environment else environment_name()
    return f"{cap.replace('-', '_')}_{env.replace('-', '_')}_db"


def resolved_glue_database() -> str:
    """Env override, else {capability}_{env}_db. Never silently use Glue 'default'."""
    return (os.getenv("GLUE_DATABASE_NAME") or os.getenv("GLUE_DATABASE") or glue_database_name()).strip()


def resolved_dlq_table() -> str:
    """Env override, else {capability}-{environment}-dlq."""
    return (os.getenv("DYNAMODB_DLQ_TABLE") or dynamodb_table_name("dlq")).strip()


def s3_bucket_name(
    purpose: str,
    *,
    capability: str | None = None,
    environment: str | None = None,
    account_id: str | None = None,
) -> str:
    cap = sanitize_name(capability) if capability else capability_name()
    env = sanitize_name(environment) if environment else environment_name()
    base = f"{cap}-{env}-{purpose}"
    acct = account_id or os.getenv("LOCAL_AWS_ACCOUNT_ID") or os.getenv("AWS_ACCOUNT_ID")
    return f"{base}-{acct}" if acct else base


def legacy_remote_table_name(purpose: str, *, environment: str | None = None) -> str:
    """CloudFormation / SSM legacy pattern: ai-engine-{purpose}-{env}."""
    env = sanitize_name(environment) if environment else environment_name()
    return f"ai-engine-{purpose}-{env}"


def legacy_remote_bucket_name(purpose: str, *, environment: str | None = None) -> str:
    """CloudFormation legacy S3 pattern: ai-engine-{purpose}-{env}."""
    env = sanitize_name(environment) if environment else environment_name()
    return f"ai-engine-{purpose}-{env}"
