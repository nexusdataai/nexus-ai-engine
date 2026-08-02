"""Moto tests for DynamoDB table provisioning (spec 050, dynamodb-tables todo)."""

from __future__ import annotations

import boto3
import moto
import pytest

from nexus_ai_engine.adapters.dynamodb.table_definitions import (
    create_all_tables,
    describe_tables,
    executions_table_definition,
    journeys_table_definition,
    prompts_table_definition,
    s3_bucket_names,
    table_names,
)


@pytest.mark.parametrize(
    "definition_fn,key",
    [
        (journeys_table_definition, "journeys"),
        (executions_table_definition, "executions"),
        (prompts_table_definition, "prompts"),
    ],
)
def test_table_definition_has_pk_sk(definition_fn, key):
    names = table_names("test")
    spec = definition_fn(names[key])
    keys = {k["AttributeName"] for k in spec["KeySchema"]}
    assert keys == {"PK", "SK"}


def test_s3_bucket_names_match_spec():
    buckets = s3_bucket_names("prod")
    assert buckets["logs"] == "ai-engine-journey-logs-prod"
    assert buckets["reports"] == "ai-engine-journey-reports-prod"


@moto.mock_aws
def test_create_all_tables_active():
    client = boto3.client("dynamodb", region_name="us-east-1")
    names = create_all_tables(client, "test")
    assert names["executions"] == "ai-engine-executions-test"
    statuses = describe_tables(client, "test")
    assert statuses == {"journeys": "ACTIVE", "executions": "ACTIVE", "prompts": "ACTIVE"}

    exec_desc = client.describe_table(TableName=names["executions"])["Table"]
    gsi_names = {g["IndexName"] for g in exec_desc.get("GlobalSecondaryIndexes", [])}
    assert gsi_names == {"GSI1", "GSI2"}

    journeys_desc = client.describe_table(TableName=names["journeys"])["Table"]
    jgsi = {g["IndexName"] for g in journeys_desc.get("GlobalSecondaryIndexes", [])}
    assert jgsi == {"GSI1", "GSI2"}


@moto.mock_aws
def test_create_all_tables_idempotent():
    client = boto3.client("dynamodb", region_name="us-east-1")
    create_all_tables(client, "dev")
    create_all_tables(client, "dev")
    assert describe_tables(client, "dev")["executions"] == "ACTIVE"
