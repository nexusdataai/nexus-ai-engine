"""DynamoDB table schemas for Nexus AI Engine (spec 050).

Used by moto integration tests and local provisioning helpers.
CloudFormation source of truth: deploy/cloudformation/ai-engine-storage.yaml
"""

from __future__ import annotations

from typing import Any


def table_names(env: str) -> dict[str, str]:
    return {
        "journeys": f"ai-engine-journeys-{env}",
        "executions": f"ai-engine-executions-{env}",
        "prompts": f"ai-engine-prompts-{env}",
    }


def s3_bucket_names(env: str) -> dict[str, str]:
    return {
        "logs": f"ai-engine-journey-logs-{env}",
        "reports": f"ai-engine-journey-reports-{env}",
    }


def journeys_table_definition(table_name: str) -> dict[str, Any]:
    return {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "entity_type", "AttributeType": "S"},
            {"AttributeName": "updated_at", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "started_at", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "entity_type", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI2",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "started_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    }


def executions_table_definition(table_name: str) -> dict[str, Any]:
    return {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "journey_id", "AttributeType": "S"},
            {"AttributeName": "started_at", "AttributeType": "S"},
            {"AttributeName": "tenant_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "journey_id", "KeyType": "HASH"},
                    {"AttributeName": "started_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI2",
                "KeySchema": [
                    {"AttributeName": "tenant_id", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    }


def prompts_table_definition(table_name: str) -> dict[str, Any]:
    return {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
    }


def create_all_tables(client: Any, env: str) -> dict[str, str]:
    """Create journeys, executions, and prompts tables. Returns table name map."""
    names = table_names(env)
    for key, definition_fn in (
        ("journeys", journeys_table_definition),
        ("executions", executions_table_definition),
        ("prompts", prompts_table_definition),
    ):
        table_name = names[key]
        try:
            client.create_table(**definition_fn(table_name))
        except client.exceptions.ResourceInUseException:
            pass
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)
        if key == "executions":
            try:
                client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
                )
            except Exception:
                pass
    return names


def describe_tables(client: Any, env: str) -> dict[str, str]:
    """Return {logical_name: TableStatus} for all engine tables."""
    result: dict[str, str] = {}
    for logical, name in table_names(env).items():
        desc = client.describe_table(TableName=name)["Table"]
        result[logical] = desc["TableStatus"]
    return result
